"""SMTP email service — Phase 6 / production approval emails.

A small async SMTP client built on the Python standard library
(``smtplib`` + ``email.message.EmailMessage``). Designed for low-volume
transactional emails such as approval-request notifications.

The service is intentionally small and side-effect-free:

* Configuration is read from :class:`Settings` (see
  :mod:`backend.app.core.config`).
* The public entry point is :func:`send_email`. It never raises
  into the caller's main workflow — failures are reported via the
  return value and the audit log. Draft creation must NEVER fail
  because SMTP is unavailable.
* Every failure is classified into a stable category (config,
  auth, connection, TLS, recipient, unknown) and the category is
  written into the audit event so the operator can tell at a glance
  why an email was not delivered.
* Bounded retry: at most ``EMAIL_MAX_RETRIES`` attempts with a
  short back-off for transient SMTP errors. No infinite loop.
* The body is NEVER logged. Only its SHA-256[:16] fingerprint
  and the recipient-domain (not the full address) appear in audit
  events.

HTML email + plain-text fallback:

* :func:`build_approval_email` returns a ``(text_body, html_body)``
  tuple. The plain-text variant is fully readable in any mail
  client; the HTML variant uses an inline-styled LinkedIn-styled
  layout that renders correctly in Gmail, Outlook, Apple Mail,
  and mobile clients. No external CSS, no images, no JavaScript.

NEVER log: ``SMTP_PASSWORD``, email body, ``approval_token``,
LinkedIn access / refresh / authorization code, client secret.
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import logging
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional, Sequence, Tuple

from backend.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class EmailResult:
    """Outcome of a single ``send_email`` call."""

    success: bool
    error: Optional[str] = None
    error_category: Optional[str] = None
    attempts: int = 0
    fingerprint_sha256_16: Optional[str] = None

    def to_audit_dict(self) -> dict:
        """Project the result into a safe audit-event dict.

        The audit log persists these fields; consumers MUST never
        write the email body, the SMTP password, the approval
        token, or the raw recipient address.
        """
        d: dict = {"success": self.success}
        if self.error is not None:
            d["error"] = self.error
        if self.error_category is not None:
            d["error_category"] = self.error_category
        d["attempts"] = self.attempts
        if self.fingerprint_sha256_16 is not None:
            d["body_fingerprint_sha256_16"] = self.fingerprint_sha256_16
        return d


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


#: Stable error categories. The set is closed — new entries must be
#: added deliberately so audit events remain queryable.
ERROR_CATEGORY_CONFIG = "config"
ERROR_CATEGORY_AUTH = "auth"
ERROR_CATEGORY_CONNECTION = "connection"
ERROR_CATEGORY_TLS = "tls"
ERROR_CATEGORY_RECIPIENT = "recipient"
ERROR_CATEGORY_PAYLOAD = "payload"
ERROR_CATEGORY_UNKNOWN = "unknown"

#: Hard cap on the email subject line. SMTP / RFC 5322 limits the
#: subject to 998 octets, but a reasonable production limit is
#: 256 characters which is well within all major SMTP servers.
MAX_SUBJECT_CHARS = 256

#: Hard cap on the rendered text body. The legacy builder keeps the
#: body under ~1 MB; this is a defensive limit to prevent
#: pathological payloads from leaking through SMTP.
MAX_TEXT_BODY_CHARS = 500_000

#: Hard cap on the rendered HTML body.
MAX_HTML_BODY_CHARS = 1_000_000

#: Hard cap on the From address length. RFC 5322 allows long local
#: parts but production servers rarely accept more than 254.
MAX_FROM_CHARS = 254


def classify_smtp_exception(exc: BaseException) -> Tuple[str, str]:
    """Classify a raw exception into a stable (category, code) pair.

    Returns ``(category, code)`` where ``code`` is the exception
    class name (e.g. ``"SMTPAuthenticationError"``) and ``category``
    is one of the closed set above. The code is safe to log; the
    category is safe to surface to the API.

    The classification is intentionally narrow and pattern-based —
    we do not import every smtplib constant; we use the exception
    class name and a small message-sniff fallback.
    """
    cls = exc.__class__.__name__
    msg = str(exc) or cls

    # Config: nothing to send to. Either not configured, or the
    # server rejected our payload outright.
    if cls in {"EmailNotConfiguredError"}:
        return ERROR_CATEGORY_CONFIG, cls
    if "SMTPRecipientsRefused" in cls:
        return ERROR_CATEGORY_RECIPIENT, cls
    if "SMTPSenderRefused" in cls:
        return ERROR_CATEGORY_RECIPIENT, cls
    if cls == "SMTPServerDisconnected":
        return ERROR_CATEGORY_CONNECTION, cls
    if "SMTPAuthenticationError" in cls or "SMTPHeloError" in cls:
        # The server responded but the auth / handshake failed —
        # usually a config issue (wrong username/password).
        return ERROR_CATEGORY_AUTH, cls
    if "SMTPConnectError" in cls or "SMTPServerDisconnected" in cls:
        return ERROR_CATEGORY_CONNECTION, cls
    if "SSL" in cls or "TLS" in cls or "ssl" in cls.lower():
        return ERROR_CATEGORY_TLS, cls
    if "SSLError" in cls or "ssl.SSLError" in cls:
        return ERROR_CATEGORY_TLS, cls
    # Catch-all: network connection issues.
    if "ConnectionError" in cls or "TimeoutError" in cls or "OSError" in cls:
        return ERROR_CATEGORY_CONNECTION, cls
    # Some smtplib errors expose the server reply text — keep only
    # the class name.
    return ERROR_CATEGORY_UNKNOWN, cls


def _safe_recipient_domain(address: str) -> str:
    """Return the domain part of an email address, never the full
    recipient. Safe to log / audit."""
    if not address or "@" not in address:
        return ""
    try:
        return address.rsplit("@", 1)[-1].lower()
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# SMTP transport
# ---------------------------------------------------------------------------


#: Maximum number of total attempts (initial + retries) per
#: ``send_email`` call. Bounded to keep the calling workflow
#: (draft creation) responsive.
EMAIL_MAX_ATTEMPTS = 3

#: Initial retry back-off in seconds. Doubles on each attempt.
EMAIL_RETRY_BACKOFF_SECONDS = 0.5


def _smtp_send(
    host: str,
    port: int,
    username: Optional[str],
    password: Optional[str],
    use_tls: bool,
    message: EmailMessage,
) -> None:
    """Synchronous SMTP send. Run inside ``asyncio.to_thread``.

    Raises whatever ``smtplib`` raises. Callers are responsible
    for classifying the exception via :func:`classify_smtp_exception`.
    """
    if use_tls:
        with smtplib.SMTP(host, port, timeout=15) as client:
            client.ehlo()
            client.starttls()
            client.ehlo()
            if username and password:
                client.login(username, password)
            client.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=15) as client:
            client.ehlo()
            if username and password:
                client.login(username, password)
            client.send_message(message)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def send_email(
    *,
    to: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> EmailResult:
    """Send one transactional email.

    The message is always sent as ``multipart/alternative`` when
    ``html_body`` is provided, so the recipient's mail client
    falls back to ``text_body`` cleanly when HTML is disabled.

    Returns an :class:`EmailResult` whose ``success`` flag indicates
    whether the SMTP server accepted the message. Any error is
    captured and returned — this function never raises into the
    caller.

    Configuration is read from :class:`Settings`. If SMTP is not
    configured (any of host / username / password / from is
    missing), the call short-circuits and returns
    ``success=False`` with category ``config`` and code
    ``email_not_configured`` — the calling workflow is unaffected.

    Defensive input caps (Phase 16):
    * subject: capped at :data:`MAX_SUBJECT_CHARS`
    * text_body: capped at :data:`MAX_TEXT_BODY_CHARS`
    * html_body: capped at :data:`MAX_HTML_BODY_CHARS`
    * From:    must look like an email address and fit in
                :data:`MAX_FROM_CHARS`
    * to:      must be a valid email address (see
                :func:`is_valid_recipient`)
    """
    cfg = settings or get_settings()

    # Defensive input validation. None of these can be triggered by
    # the existing call sites (which build the subject / body /
    # from / to from controlled inputs), but a future caller could.
    if not subject or not subject.strip():
        return EmailResult(
            success=False,
            error="empty_subject",
            error_category=ERROR_CATEGORY_PAYLOAD,
        )
    if len(subject) > MAX_SUBJECT_CHARS:
        subject = subject[: MAX_SUBJECT_CHARS - 1] + "…"
    if len(text_body) > MAX_TEXT_BODY_CHARS:
        text_body = text_body[:MAX_TEXT_BODY_CHARS]
    if html_body and len(html_body) > MAX_HTML_BODY_CHARS:
        html_body = html_body[:MAX_HTML_BODY_CHARS]
    if cfg.email_from and (
        not is_valid_recipient(cfg.email_from)
        or len(cfg.email_from) > MAX_FROM_CHARS
    ):
        # Misconfigured From address — refuse to send so we don't
        # risk spoofing the brand or being silently dropped by the
        # receiving server.
        return EmailResult(
            success=False,
            error="invalid_from",
            error_category=ERROR_CATEGORY_CONFIG,
        )
    if not to or not is_valid_recipient(to):
        return EmailResult(
            success=False,
            error="invalid_recipient",
            error_category=ERROR_CATEGORY_RECIPIENT,
        )

    if not (
        cfg.smtp_host
        and cfg.smtp_username
        and cfg.smtp_password
        and cfg.email_from
        and to
    ):
        return EmailResult(
            success=False,
            error="email_not_configured",
            error_category=ERROR_CATEGORY_CONFIG,
        )

    fingerprint = _fingerprint(f"{to}|{subject}|{text_body}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.email_from
    msg["To"] = to
    # Plain text first — the standard for multipart/alternative
    # is text/plain then text/html.
    msg.set_content(text_body)
    if html_body:
        # ``add_alternative`` switches the message to
        # ``multipart/alternative`` automatically. The text/html
        # part is added with the correct Content-Type.
        msg.add_alternative(html_body, subtype="html")

    last_category = ERROR_CATEGORY_UNKNOWN
    last_code = "unknown"
    backoff = EMAIL_RETRY_BACKOFF_SECONDS

    for attempt in range(1, EMAIL_MAX_ATTEMPTS + 1):
        try:
            await asyncio.to_thread(
                _smtp_send,
                cfg.smtp_host,
                cfg.smtp_port,
                cfg.smtp_username,
                cfg.smtp_password,
                cfg.email_use_tls,
                msg,
            )
            return EmailResult(
                success=True,
                attempts=attempt,
                fingerprint_sha256_16=fingerprint,
            )
        except Exception as exc:  # noqa: BLE001 — broad on purpose
            category, code = classify_smtp_exception(exc)
            last_category = category
            last_code = code
            # Auth / config / recipient / payload errors are NOT
            # transient — retrying would not help. Connection / TLS
            # / unknown errors are retried up to the cap.
            transient = category in (
                ERROR_CATEGORY_CONNECTION,
                ERROR_CATEGORY_TLS,
                ERROR_CATEGORY_UNKNOWN,
            )
            if not transient or attempt >= EMAIL_MAX_ATTEMPTS:
                logger.warning(
                    "SMTP send failed (attempt %d/%d, category=%s, code=%s)",
                    attempt,
                    EMAIL_MAX_ATTEMPTS,
                    category,
                    code,
                )
                return EmailResult(
                    success=False,
                    error=code,
                    error_category=category,
                    attempts=attempt,
                    fingerprint_sha256_16=fingerprint,
                )
            logger.info(
                "SMTP transient failure (attempt %d/%d, category=%s, "
                "code=%s); retrying in %.1fs",
                attempt,
                EMAIL_MAX_ATTEMPTS,
                category,
                code,
                backoff,
            )
            await asyncio.sleep(backoff)
            backoff *= 2

    # Defensive: the loop should have returned already.
    return EmailResult(
        success=False,
        error=last_code,
        error_category=last_category,
        attempts=EMAIL_MAX_ATTEMPTS,
        fingerprint_sha256_16=fingerprint,
    )


# ---------------------------------------------------------------------------
# Approval email rendering
# ---------------------------------------------------------------------------


#: Display labels for the canonical source types the user sees
#: in the email. The mapping mirrors the project's
#: ``SOURCE_TYPE_LABEL`` in the design system.
SOURCE_TYPE_DISPLAY_LABEL = {
    "github_repository": "GitHub Repository",
    "github_readme": "GitHub README",
    "blog_article": "Blog Article",
    "documentation": "Documentation",
    "product_page": "Product Announcement",
    "generic_webpage": "Web Article",
}


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _html_escape(text: str) -> str:
    """Escape a string for safe inclusion in an HTML email body."""
    return html_lib.escape(text or "", quote=True)


def _preview_text(content: str, *, max_chars: int = 480) -> str:
    """Build a short preview of the post content for the email.

    The preview preserves paragraph breaks and bullets (which are
    already LinkedIn-native, plain text). We never inject Markdown
    here — Phase 2's ``normalize_linkedin_post`` is the canonical
    layer and the email consumes the same stored content.
    """
    if not content:
        return ""
    text = content.strip()
    if len(text) <= max_chars:
        return text
    head = text[:max_chars]
    # Try to cut at a paragraph break so the preview doesn't end
    # mid-sentence.
    last_break = head.rfind("\n\n")
    if last_break > max_chars // 2:
        return head[:last_break].rstrip() + "…"
    last_break = head.rfind("\n")
    if last_break > max_chars // 2:
        return head[:last_break].rstrip() + "…"
    return head.rstrip() + "…"


def _hashtags_block(hashtags: Sequence[str]) -> str:
    """Render a hashtags list as a single line for the email body."""
    cleaned = [h if h.startswith("#") else f"#{h}" for h in (hashtags or []) if h]
    if not cleaned:
        return ""
    return " ".join(cleaned)


# ---------------------------------------------------------------------------
# Public: build_approval_email
# ---------------------------------------------------------------------------


def build_approval_email(
    *,
    draft_title: str,
    draft_content: str,
    draft_hashtags: Sequence[str],
    approval_url: str,
    review_url: str,
    source_label: Optional[str] = None,
    source_url: Optional[str] = None,
    expires_at_display: Optional[str] = None,
    frontend_brand: str = "LinkedIn AI Studio",
) -> Tuple[str, str]:
    """Build the approval-request email as a ``(text, html)`` tuple.

    The plain text variant is fully readable in any mail client.
    The HTML variant is an inline-styled, mobile-friendly layout
    that does not depend on external CSS / images / JS.

    Both variants:

    * show the post title, a preview of the normalized content,
      and a list of hashtags at the end of the post;
    * show a "Source" block when ``source_url`` is supplied (Phase 5
      source-mode drafts) and ``source_label`` describes what kind
      of source it is (e.g. "GitHub Repository");
    * show a primary "Approve & Publish" button (HTML) / link
      (text) and a secondary "Review Draft" link;
    * show the approval link's expiry in a non-leaking format.

    The email never includes the approval token in human-readable
    form; the token only appears inside the URL.
    """
    safe_title = _html_escape(draft_title or "Untitled draft")
    safe_preview = _html_escape(_preview_text(draft_content or ""))
    hashtags_str = _hashtags_block(draft_hashtags or [])
    safe_hashtags_html = _html_escape(hashtags_str)
    safe_hashtags_text = hashtags_str

    safe_source_label = _html_escape(source_label) if source_label else ""
    safe_source_url = _html_escape(source_url) if source_url else ""
    safe_approval_url = _html_escape(approval_url)
    safe_review_url = _html_escape(review_url)
    safe_brand = _html_escape(frontend_brand)
    safe_expires = _html_escape(expires_at_display) if expires_at_display else ""

    # ---------- Plain text ----------
    text_lines: list[str] = []
    text_lines.append(frontend_brand)
    text_lines.append("")
    text_lines.append("New LinkedIn post waiting for approval")
    text_lines.append("=" * 44)
    text_lines.append("")
    text_lines.append(f"Title: {draft_title or 'Untitled draft'}")
    text_lines.append("")
    if source_label and source_url:
        text_lines.append(f"Source: {source_label}")
        text_lines.append(f"        {source_url}")
        text_lines.append("")
    text_lines.append("Post preview:")
    text_lines.append("-------------")
    text_lines.append(_preview_text(draft_content or "", max_chars=1200))
    if safe_hashtags_text:
        text_lines.append("")
        text_lines.append(safe_hashtags_text)
    text_lines.append("")
    text_lines.append("Actions:")
    text_lines.append("--------")
    text_lines.append(f"Approve & Publish: {approval_url}")
    text_lines.append(f"Review Draft:      {review_url}")
    if expires_at_display:
        text_lines.append("")
        text_lines.append(f"This approval link expires {expires_at_display}.")
    text_lines.append("")
    text_lines.append(
        "If you did not request this post, you can safely ignore this email."
    )
    text_body = "\n".join(text_lines)

    # ---------- HTML ----------
    # Inline-styled, table-based layout so it renders correctly in
    # Gmail, Outlook, Apple Mail, and mobile clients without
    # external CSS. No images, no JavaScript.
    html_body = _render_approval_html(
        brand=safe_brand,
        title=safe_title,
        preview=safe_preview,
        hashtags_html=safe_hashtags_html,
        source_label_html=safe_source_label,
        source_url=safe_source_url,
        source_url_display=source_url or "",
        approval_url=safe_approval_url,
        review_url=safe_review_url,
        expires_html=safe_expires,
    )

    return text_body, html_body


def _render_approval_html(
    *,
    brand: str,
    title: str,
    preview: str,
    hashtags_html: str,
    source_label_html: str,
    source_url: str,
    source_url_display: str,
    approval_url: str,
    review_url: str,
    expires_html: str,
) -> str:
    """Render the HTML variant of the approval email.

    All string interpolation goes through ``_html_escape`` at the
    call site so this function never needs to escape again.
    """
    source_block = ""
    if source_url:
        # Use the display URL (unescaped) inside the link, the
        # escaped URL in the ``href``.
        source_block = (
            '<tr><td style="padding:0 0 16px 0;">'
            '<div style="font-size:11px;font-weight:600;letter-spacing:0.08em;'
            'text-transform:uppercase;color:#7a7a85;margin-bottom:6px;">Source</div>'
            f'<div style="font-size:14px;color:#c2c2c8;">'
            f'{source_label_html}</div>'
            f'<a href="{source_url}" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-block;margin-top:6px;word-break:break-all;'
            'color:#a78bfa;text-decoration:none;font-size:13px;">'
            f'{_html_escape(source_url_display)}</a></td></tr>'
        )

    expires_block = ""
    if expires_html:
        expires_block = (
            '<tr><td style="padding:0 0 24px 0;">'
            '<div style="font-size:12px;color:#7a7a85;line-height:18px;">'
            f'This approval link expires <strong style="color:#c2c2c8;">'
            f'{expires_html}</strong>.</div></td></tr>'
        )

    # Convert the post preview's paragraph breaks to <p> tags
    # so the HTML mirrors the LinkedIn-native formatting.
    preview_paragraphs = [
        p.strip() for p in (preview or "").split("\n\n") if p.strip()
    ]
    if not preview_paragraphs:
        preview_paragraphs = ["<em>(empty post)</em>"]
    preview_html = "".join(
        f'<p style="margin:0 0 14px 0;font-size:15px;line-height:24px;'
        f'color:#e4e4e7;white-space:pre-line;">{p}</p>'
        for p in preview_paragraphs
    )

    hashtags_block = ""
    if hashtags_html:
        hashtags_block = (
            '<tr><td style="padding:0 0 24px 0;">'
            '<div style="font-size:14px;line-height:22px;color:#a78bfa;'
            'word-break:break-word;">'
            f'{hashtags_html}</div></td></tr>'
        )

    # Note: all variable interpolation has already been escaped
    # by the caller; we only insert these as already-safe strings.
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <meta name="x-apple-disable-message-reformatting" />
    <title>New LinkedIn post waiting for approval</title>
  </head>
  <body style="margin:0;padding:0;background-color:#070709;color:#fafafa;
               font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
               'Inter',Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color:#070709;padding:32px 16px;">
      <tr><td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;width:100%;background-color:rgba(20,20,24,0.85);
                      border:1px solid rgba(255,255,255,0.08);
                      border-radius:16px;overflow:hidden;">
          <tr><td style="padding:24px 28px;border-bottom:1px solid rgba(255,255,255,0.06);">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="vertical-align:middle;">
                  <div style="font-size:12px;font-weight:600;letter-spacing:0.08em;
                              text-transform:uppercase;color:#a78bfa;">{brand}</div>
                  <div style="margin-top:4px;font-size:18px;font-weight:600;
                              color:#fafafa;line-height:24px;">New LinkedIn post
                    waiting for approval</div>
                </td>
                <td align="right" valign="middle"
                    style="vertical-align:middle;">
                  <span style="display:inline-block;padding:4px 10px;
                               border-radius:999px;background-color:rgba(245,158,11,0.16);
                               color:#fcd34d;font-size:11px;font-weight:600;
                               letter-spacing:0.06em;text-transform:uppercase;">
                    Pending approval
                  </span>
                </td>
              </tr>
            </table>
          </td></tr>

          <tr><td style="padding:24px 28px 0 28px;">
            <div style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                        text-transform:uppercase;color:#7a7a85;margin-bottom:6px;">
              Post title
            </div>
            <div style="font-size:18px;font-weight:600;color:#fafafa;
                        line-height:26px;letter-spacing:-0.01em;">{title}</div>
          </td></tr>

          <tr><td style="padding:16px 28px 0 28px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="background-color:rgba(15,17,21,0.7);
                          border:1px solid rgba(255,255,255,0.06);
                          border-radius:12px;">
              <tr><td style="padding:18px 20px;">
                <div style="font-size:11px;font-weight:600;letter-spacing:0.08em;
                            text-transform:uppercase;color:#7a7a85;margin-bottom:10px;">
                  Post preview
                </div>
                {preview_html}
              </td></tr>
            </table>
          </td></tr>

          {hashtags_block}

          <tr><td style="padding:0 28px 0 28px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid rgba(255,255,255,0.06);
                          border-radius:12px;background-color:rgba(255,255,255,0.02);">
              {source_block}
            </table>
          </td></tr>

          <tr><td style="padding:24px 28px 8px 28px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="left" valign="top" style="padding:0 0 12px 0;">
                  <a href="{approval_url}" target="_blank" rel="noopener noreferrer"
                     style="display:inline-block;background-image:linear-gradient(180deg,#a78bfa 0%,#7c3aed 100%);
                            color:#ffffff;padding:13px 22px;border-radius:12px;
                            text-decoration:none;font-size:14px;font-weight:600;
                            letter-spacing:-0.005em;box-shadow:0 6px 18px rgba(124,58,237,0.45);">
                    Approve &amp; Publish
                  </a>
                </td>
              </tr>
              <tr>
                <td align="left">
                  <a href="{review_url}" target="_blank" rel="noopener noreferrer"
                     style="display:inline-block;background-color:rgba(255,255,255,0.04);
                            border:1px solid rgba(255,255,255,0.12);
                            color:#e4e4e7;padding:11px 20px;border-radius:12px;
                            text-decoration:none;font-size:14px;font-weight:500;">
                    Review Draft
                  </a>
                </td>
              </tr>
            </table>
          </td></tr>

          {expires_block}

          <tr><td style="padding:16px 28px 24px 28px;">
            <div style="font-size:12px;line-height:18px;color:#7a7a85;">
              If you did not request this post, you can safely ignore this email.
            </div>
          </td></tr>
        </table>

        <div style="max-width:600px;margin:16px auto 0 auto;text-align:center;
                    font-size:11px;color:#52525b;line-height:16px;">
          Sent by {brand}.
        </div>
      </td></tr>
    </table>
  </body>
</html>
"""


