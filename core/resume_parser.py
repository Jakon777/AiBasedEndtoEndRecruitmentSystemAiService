# import pdfplumber
# import re
# # import spacy

# # # nlp = spacy.load("en_core_web_sm")
# # nlp = None  # Global variable

# # def get_nlp():
# #     global nlp
# #     if nlp is None:
# #         nlp = spacy.load("en_core_web_sm")
# #     return nlp

# COMMON_SKILLS = [
#     "python","java","c++","react","node","mongodb",
#     "mysql","docker","kubernetes","aws","html",
#     "css","javascript","fastapi","spring","django"
# ]

# def parse_resume(file_path):
#     text = ""
#     with pdfplumber.open(file_path) as pdf:
#         for page in pdf.pages:
#             text += page.extract_text() or ""

#     email = re.search(r'\S+@\S+', text)
#     phone = re.search(r'\+?\d[\d\s\-]{8,15}', text)

#     name = ""
#     # doc = nlp(text)
#     # 🔽 THIS is where it goes
#     doc = get_nlp()(text)


#     for ent in doc.ents:
#         if ent.label_ == "PERSON":
#             name = ent.text
#             break

#     skills = [s for s in COMMON_SKILLS if s in text.lower()]

#     return {
#         "name": name,
#         "email": email.group(0) if email else "",
#         "phone": phone.group(0) if phone else "",
#         "skills": list(set(skills)),
#         "raw_text": text
#     }






# import spacy
# import pdfplumber

# # Load spacy model once
# nlp = spacy.load("en_core_web_sm")


# def get_nlp():
#     return nlp


# def extract_text_from_pdf(path: str):
#     text = ""

#     with pdfplumber.open(path) as pdf:
#         for page in pdf.pages:
#             text += page.extract_text() or ""

#     return text


# def parse_resume(path: str):
#     text = extract_text_from_pdf(path)

#     doc = get_nlp()(text)

#     skills = []
#     emails = []
#     names = []

#     for ent in doc.ents:
#         if ent.label_ == "PERSON":
#             names.append(ent.text)
#         if ent.label_ == "ORG":
#             skills.append(ent.text)

#     for token in doc:
#         if "@" in token.text:
#             emails.append(token.text)

#     return {
#         "name": list(set(names)),
#         "skills": list(set(skills)),
#         "email": list(set(emails)),
#         "text": text[:1000]
#     }





# import spacy
# import pdfplumber

# nlp = spacy.load("en_core_web_sm")

# def get_nlp():
#     return nlp

# def extract_text_from_pdf(path):
#     text = ""

#     with pdfplumber.open(path) as pdf:
#         for page in pdf.pages:
#             page_text = page.extract_text()
#             if page_text:
#                 text += page_text

#     return text

# def parse_resume(path):
#     text = extract_text_from_pdf(path)

#     if not text:
#         return {"error": "No text extracted from resume"}

#     doc = get_nlp()(text)

#     names = []
#     emails = []

#     for ent in doc.ents:
#         if ent.label_ == "PERSON":
#             names.append(ent.text)

#     for token in doc:
#         if "@" in token.text:
#             emails.append(token.text)

#     return {
#         "name": list(set(names)),
#         "email": list(set(emails)),
#         "text": text[:1000]
#     }



import pdfplumber
import re


def extract_text_from_pdf(path: str, max_chars: int = 12000) -> str:
    """
    Extract text from a PDF while capping total characters.

    This prevents large resumes from pushing the app over tight memory limits
    (e.g. Render 512MB) during embedding.
    """
    chunks: list[str] = []
    total = 0

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            if total >= max_chars:
                break

            page_text = page.extract_text() or ""
            if not page_text:
                continue

            remaining = max_chars - total
            if remaining <= 0:
                break

            # Bound per-page contribution to avoid building huge strings.
            if len(page_text) > remaining:
                page_text = page_text[:remaining]

            chunks.append(page_text + "\n")
            total += len(page_text)

    return "".join(chunks)


def extract_email(text):
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    emails = re.findall(email_pattern, text)
    return list(dict.fromkeys(emails))


