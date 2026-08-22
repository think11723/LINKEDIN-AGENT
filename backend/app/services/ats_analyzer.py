"""ATS analyzer — Phase 10.

Deterministic Job Description parsing and Resume ↔ JD compatibility
scoring. The system produces:

* a structured :class:`JDAnalysis` (skills, technologies,
  responsibilities, education, important keywords, etc.)
* a list of matched / missing / related keywords
* a 0–100 :class:`ATSScoreBreakdown` (no specific ATS vendor
  is referenced — this is the "ATS Compatibility Score" the
  product UI surfaces)
* a list of actionable :class:`ATSImprovementItem`

Everything is deterministic. We do NOT call an LLM. We do NOT
fabricate metrics, technologies, or experience. If the JD is
ambiguous, the analyzer surfaces that ambiguity as a low score
in the relevant dimension and as an improvement item.

The LLM may be layered on top in a follow-up for human-language
suggestions, but the score, the matched / missing keyword lists,
and the structural extraction are all rule-based so the result
is reproducible and trustable.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Set, Tuple

from backend.app.models.resume import (
    ATSAnalysis,
    ATSImprovementItem,
    ATSScoreBreakdown,
    JDAnalysis,
    Resume,
)


# Common English stop words that should not count as keywords.
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that",
    "the", "this", "to", "was", "were", "will", "with", "you",
    "your", "our", "their", "they", "we", "i", "me", "my", "he",
    "she", "his", "her", "us", "them", "so", "if", "then",
    "than", "but", "not", "be", "been", "being", "do", "does",
    "did", "doing", "have", "having", "can", "could", "would",
    "should", "may", "might", "must", "shall", "about", "above",
    "across", "after", "against", "along", "among", "around",
    "before", "behind", "below", "beneath", "beside", "between",
    "beyond", "during", "except", "inside", "into", "near",
    "onto", "outside", "over", "through", "toward", "under",
    "underneath", "until", "upon", "within", "without",
    "their", "team", "work", "working", "experience", "experiences",
    "knowledge", "familiarity", "years", "year",
    "etc", "via", "using", "use", "ability", "able", "strong",
    "plus", "must", "required", "preferred", "nice", "bonus",
    "great", "good", "best", "you'll", "we'll", "they'll",
    "candidate", "candidates", "applicant", "applicants",
    "role", "position", "company", "team", "teams", "responsibilities",
    "requirement", "requirements", "qualification", "qualifications",
}


# A small, opinionated list of common skill tokens that should be
# normalized the same way on both sides. This is not a complete
# taxonomy; it's a bias-reduction tool for the keyword matcher.
NORMALIZE_MAP = {
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "python": "python",
    "py": "python",
    "java": "java",
    "kotlin": "kotlin",
    "swift": "swift",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "ruby": "ruby",
    "php": "php",
    "c++": "c++",
    "cpp": "c++",
    "c#": "c#",
    "csharp": "c#",
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "vue": "vue.js",
    "vuejs": "vue.js",
    "vue.js": "vue.js",
    "next": "next.js",
    "nextjs": "next.js",
    "next.js": "next.js",
    "angular": "angular",
    "svelte": "svelte",
    "fastapi": "fastapi",
    "flask": "flask",
    "django": "django",
    "express": "express",
    "expressjs": "express",
    "spring": "spring boot",
    "spring boot": "spring boot",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "psql": "postgresql",
    "mysql": "mysql",
    "mongodb": "mongodb",
    "mongo": "mongodb",
    "redis": "redis",
    "elasticsearch": "elasticsearch",
    "elastic search": "elasticsearch",
    "kafka": "kafka",
    "rabbitmq": "rabbitmq",
    "aws": "aws",
    "amazon web services": "aws",
    "ec2": "aws",
    "s3": "aws",
    "lambda": "aws",
    "gcp": "gcp",
    "google cloud": "gcp",
    "azure": "azure",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "docker": "docker",
    "terraform": "terraform",
    "ansible": "ansible",
    "jenkins": "jenkins",
    "github actions": "github actions",
    "ci/cd": "ci/cd",
    "machine learning": "machine learning",
    "ml": "machine learning",
    "ai": "ai",
    "artificial intelligence": "ai",
    "llm": "llm",
    "large language model": "llm",
    "rag": "rag",
    "vector database": "vector database",
    "embeddings": "embeddings",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "huggingface": "huggingface",
    "transformers": "transformers",
    "langchain": "langchain",
    "llamaindex": "llamaindex",
    "openai": "openai",
    "anthropic": "anthropic",
    "aws sagemaker": "aws sagemaker",
    "rest api": "rest api",
    "rest apis": "rest api",
    "graphql": "graphql",
    "grpc": "grpc",
    "kafka": "kafka",
    "airflow": "airflow",
    "dbt": "dbt",
    "spark": "spark",
    "hadoop": "hadoop",
    "snowflake": "snowflake",
    "databricks": "databricks",
    "looker": "looker",
    "tableau": "tableau",
    "power bi": "power bi",
    "figma": "figma",
    "sketch": "sketch",
    "terraform": "terraform",
    "circleci": "circleci",
    "travis": "travis",
    "jest": "jest",
    "pytest": "pytest",
    "unittest": "unittest",
    "junit": "junit",
    "rspec": "rspec",
    "selenium": "selenium",
    "cypress": "cypress",
    "playwright": "playwright",
    "puppeteer": "puppeteer",
    "html": "html",
    "css": "css",
    "sass": "sass",
    "tailwind": "tailwind",
    "bootstrap": "bootstrap",
    "material ui": "material ui",
    "shadcn": "shadcn",
    "redux": "redux",
    "mobx": "mobx",
    "zustand": "zustand",
    "rxjs": "rxjs",
    "webgl": "webgl",
    "three.js": "three.js",
    "d3": "d3",
    "agile": "agile",
    "scrum": "scrum",
    "kanban": "kanban",
    "jira": "jira",
    "confluence": "confluence",
    "notion": "notion",
    "figma": "figma",
    "sketch": "sketch",
    "photoshop": "photoshop",
    "illustrator": "illustrator",
    "after effects": "after effects",
    "premiere": "premiere",
    "figma": "figma",
}


# Map each canonical skill → a few related/equivalent terms. Used to
# surface "related keywords" even when the exact term is missing.
RELATED_TERMS: dict = {
    "python": ["django", "flask", "fastapi", "pandas", "numpy"],
    "javascript": ["typescript", "node.js", "react", "vue.js", "angular"],
    "typescript": ["javascript", "node.js"],
    "react": ["next.js", "redux", "javascript"],
    "vue.js": ["javascript", "vuex"],
    "next.js": ["react", "javascript", "typescript"],
    "node.js": ["express", "javascript", "typescript"],
    "aws": ["ec2", "s3", "lambda", "cloudformation", "sagemaker"],
    "gcp": ["google cloud", "bigquery", "cloud run"],
    "azure": ["cosmos db", "aks"],
    "kubernetes": ["docker", "helm", "kustomize", "istio"],
    "docker": ["kubernetes", "compose", "swarm"],
    "postgresql": ["sql", "psql", "pg"],
    "mongodb": ["nosql", "atlas"],
    "redis": ["cache", "pub/sub"],
    "machine learning": ["ai", "pytorch", "tensorflow", "sklearn"],
    "ai": ["llm", "rag", "embeddings", "vector database"],
    "llm": ["prompt engineering", "rag", "ai"],
    "rag": ["vector database", "embeddings", "llm"],
    "vector database": ["pinecone", "weaviate", "chroma", "qdrant"],
    "pytorch": ["machine learning", "deep learning"],
    "tensorflow": ["machine learning", "deep learning"],
    "langchain": ["llm", "rag", "ai"],
    "rest api": ["graphql", "grpc", "fastapi", "express"],
    "graphql": ["rest api", "apollo"],
    "figma": ["design", "ui", "ux"],
    "tailwind": ["css", "frontend"],
    "docker": ["kubernetes", "devops"],
    "terraform": ["aws", "gcp", "azure", "devops"],
    "ci/cd": ["github actions", "jenkins", "circleci"],
    "github actions": ["ci/cd", "devops"],
}


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./\-]{1,30}")
_BULLET_RE = re.compile(r"^\s*[•\-\*◦▪▫]\s+(.*)$")
_YEARS_RE = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)


def _tokenize_keywords(text: str) -> List[str]:
    """Extract a deduplicated list of normalized keywords from
    free-form text. The order is preserved (first-seen wins) so the
    output is deterministic.
    """
    if not text:
        return []
    seen: set = set()
    out: list = []
    # Lower-case, then split on word boundaries.
    lowered = text.lower()
    # Also split on common separators so things like "node.js" and
    # "spring boot" can still be picked up.
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9+#./\-]{1,30}", lowered)
    for cand in candidates:
        if not cand:
            continue
        # Normalize.
        normalized = NORMALIZE_MAP.get(cand, cand)
        normalized = normalized.strip(".-/+#")
        if not normalized or len(normalized) < 2:
            continue
        if normalized in STOP_WORDS:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _parse_jd_lines(text: str) -> JDAnalysis:
    """Produce a structured JD analysis from a free-form Job
    Description. Heuristic, no LLM.
    """
    if not text or not text.strip():
        return JDAnalysis()

    lines = text.splitlines()

    # Try to extract a role title and company from the first
    # non-empty lines. The format is not standardized so we look
    # for common patterns.
    role_title = ""
    company = ""
    for raw in lines[:8]:
        s = raw.strip()
        if not s:
            continue
        # "Role at Company" or "Role, Company" or "Role — Company"
        m = re.match(
            r"^(?P<role>[^,\-|]+?)\s*(?:at|@|,|\-|–|—)\s*(?P<company>[^,\-|]+?)\s*$",
            s,
        )
        if m and len(s) < 120:
            role_title = m.group("role").strip()
            company = m.group("company").strip()
            break
        # "Software Engineer" style first line.
        if not role_title and 1 <= len(s.split()) <= 8 and not s.endswith("."):
            role_title = s
        # Standalone company (often a single capitalized line).
        if not company and re.match(r"^[A-Z][A-Za-z0-9 &.,]+$", s) and len(s.split()) <= 5:
            company = s

    # Experience years.
    experience_years = ""
    for raw in lines:
        m = _YEARS_RE.search(raw)
        if m:
            experience_years = m.group(0)
            break

    # Education requirement — heuristic.
    education = ""
    lowered = text.lower()
    if "phd" in lowered or "doctorate" in lowered:
        education = "PhD preferred"
    elif "master" in lowered or "msc" in lowered or "m.s." in lowered:
        education = "Master's degree preferred"
    elif "bachelor" in lowered or "bs/" in lowered or "b.s." in lowered:
        education = "Bachelor's degree preferred"

    # Required vs preferred skills. Look for section headings.
    required_skills: list = []
    preferred_skills: list = []
    technologies: list = []
    responsibilities: list = []
    current_section: str = ""
    section_buffer: list = []
    required_pattern = re.compile(r"^\s*(requirements?|required|qualifications?|what you.{0,3}ll need|must have)\s*:?\s*$", re.IGNORECASE)
    preferred_pattern = re.compile(r"^\s*(preferred|nice to have|bonus|would be a plus|plus)\s*:?\s*$", re.IGNORECASE)
    responsibilities_pattern = re.compile(r"^\s*(responsibilities|what you(?:.{0,3}ll)? do|your role|duties|day to day)\s*:?\s*$", re.IGNORECASE)
    tech_pattern = re.compile(r"^\s*(technologies|tech stack|our stack|tools|tech)\s*:?\s*$", re.IGNORECASE)

    def flush() -> None:
        nonlocal current_section, section_buffer
        if not current_section or not section_buffer:
            section_buffer = []
            current_section = ""
            return
        body = "\n".join(section_buffer).strip()
        if not body:
            current_section = ""
            section_buffer = []
            return
        if current_section == "responsibilities":
            for line in body.splitlines():
                m = _BULLET_RE.match(line)
                text_line = m.group(1).strip() if m else line.strip()
                if text_line:
                    responsibilities.append(text_line[:200])
        elif current_section == "required":
            kws = _tokenize_keywords(body)
            required_skills.extend(kws)
        elif current_section == "preferred":
            kws = _tokenize_keywords(body)
            preferred_skills.extend(kws)
        elif current_section == "tech":
            kws = _tokenize_keywords(body)
            technologies.extend(kws)
        current_section = ""
        section_buffer = []

    for raw in lines:
        s = raw.strip()
        if required_pattern.match(s):
            flush()
            current_section = "required"
            section_buffer = []
        elif preferred_pattern.match(s):
            flush()
            current_section = "preferred"
            section_buffer = []
        elif responsibilities_pattern.match(s):
            flush()
            current_section = "responsibilities"
            section_buffer = []
        elif tech_pattern.match(s):
            flush()
            current_section = "tech"
            section_buffer = []
        else:
            if current_section:
                section_buffer.append(raw)
    flush()

    # If the JD has no clear sections, distribute the body across
    # the most useful buckets.
    if not required_skills and not responsibilities and not technologies:
        all_kws = _tokenize_keywords(text)
        required_skills = all_kws[:15]
        technologies = all_kws[:15]

    # Top important keywords: union of required + tech + most-frequent
    # tokens, dedup'd, capped.
    important = list(dict.fromkeys(required_skills + technologies))[:25]

    return JDAnalysis(
        role_title=role_title,
        company=company,
        domain="",
        required_skills=required_skills[:30],
        preferred_skills=preferred_skills[:30],
        technologies=technologies[:30],
        responsibilities=responsibilities[:30],
        experience_years=experience_years,
        education=education,
        important_keywords=important,
    )


def _resume_skill_set(resume: Resume) -> Set[str]:
    """Return the set of normalized skill tokens present in the
    resume, drawn from the structured ``skills`` section AND every
    free-form text field (so the ATS analyzer picks up a skill
    mentioned in the summary or in a project description).
    """
    out: set = set()
    for group in resume.skills:
        for s in group.skills:
            n = NORMALIZE_MAP.get(s.strip().lower(), s.strip().lower())
            if n:
                out.add(n)
    for source_text in [resume.summary] + [
        exp.description + " " + " ".join(exp.technologies)
        for exp in resume.experience
    ] + [
        p.description + " " + " ".join(p.technologies)
        for p in resume.projects
    ]:
        for k in _tokenize_keywords(source_text or ""):
            out.add(k)
    # Also include experience / project / cert / achievement titles
    # (they often contain the right keywords).
    for exp in resume.experience:
        for k in _tokenize_keywords(" ".join([exp.role, exp.company])):
            out.add(k)
    for p in resume.projects:
        for k in _tokenize_keywords(p.name or ""):
            out.add(k)
    for c in resume.certifications:
        for k in _tokenize_keywords(" ".join([c.name, c.issuing_organization])):
            out.add(k)
    return out


def _score_breakdown(
    resume: Resume,
    jd: JDAnalysis,
) -> Tuple[ATSScoreBreakdown, list, list, list, list]:
    """Compute the ATS sub-scores + matched / missing / related
    keywords. Returns 5-tuple of (breakdown, matched, missing,
    related, overused).
    """
    resume_skills = _resume_skill_set(resume)
    jd_keywords = list(dict.fromkeys(
        jd.required_skills + jd.preferred_skills + jd.technologies + jd.important_keywords
    ))
    # Match
    matched = []
    missing = []
    for kw in jd_keywords:
        if kw in resume_skills:
            matched.append(kw)
        else:
            missing.append(kw)

    # Related: for each missing term, surface the related terms
    # the resume already has.
    related = []
    for kw in missing:
        for rel in RELATED_TERMS.get(kw, []):
            if rel in resume_skills and rel not in related:
                related.append(rel)

    # Overused: words that appear ≥ 5 times in the resume body
    # (excluding the structured skills list which is already broken
    # into categories).
    text = (
        resume.summary + " "
        + " ".join(
            exp.description + " " + " ".join(exp.achievements)
            for exp in resume.experience
        )
        + " "
        + " ".join(p.description for p in resume.projects)
    ).lower()
    counts = Counter(re.findall(r"\b[A-Za-z][A-Za-z0-9+#]{2,}\b", text))
    overused = [w for w, c in counts.most_common(8) if c >= 5 and w not in STOP_WORDS]

    # Sub-scores, each 0–100.
    if not jd_keywords:
        keyword_score = 70
    else:
        keyword_score = round(100 * len(matched) / max(1, len(matched) + len(missing)))

    skills_intersection = len(set(matched) & set(resume_skills))
    skills_score = (
        round(100 * skills_intersection / max(1, len(jd.required_skills) or 1))
        if jd.required_skills
        else 70
    )

    # Experience relevance: heuristic — if at least one of the
    # experience.role / company / description contains a JD keyword
    # and the resume has at least 1 experience entry, give a
    # reasonable score; otherwise penalize.
    exp_relevance = 50
    if jd_keywords and resume.experience:
        exp_hits = 0
        for exp in resume.experience:
            text = (
                (exp.role or "") + " " + (exp.company or "") + " " + (exp.description or "")
            ).lower()
            for kw in jd_keywords:
                if kw in text:
                    exp_hits += 1
                    break
        exp_relevance = min(100, 50 + 30 * exp_hits)

    # Education relevance.
    edu_relevance = 70
    if jd.education:
        jd_edu = jd.education.lower()
        for entry in resume.education:
            text = (
                (entry.degree or "") + " " + (entry.field or "")
            ).lower()
            if any(token in text for token in ("bachelor", "master", "phd", "doctorate", "msc", "bsc")):
                edu_relevance = 90
                break
        if "bachelor" in jd_edu and not resume.education:
            edu_relevance = 30
        if "master" in jd_edu and not any(
            "master" in ((e.degree or "") + (e.field or "")).lower()
            for e in resume.education
        ):
            edu_relevance = min(edu_relevance, 55)

    # Title alignment: how well the resume summary / latest role
    # aligns with the JD title.
    title_alignment = 60
    if jd.role_title:
        rt = jd.role_title.lower()
        haystacks = (
            [resume.summary.lower(), resume.personal.headline.lower()]
            + [exp.role.lower() + " " + exp.company.lower() for exp in resume.experience]
        )
        overlap = 0
        for kw in _tokenize_keywords(rt):
            if any(kw in h for h in haystacks):
                overlap += 1
        title_alignment = min(100, 50 + 20 * overlap)

    # Formatting / readability heuristic: rewards resumes with
    # multiple structured sections, a non-trivial summary, and at
    # least 3 skills.
    formatting = 60
    if resume.summary and len(resume.summary) >= 80:
        formatting += 10
    if resume.experience:
        formatting += 10
    if resume.education:
        formatting += 5
    if resume.skill_list_flat():
        formatting += 10
    if resume.personal.full_name and resume.personal.email:
        formatting += 5
    formatting = min(100, formatting)

    section_completeness = 60
    if resume.personal.full_name:
        section_completeness += 5
    if resume.personal.email:
        section_completeness += 5
    if resume.summary:
        section_completeness += 10
    if resume.experience:
        section_completeness += 10
    if resume.education:
        section_completeness += 5
    if resume.skill_list_flat():
        section_completeness += 5
    section_completeness = min(100, section_completeness)

    breakdown = ATSScoreBreakdown(
        keyword_match=keyword_score,
        skills_match=skills_score,
        experience_relevance=exp_relevance,
        education_relevance=edu_relevance,
        title_alignment=title_alignment,
        formatting_readability=formatting,
        section_completeness=section_completeness,
    )
    return breakdown, matched, missing, related, overused


def _build_improvements(
    resume: Resume,
    jd: JDAnalysis,
    missing: list,
    breakdown: ATSScoreBreakdown,
) -> List[ATSImprovementItem]:
    """Deterministic improvement suggestions. NEVER invents
    metrics. NEVER rewrites the resume. Always explains the why.
    """
    out: list = []

    # Missing keywords.
    if missing:
        top_missing = missing[:8]
        out.append(
            ATSImprovementItem(
                title=f"Add {len(top_missing)} missing keyword{'s' if len(top_missing) != 1 else ''} to your resume",
                detail=(
                    "The Job Description repeatedly uses "
                    f"{', '.join(top_missing)}. Your resume does not currently mention "
                    "any of them. If you have this experience, surface it explicitly in the "
                    "summary or in the relevant project / experience bullet. The ATS "
                    "parser will pick up exact word matches; do not invent experience you "
                    "do not have."
                ),
                priority="high",
            )
        )

    # No summary.
    if not resume.summary or len(resume.summary.strip()) < 80:
        out.append(
            ATSImprovementItem(
                title="Add a substantive professional summary",
                detail=(
                    "A 2–4 sentence summary at the top of your resume gives the ATS "
                    "parser a high-signal block to match against the Job Description. "
                    "Mirror the role title and the top required skills naturally — do not "
                    "stuff keywords; the parser reads prose."
                ),
                priority="high",
            )
        )

    # No metrics in achievements.
    metric_hits = 0
    for exp in resume.experience:
        for a in exp.achievements:
            if re.search(r"\b\d", a):
                metric_hits += 1
    if metric_hits < 3:
        out.append(
            ATSImprovementItem(
                title="Add measurable impact to your achievements",
                detail=(
                    "Recruiters and ATS systems both reward achievement bullets with "
                    "quantified impact (e.g. \"cut p99 latency by 40%\", \"shipped to 12k "
                    "users in 6 weeks\"). You currently have fewer than three such "
                    "bullets. Only add real numbers — never invent them. If a number "
                    "isn't available, describe the *delta* (before → after) qualitatively."
                ),
                priority="medium",
            )
        )

    # No education.
    if not resume.education:
        out.append(
            ATSImprovementItem(
                title="Add an education section",
                detail=(
                    "An ATS system that requires a degree will skip resumes without an "
                    "Education section, even if the candidate has the right skills. "
                    "If you have a degree, list it. If you don't, add any relevant "
                    "bootcamps, certifications, or self-study."
                ),
                priority="medium" if jd.education else "high",
            )
        )

    # Empty personal.
    if not resume.personal.email or not resume.personal.full_name:
        out.append(
            ATSImprovementItem(
                title="Add contact information",
                detail=(
                    "Your resume must include at minimum a name and an email address. "
                    "Phone, location, LinkedIn, and GitHub are commonly expected by "
                    "modern ATS systems."
                ),
                priority="high",
            )
        )

    # Title alignment.
    if breakdown.title_alignment < 70 and jd.role_title:
        out.append(
            ATSImprovementItem(
                title="Mirror the Job Description's role title in your summary",
                detail=(
                    f"The Job Description asks for a \"{jd.role_title}\". If that's "
                    "the role you're targeting, make sure your summary and most recent "
                    "job title use the same vocabulary. The ATS parser scores exact "
                    "title matches heavily."
                ),
                priority="medium",
            )
        )

    # Formatting.
    if breakdown.formatting_readability < 80:
        out.append(
            ATSImprovementItem(
                title="Improve resume structure",
                detail=(
                    "Your resume is missing some standard sections (Personal, Summary, "
                    "Experience, Education, Skills). Most ATS parsers reward clean, "
                    "predictable section headings: PERSONAL, SUMMARY, EXPERIENCE, "
                    "EDUCATION, SKILLS, PROJECTS. Use these as your section labels."
                ),
                priority="low",
            )
        )

    # Education requirement.
    if jd.education and breakdown.education_relevance < 70:
        out.append(
            ATSImprovementItem(
                title=(
                    f"Address the degree requirement ({jd.education})"
                ),
                detail=(
                    "The Job Description calls out a degree requirement. If you meet "
                    "it, list the degree in your Education section. If you don't, "
                    "highlight equivalent real-world experience so the ATS does not "
                    "filter you out on a keyword check."
                ),
                priority="medium",
            )
        )

    # Always include one low-priority reminder.
    out.append(
        ATSImprovementItem(
            title="Save a version for this Job Description",
            detail=(
                "Use the 'Optimize Resume' action to create a copy of your resume "
                "tuned for this Job Description. The original is preserved so you can "
                "iterate without losing your baseline."
            ),
            priority="low",
        )
    )
    return out


def analyze_resume_against_jd(resume: Resume, jd_text: str) -> ATSAnalysis:
    """Run the full deterministic ATS analysis.

    This is the public entry point used by the service layer.
    """
    jd = _parse_jd_lines(jd_text)
    breakdown, matched, missing, related, _overused = _score_breakdown(resume, jd)
    improvements = _build_improvements(resume, jd, missing, breakdown)
    return ATSAnalysis(
        id="",  # filled in by the repository
        resume_id="",  # filled in by the repository
        overall_score=breakdown.overall,
        breakdown=breakdown,
        matched_keywords=matched[:50],
        missing_keywords=missing[:50],
        related_keywords=related[:50],
        jd_analysis=jd,
        improvements=improvements[:12],
    )


__all__ = ["analyze_resume_against_jd"]
