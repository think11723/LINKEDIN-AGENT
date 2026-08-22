"""Resume → LinkedIn bridge — Phase 10.

Builds a structured source context from a section of the user's
resume, then hands it to the existing :class:`WorkflowService`
(Phase 5 source-aware Writer + Reviewer). The resulting post is
stored as a normal :class:`Draft` and is available through the
existing approval / publishing workflow.

The Writer is told the source is a "Resume" section so the
narrative angle stays relevant (a project launch, a career
achievement, a learning journey, etc.). The framing hint from
the request is forwarded as ``USER'S DESIRED ANGLE``.

CRITICAL INVARIANTS:

* The Writer is NEVER given the raw resume JSON. The bridge
  builds a human-readable summary the Writer can quote.
* The Writer is NEVER told to invent metrics. If the resume
  bullet says "Built X", the post says "Built X" — not "Built X,
  saving 40%" if no such number exists.
* The bridge passes the section as ``source_type="resume_section"``
  so the Draft Viewer attribution card and the email render the
  correct source label.
"""

from __future__ import annotations

from typing import Optional

from backend.app.models.resume import (
    AchievementItem,
    CertificationItem,
    ExperienceItem,
    ProjectItem,
    Resume,
)


# Allowed post types — these are the values the API accepts and the
# labels the frontend renders. Mirrors the spec's "Post type"
# options.
ALLOWED_POST_TYPES = {
    "project_launch",
    "career_achievement",
    "learning_journey",
    "job_experience",
    "certification",
    "technical_deep_dive",
    "career_milestone",
}
POST_TYPE_LABEL = {
    "project_launch": "Project launch",
    "career_achievement": "Career achievement",
    "learning_journey": "Learning journey",
    "job_experience": "Job experience",
    "certification": "Certification",
    "technical_deep_dive": "Technical deep dive",
    "career_milestone": "Career milestone",
}

ALLOWED_TONES = {
    "professional",
    "storytelling",
    "educational",
    "founder",
    "opinion",
}


def _section_human_summary(
    *,
    post_type: str,
    tone: str,
    resume: Resume,
    section: str,
    section_id: str,
) -> Optional[dict]:
    """Return ``{"title": ..., "summary": ..., "key_facts": [...]}``
    describing the chosen section of the resume. Returns ``None``
    when the requested section is empty.
    """
    personal = resume.personal
    headline = personal.headline or personal.full_name

    if section == "summary":
        if not resume.summary.strip():
            return None
        return {
            "title": f"Professional summary — {headline}",
            "summary": resume.summary.strip(),
            "key_facts": _summary_facts(resume, post_type),
        }

    if section == "experience":
        items = list(resume.experience)
        if section_id:
            for it in items:
                if (it.role or "").lower() == section_id.lower() or (
                    it.company or ""
                ).lower() == section_id.lower():
                    return _experience_to_facts(it, resume, post_type)
        if not items:
            return None
        # Default: most recent experience.
        return _experience_to_facts(items[0], resume, post_type)

    if section == "projects":
        items = list(resume.projects)
        if section_id:
            for p in items:
                if (p.name or "").lower() == section_id.lower():
                    return _project_to_facts(p, resume, post_type)
        if not items:
            return None
        return _project_to_facts(items[0], resume, post_type)

    if section == "certifications":
        items = list(resume.certifications)
        if section_id:
            for c in items:
                if (c.name or "").lower() == section_id.lower():
                    return _certification_to_facts(c, resume, post_type)
        if not items:
            return None
        return _certification_to_facts(items[0], resume, post_type)

    if section == "achievements":
        items = list(resume.achievements)
        if section_id:
            for a in items:
                if (a.title or "").lower() == section_id.lower():
                    return _achievement_to_facts(a, resume, post_type)
        if not items:
            return None
        return _achievement_to_facts(items[0], resume, post_type)

    return None


def _summary_facts(resume: Resume, post_type: str) -> list:
    facts: list = []
    if resume.personal.headline:
        facts.append(f"Current headline: {resume.personal.headline}")
    flat = resume.skill_list_flat()
    if flat:
        facts.append("Top skills: " + ", ".join(flat[:8]))
    if resume.experience:
        first = resume.experience[0]
        facts.append(
            f"Most recent role: {first.role or 'unknown role'} at {first.company or 'a previous employer'}"
        )
    return facts[:6]