# ---------------------------------------------------------------------------
# Backward-compat: build_approval_email_body
# ---------------------------------------------------------------------------


def build_approval_email_body(
    *,
    draft_title: str,
    draft_topic: str,
    approval_token: str,
    approval_url: str,
) -> str:
    """Legacy plain-text approval email body.

    Preserved for callers (and tests) that imported this function
    before Phase 6. New callers should use
    :func:`build_approval_email` which returns ``(text, html)``
    and supports source-aware rendering.
    """
    return (
        "A new LinkedIn post is waiting for your approval.\n\n"
        f"Title: {draft_title}\n"
        f"Topic: {draft_topic}\n\n"
        "Approve the post by visiting the link below. The link contains\n"
        "a single-use approval token tied to your account.\n\n"
        f"{approval_url}\n\n"
        "If you did not request this post, you can safely ignore this email.\n"
    )


# ---------------------------------------------------------------------------
# Source label helper
# ---------------------------------------------------------------------------


def source_label_for(source_type: Optional[str]) -> Optional[str]:
    """Return the human-readable label for a source type, or None."""
    if not source_type:
        return None
    return SOURCE_TYPE_DISPLAY_LABEL.get(source_type, "Web Article")


# ---------------------------------------------------------------------------
# Recipient sanitization
# ---------------------------------------------------------------------------


_RECIPIENT_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


def is_valid_recipient(address: str) -> bool:
    """Cheap, conservative recipient validation.

    Stops clearly-malformed addresses (multiple @, whitespace, HTML,
    SQL-injection-style characters) before they ever leave the
    application. Real validation happens at the SMTP server — this
    only catches obvious garbage.
    """
    if not isinstance(address, str) or not address:
        return False
    if len(address) > 254:
        return False
    return bool(_RECIPIENT_RE.match(address))
