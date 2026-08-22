"""Resume parser — Phase 10.

A deterministic pipeline that converts a raw text (extracted from
PDF / DOCX by the upload endpoint) into a structured
:class:`Resume`.

The parser is rule-based. It DOES NOT call an LLM. The LLM-assisted
normalization step (Phase 10 follow-up) is layered on top by the
service after the user has reviewed the deterministic draft.

Hard rules
----------

* A field the parser cannot confidently extract stays empty.
* The parser never invents company names, dates, GPA, certifications,
  technologies, or achievements.
* Section detection is case-insensitive and tolerates a wide range
  of common resume headings (e.g. "EXPERIENCE", "Professional
  Experience", "Work Experience").
* Date strings are kept verbatim — no ISO conversion. The user
  edits them in the resume editor.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from backend.app.models.resume import (
    AchievementItem,
    CertificationItem,
    EducationItem,
    ExperienceItem,
    LinkItem,
    PersonalInfo,
    ProjectItem,
    Resume,
    SkillsGroup,
)


# Section headings → canonical key. Order matters for header-strip
# matching (we match the FIRST heading we see and treat everything
# after it as that section's body until another heading appears).
SECTION_PATTERNS = [
    ("personal", re.compile(
        r"^\s*(personal(?:\s+information)?|contact(?:\s+information)?|contact\s+details?)\s*:?\s*$",
        re.IGNORECASE,
    )),
    ("summary", re.compile(
        r"^\s*(summary|professional\s+summary|profile|about(?:\s+me)?|objective)\s*:?\s*$",
        re.IGNORECASE,
    )),
    ("experience", re.compile(
        r"^\s*(experience|work\s+experience|professional\s+experience|employment(?:\s+history)?|career\s+history)\s*:?\s*$",
        re.IGNORECASE,
    )),
    ("education", re.compile(
        r"^\s*(education|academic\s+background|educational\s+qualifications?)\s*:?\s*$",
        re.IGNORECASE,
    )),
    ("skills", re.compile(
        r"^\s*(skills|technical\s+skills|core\s+competencies|key\s+skills|expertise|technologies)\s*:?\s*$",
        re.IGNORECASE,
    )),
    ("projects", re.compile(
        r"^\s*(projects|personal\s+projects|key\s+projects|academic\s+projects)\s*:?\s*$",
        re.IGNORECASE,
    )),
    ("certifications", re.compile(
        r"^\s*(certifications?|licenses?\s+(?:and|&)\s+certifications?|professional\s+certifications?)\s*:?\s*$",
        re.IGNORECASE,
    )),
    ("achievements", re.compile(
        r"^\s*(achievements?|awards?|honors?|achievements\s+and\s+awards?)\s*:?\s*$",
        re.IGNORECASE,
    )),
    ("links", re.compile(
        r"^\s*(links|additional\s+links|profiles?)\s*:?\s*$",
        re.IGNORECASE,
    )),
]


_EMAIL_RE = re.compile(r"[\w\.\+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
)
_URL_RE = re.compile(r"https?://[\w\-\./\?=&%#:~+]+", re.IGNORECASE)
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/[\w\-]+", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*[•\-\*◦▪▫•]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\s*(\d+)\.\s+(.*)$")
_DATE_RANGE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4})"
    r"\s*[\-–to]+\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4}|Present|Current|Now)",
    re.IGNORECASE,
)
_SINGLE_DATE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4})"
)


# A "name" + "role" + "company" + "dates" line typically appears in
# the experience section. We use heuristics: if the line contains a
# date range, we treat it as an experience header.
def _looks_like_experience_header(line: str) -> bool:
    if not line or len(line) > 200:
        return False
    has_date = bool(_DATE_RANGE_RE.search(line) or _SINGLE_DATE_RE.search(line))
    # Heuristic: a header has either a date range OR a single
    # year (e.g. "Google · 2020–2023"). We require the line to
    # not start with a bullet and to not look like a sentence.
    starts_with_bullet = bool(_BULLET_RE.match(line)) or bool(
        _NUMBERED_RE.match(line)
    )
    return has_date and not starts_with_bullet and len(line.split()) < 25


def _split_role_company_dates(line: str) -> Tuple[str, str, str, str]:
    """Extract ``role @ company`` and date range from a header line.

    Returns ``(role, company, start_date, end_date)``. Anything
    that cannot be cleanly extracted stays empty.
    """
    role = company = start = end = ""

    # Date range
    m = _DATE_RANGE_RE.search(line)
    if m:
        start, end = m.group(1).strip(), m.group(2).strip()
        line = (line[: m.start()] + line[m.end():]).strip()
    else:
        m2 = _SINGLE_DATE_RE.search(line)
        if m2:
            start = end = m2.group(1).strip()
            line = (line[: m2.start()] + line[m2.end():]).strip()

    # Role @ Company or Role — Company or Role at Company
    role_company_match = re.search(
        r"^(?P<role>[^@\-|•\n]+?)\s*(?:@|at|\-|–|,|\|)\s*(?P<company>[^@\-|•\n]+?)\s*$",
        line.strip(),
    )
    if role_company_match:
        role = role_company_match.group("role").strip()
        company = role_company_match.group("company").strip()
    else:
        # Fallback: split on first comma or " at "
        parts = re.split(r"\s+(?:at|@)\s+|,\s+", line.strip(), maxsplit=1)
        if len(parts) == 2:
            role, company = parts[0].strip(), parts[1].strip()
        else:
            role = line.strip()
    return role, company, start, end


def _looks_like_education_header(line: str) -> bool:
    if not line or len(line) > 200:
        return False
    has_date = bool(_DATE_RANGE_RE.search(line) or _SINGLE_DATE_RE.search(line))
    starts_with_bullet = bool(_BULLET_RE.match(line)) or bool(
        _NUMBERED_RE.match(line)
    )
    return has_date and not starts_with_bullet and len(line.split()) < 25


def _looks_like_project_header(line: str) -> bool:
    # A project line is usually 1–12 words, no leading bullet, no
    # date range. URLs are stripped separately.
    if not line or len(line) > 200:
        return False
    if _BULLET_RE.match(line) or _NUMBERED_RE.match(line):
        return False
    if _DATE_RANGE_RE.search(line):
        return False
    if _URL_RE.search(line):
        return False
    return 1 <= len(line.split()) <= 14


def _section_bullets(section_body: str) -> List[str]:
    out: list = []
    for line in section_body.splitlines():
        m = _BULLET_RE.match(line)
        if m:
            out.append(m.group(1).strip())
        else:
            m2 = _NUMBERED_RE.match(line)
            if m2:
                out.append(m2.group(2).strip())
            else:
                stripped = line.strip()
                if stripped:
                    out.append(stripped)
    return out


def _parse_skills_block(text: str) -> List[SkillsGroup]:
    """A skills block may be a single list, or several category::

        Languages: Python, Go, TypeScript
        Cloud: AWS, GCP
        AI/ML: PyTorch, HuggingFace

    We split on lines that look like "Category: comma, separated"
    and accumulate. If no category headers exist, return a single
    group named "Skills".
    """
    groups: list = []
    current: Optional[SkillsGroup] = None
    category_re = re.compile(r"^([A-Za-z][A-Za-z0-9 &/\-\.]{0,40})\s*[:\-]\s*(.+)$")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = category_re.match(line)
        if m:
            cat = m.group(1).strip()
            rest = m.group(2).strip()
            skills = [s.strip() for s in re.split(r"[,;|]", rest) if s.strip()]
            current = SkillsGroup(category=cat, skills=skills)
            groups.append(current)
        elif current is not None:
            # Continuation of the current category: comma list.
            extra = [s.strip() for s in re.split(r"[,;|]", line) if s.strip()]
            current.skills.extend(extra)
        else:
            # No category yet — collect as "Skills".
            current = SkillsGroup(
                category="Skills",
                skills=[s.strip() for s in re.split(r"[,;|]", line) if s.strip()],
            )
            groups.append(current)
    return groups


def _parse_personal_header(text: str) -> PersonalInfo:
    """Best-effort extraction of contact info from the header
    block. Only fields that can be confidently extracted are set.
    """
    info = PersonalInfo()
    info.full_name = _first_meaningful_line(text)
    info.email = _first_match(_EMAIL_RE, text)
    info.phone = _first_match(_PHONE_RE, text)
    info.linkedin_url = _first_url_match(_LINKEDIN_RE, text)
    info.github_url = _first_url_match(_GITHUB_RE, text)
    info.portfolio_url = _first_other_url(text)
    info.location = _guess_location(text)
    info.headline = _guess_headline(text)
    return info


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        # The first non-empty line is almost always the name.
        return s[:120]
    return ""


def _first_match(pattern: re.Pattern, text: str) -> str:
    m = pattern.search(text)
    return m.group(0) if m else ""


def _first_url_match(pattern: re.Pattern, text: str) -> str:
    m = pattern.search(text)
    if not m:
        return ""
    # Find the full line that contains the match so we can grab
    # the full URL (the regex may have matched only a host path
    # without a protocol).
    start = m.start()
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    m2 = _URL_RE.search(line)
    if m2:
        return m2.group(0)
    return m.group(0)


def _first_other_url(text: str) -> str:
    for m in _URL_RE.finditer(text):
        url = m.group(0).lower()
        if "linkedin.com" in url or "github.com" in url:
            continue
        return m.group(0)
    return ""


def _guess_location(text: str) -> str:
    # Heuristic: a single line with a comma (City, State) before
    # the experience section.
    for line in text.splitlines()[:8]:
        s = line.strip()
        if not s:
            continue
        if "," in s and not _EMAIL_RE.search(s) and not _URL_RE.search(s) and len(s) < 80:
            return s
    return ""


def _guess_headline(text: str) -> str:
    # Heuristic: the line after the name, if short and not an
    # email / phone / URL.
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return ""
    second = lines[1]
    if (
        _EMAIL_RE.search(second)
        or _URL_RE.search(second)
        or _PHONE_RE.search(second)
    ):
        return ""
    if len(second) <= 120:
        return second
    return ""


def _parse_experience(text: str) -> List[ExperienceItem]:
    items: list = []
    current: Optional[ExperienceItem] = None
    for line in text.splitlines():
        if _looks_like_experience_header(line):
            if current is not None:
                items.append(current)
            role, company, start, end = _split_role_company_dates(line)
            current = ExperienceItem(
                role=role,
                company=company,
                start_date=start,
                end_date=end,
            )
        elif current is not None:
            s = line.strip()
            if s:
                m = _BULLET_RE.match(s)
                if m:
                    current.achievements.append(m.group(1).strip())
                else:
                    # Non-bullet body line: append to description.
                    current.description = (
        current.description + (" " if current.description else "") + s
    ).strip()
    if current is not None:
        items.append(current)
    return items


def _parse_education(text: str) -> List[EducationItem]:
    items: list = []
    current: Optional[EducationItem] = None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        m_date = _DATE_RANGE_RE.search(s) or _SINGLE_DATE_RE.search(s)
        looks_header = _looks_like_education_header(s) or (
            m_date
            and not _BULLET_RE.match(s)
            and len(s.split()) < 25
        )
        if looks_header:
            if current is not None:
                items.append(current)
            dates = ""
            if m_date:
                if hasattr(m_date, "group") and m_date.lastindex and m_date.lastindex >= 2:
                    dates = f"{m_date.group(1).strip()} - {m_date.group(2).strip()}"
                else:
                    dates = m_date.group(1).strip()
            # Strip the date substring from the header to get the
            # institution / degree / field.
            rest = _DATE_RANGE_RE.sub("", s)
            rest = _SINGLE_DATE_RE.sub("", rest).strip(" -–\t")
            current = EducationItem(
                institution=rest,
                degree="",
                field="",
                start_date="",
                end_date=dates,
            )
        elif current is not None:
            mm = _BULLET_RE.match(s)
            if mm:
                current.coursework.append(mm.group(1).strip())
            else:
                # Often a degree / field line.
                if not current.degree and not current.field:
                    current.degree = s
                else:
                    current.field = s
    if current is not None:
        items.append(current)
    return items


def _parse_projects(text: str) -> List[ProjectItem]:
    items: list = []
    current: Optional[ProjectItem] = None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _BULLET_RE.match(s)
        if m:
            content = m.group(1).strip()
            if current is None:
                current = ProjectItem(name="", description=content)
            else:
                current.achievements.append(content)
        elif _looks_like_project_header(s):
            if current is not None:
                items.append(current)
            current = ProjectItem(name=s)
        elif current is not None:
            current.description = (
        current.description + (" " if current.description else "") + s
    ).strip()
    # Pull URLs out of description.
    for it in items + ([current] if current else []):
        if it is None or not it.description:
            continue
        for m in _URL_RE.finditer(it.description):
            url = m.group(0)
            if "github.com" in url and not it.github_url:
                it.github_url = url
            elif not it.live_url:
                it.live_url = url
    if current is not None and current not in items:
        items.append(current)
    return items


def _parse_certifications(text: str) -> List[CertificationItem]:
    items: list = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _BULLET_RE.match(s)
        if not m:
            continue
        body = m.group(1).strip()
        if not body:
            continue
        # Best-effort split: "Name - Issuer - Date" or
        # "Name (Issuer, Date)" or free text.
        parts = [p.strip() for p in re.split(r"\s*[–\-]\s+|\s*,\s+", body) if p.strip()]
        ci = CertificationItem(
            name=parts[0] if parts else body,
            issuing_organization=parts[1] if len(parts) > 1 else "",
            date=parts[2] if len(parts) > 2 else "",
        )
        items.append(ci)
    return items


def _parse_achievements(text: str) -> List[AchievementItem]:
    items: list = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _BULLET_RE.match(s)
        body = m.group(1).strip() if m else s
        if body:
            items.append(AchievementItem(title=body[:200], description=body, date=""))
    return items


def _parse_links(text: str) -> List[LinkItem]:
    items: list = []
    for m in _URL_RE.finditer(text):
        url = m.group(0)
        if any(x in url for x in ("linkedin.com/in", "github.com")):
            continue
        items.append(LinkItem(label=url, url=url))
    # Deduplicate
    seen = set()
    out: list = []
    for it in items:
        if it.url in seen:
            continue
        seen.add(it.url)
        out.append(it)
    return out


def parse_resume_text(text: str) -> Tuple[Resume, list]:
    """Parse a raw resume ``text`` into a :class:`Resume`.

    Returns a tuple of ``(resume, warnings)`` where ``warnings`` is
    a list of short strings describing sections the parser could not
    detect. The resume is always returned; missing fields are
    simply empty.
    """
    warnings: list = []
    if not text or not text.strip():
        empty = Resume()
        warnings.append("empty document")
        return empty, warnings

    # Strip "Curriculum Vitae" or "Resume" header lines that some
    # templates prepend.
    cleaned_lines: list = []
    for line in text.splitlines():
        if re.match(r"^\s*(curriculum\s+vitae|resume|cv)\s*$", line, re.IGNORECASE):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)

    # Section split.
    section_bodies: dict = {}
    current_key: Optional[str] = None
    current_buf: list = []
    detected: list = []
    for line in cleaned.splitlines():
        matched_key = None
        for key, pattern in SECTION_PATTERNS:
            if pattern.match(line):
                matched_key = key
                break
        if matched_key is not None:
            if current_key is not None:
                section_bodies[current_key] = "\n".join(current_buf).strip()
            current_key = matched_key
            current_buf = []
            if matched_key not in detected:
                detected.append(matched_key)
        else:
            if current_key is None:
                # Everything before the first section heading is
                # treated as the personal / header block.
                current_key = "personal"
                if "personal" not in detected:
                    detected.append("personal")
            current_buf.append(line)
    if current_key is not None:
        section_bodies[current_key] = "\n".join(current_buf).strip()

    # Always include personal even if absent.
    if "personal" not in section_bodies:
        section_bodies["personal"] = cleaned[:300]

    resume = Resume()

    # Personal
    if "personal" in section_bodies:
        resume.personal = _parse_personal_header(section_bodies["personal"])

    # Summary
    if "summary" in section_bodies:
        summary_text = section_bodies["summary"].strip()
        if summary_text:
            resume.summary = summary_text

    # Experience
    if "experience" in section_bodies:
        resume.experience = _parse_experience(section_bodies["experience"])
    if not resume.experience and "personal" in section_bodies:
        # Some resumes put everything before "EXPERIENCE" under
        # the personal block; this is handled by the personal
        # parser already.

        pass

    # Education
    if "education" in section_bodies:
        resume.education = _parse_education(section_bodies["education"])

    # Skills
    if "skills" in section_bodies:
        groups = _parse_skills_block(section_bodies["skills"])
        if groups:
            resume.skills = groups

    # Projects
    if "projects" in section_bodies:
        resume.projects = _parse_projects(section_bodies["projects"])

    # Certifications
    if "certifications" in section_bodies:
        resume.certifications = _parse_certifications(section_bodies["certifications"])

    # Achievements
    if "achievements" in section_bodies:
        resume.achievements = _parse_achievements(section_bodies["achievements"])

    # Links
    if "links" in section_bodies:
        resume.links = _parse_links(section_bodies["links"])
    # Always pull URLs from the personal block as well.
    if "personal" in section_bodies:
        for link in _parse_links(section_bodies["personal"]):
            if not any(l.url == link.url for l in resume.links):
                resume.links.append(link)

    for key in ("experience", "education", "skills", "projects", "certifications", "achievements", "links"):
        if key not in section_bodies:
            warnings.append(f"no {key} section detected")

    return resume, warnings