def _experience_to_facts(item: ExperienceItem, resume: Resume, post_type: str) -> dict:
    parts: list = []
    if item.role or item.company:
        parts.append(
            f"{item.role or 'A role'} at {item.company or 'a previous employer'}"
        )
    if item.start_date or item.end_date or item.currently_working:
        span = " – ".join(
            [d for d in (item.start_date, item.end_date or ("Present" if item.currently_working else "")) if d]
        )
        if span:
            parts.append(f"Duration: {span}")
    if item.description:
        parts.append(item.description)
    for a in item.achievements[:5]:
        if a:
            parts.append(a)
    summary = ". ".join(parts)
    title_bits = [b for b in (item.role, item.company) if b]
    title = " · ".join(title_bits) or "Experience highlight"
    key_facts = [
        f"Role: {item.role or 'unknown'}",
        f"Company: {item.company or 'unknown'}",
    ]
    if item.technologies:
        key_facts.append("Tech: " + ", ".join(item.technologies[:6]))
    if item.achievements:
        key_facts.append("Achievement highlights: " + " | ".join(item.achievements[:3]))
    return {"title": title, "summary": summary, "key_facts": key_facts[:6]}


def _project_to_facts(item: ProjectItem, resume: Resume, post_type: str) -> dict:
    parts: list = []
    if item.description:
        parts.append(item.description)
    for a in item.achievements[:5]:
        if a:
            parts.append(a)
    summary = ". ".join(parts)
    title = item.name or "Project highlight"
    key_facts = [f"Project: {item.name or 'unknown'}"]
    if item.technologies:
        key_facts.append("Tech: " + ", ".join(item.technologies[:6]))
    if item.achievements:
        key_facts.append("Achievements: " + " | ".join(item.achievements[:3]))
    return {"title": title, "summary": summary, "key_facts": key_facts[:6]}


def _certification_to_facts(item: CertificationItem, resume: Resume, post_type: str) -> dict:
    title = item.name or "Certification"
    parts: list = []
    if item.issuing_organization:
        parts.append(f"Issued by {item.issuing_organization}.")
    if item.date:
        parts.append(f"Date: {item.date}.")
    summary = " ".join(parts) or "Certification earned."
    key_facts = [f"Certification: {item.name or 'unknown'}"]
    if item.issuing_organization:
        key_facts.append(f"Issuer: {item.issuing_organization}")
    return {"title": title, "summary": summary, "key_facts": key_facts[:4]}


def _achievement_to_facts(item: AchievementItem, resume: Resume, post_type: str) -> dict:
    title = item.title or "Achievement"
    summary = item.description or item.title or "Achievement."
    key_facts = [f"Achievement: {item.title or 'unnamed'}"]
    if item.date:
        key_facts.append(f"Date: {item.date}")
    if item.description and item.description != item.title:
        key_facts.append(item.description[:200])
    return {"title": title, "summary": summary, "key_facts": key_facts[:4]}


def build_resume_source_context(
    *,
    resume: Resume,
    post_type: str,
    tone: str,
    section: str = "",
    section_id: str = "",
) -> dict:
    """Return the structured source dict consumed by
    :class:`WriterAgent.write` and :class:`ReviewerAgent.review` in
    source-aware mode.

    Raises :class:`ValueError` if the resume has no usable content
    in the requested section.
    """
    post_type = (post_type or "project_launch").strip().lower()
    tone = (tone or "professional").strip().lower()
    if post_type not in ALLOWED_POST_TYPES:
        raise ValueError(f"unsupported post type: {post_type!r}")
    if tone not in ALLOWED_TONES:
        raise ValueError(f"unsupported tone: {tone!r}")

    section = (section or "").strip().lower()
    if not section:
        # Pick the most likely default: if the resume has a project
        # use that, otherwise a recent role, otherwise the summary.
        if resume.projects:
            section = "projects"
        elif resume.experience:
            section = "experience"
        else:
            section = "summary"

    facts = _section_human_summary(
        post_type=post_type,
        tone=tone,
        resume=resume,
        section=section,
        section_id=section_id,
    )
    if facts is None:
        raise ValueError(
            f"no content available in resume section {section!r}"
        )

    # The source dict matches the Phase 5 source-aware contract.
    canonical_url = ""
    if resume.personal.linkedin_url:
        canonical_url = resume.personal.linkedin_url
    elif resume.personal.github_url:
        canonical_url = resume.personal.github_url

    return {
        "source_type": "resume_section",
        "source_title": facts["title"],
        "source_url": canonical_url,
        "source_summary": facts["summary"],
        "key_points": list(facts["key_facts"]),
        "technical_details": [],
        "author": resume.personal.full_name or "",
        "published_at": "",
        "site_name": "",
        "framing_hint": (
            f"Post type: {post_type}. Tone: {tone}. "
            f"Focus only on the section the candidate selected. "
            "Do not invent metrics, technologies, or claims that "
            "are not explicitly present in the source below."
        ),
        "source_metadata": {
            "post_type": post_type,
            "tone": tone,
            "section": section,
            "section_id": section_id or "",
        },
    }


__all__ = [
    "ALLOWED_POST_TYPES",
    "ALLOWED_TONES",
    "POST_TYPE_LABEL",
    "build_resume_source_context",
]