# Section titles often appear in ALL CAPS in PDFs and were mistaken for names.
_SECTION_HEADERS = {
    "education", "experience", "work experience", "employment history",
    "employment", "professional experience", "projects", "project",
    "skills", "technical skills", "core competencies", "competencies",
    "summary", "professional summary", "profile", "objective",
    "career objective", "contact", "personal details", "about",
    "about me", "certifications", "achievements", "awards",
    "internship", "internships", "training", "courses",
    "references", "languages", "hobbies", "declaration",
    "academic projects", "personal projects",
}


def _normalize_header_key(s: str) -> str:
    return re.sub(r"[^\w\s]", "", s.strip().lower())


def _looks_like_contact_line(line: str) -> bool:
    low = line.lower()
    if "@" in line or "http://" in low or "https://" in low or "www." in low:
        return True
    if re.search(r"\+?\d[\d\s\-|/]{7,}", line):
        return True
    return False


def _is_section_header(line: str) -> bool:
    raw = line.strip()
    if not raw:
        return True
    key = _normalize_header_key(raw)
    if key in _SECTION_HEADERS:
        return True
    # Single ALL-CAPS token that matches a known section word
    parts = raw.split()
    if len(parts) == 1 and raw.isupper():
        if raw.lower() in _SECTION_HEADERS:
            return True
    return False


def _word_is_name_token(w: str) -> bool:
    core = w.strip(".,|-")
    if not core:
        return False
    return core.replace("-", "").isalpha()


def _line_looks_like_person_name(line: str) -> bool:
    words = line.split()
    if not (2 <= len(words) <= 5):
        return False
    if any(ch.isdigit() for ch in line):
        return False
    if not all(_word_is_name_token(w) for w in words):
        return False
    # Title Case or reasonable mixed case (e.g. McDonald); ALL-CAPS also OK
    title_like = sum(1 for w in words if w[:1].isupper())
    return title_like >= max(1, len(words) - 1)


def extract_name(text):
    lines = [ln.strip() for ln in text.splitlines()]

    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return ""

    head = lines[:30]

    for line in head:
        if not line or _looks_like_contact_line(line):
            continue
        if _is_section_header(line):
            continue
        if _line_looks_like_person_name(line):
            return line

    for line in head:
        if not line or _looks_like_contact_line(line):
            continue
        if _is_section_header(line):
            continue
        words = line.split()
        if 1 <= len(words) <= 4 and not any(ch.isdigit() for ch in line):
            if all(_word_is_name_token(w) for w in words):
                return line

    return lines[0] if lines else ""


def extract_phone(text):
    m = re.search(
        r"(?:\+91[\s\-]?)?(?:\+?\d{1,3}[\s\-]?)?\d{5}[\s\-]?\d{5}|\+\d{10,15}",
        text,
    )
    return m.group(0).strip() if m else ""


def extract_skills(text):

    skills_db = [
        "python", "java", "machine learning", "deep learning",
        "data science", "spring boot", "springboot", "spring",
        "javascript", "html", "css", "react", "node", "mongodb",
        "sql", "c++", "c", "oop", "data structures",
        "artificial intelligence", "computer vision", "fastapi", "django",
    ]

    text_lower = text.lower()

    found_skills = []

    for skill in skills_db:
        if skill in text_lower:
            found_skills.append(skill)

    # Prefer canonical multi-word labels; drop redundant "spring" if spring boot present
    out = list(dict.fromkeys(found_skills))
    if "spring boot" in out and "spring" in out:
        out.remove("spring")
    if "spring boot" in out and "springboot" in out:
        out.remove("springboot")
    return out


def parse_resume(
    path: str,
    include_full_text: bool = False,
    *,
    max_chars: int = 12000,
    text_preview_chars: int = 500,
    similarity_chars: int = 4000,
):
    text = extract_text_from_pdf(path, max_chars=max_chars)

    name = extract_name(text)
    emails = extract_email(text)
    skills = extract_skills(text)
    phone = extract_phone(text)

    out: dict[str, object] = {
        "name": name,
        "email": emails,
        "phone": phone,
        "skills": skills,
        "text_preview": text[:text_preview_chars],
        # Use a bounded text slice for embeddings / similarity.
        "text_for_similarity": text[:similarity_chars],
    }
    if include_full_text:
        # Note: still capped by `max_chars` above.
        out["full_text"] = text
    return out  