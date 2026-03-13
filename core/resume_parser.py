import pdfplumber
import re
import spacy

# nlp = spacy.load("en_core_web_sm")
nlp = None  # Global variable

def get_nlp():
    global nlp
    if nlp is None:
        nlp = spacy.load("en_core_web_sm")
    return nlp

COMMON_SKILLS = [
    "python","java","c++","react","node","mongodb",
    "mysql","docker","kubernetes","aws","html",
    "css","javascript","fastapi","spring","django"
]

def parse_resume(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    email = re.search(r'\S+@\S+', text)
    phone = re.search(r'\+?\d[\d\s\-]{8,15}', text)

    name = ""
    # doc = nlp(text)
    # 🔽 THIS is where it goes
    doc = get_nlp()(text)


    for ent in doc.ents:
        if ent.label_ == "PERSON":
            name = ent.text
            break

    skills = [s for s in COMMON_SKILLS if s in text.lower()]

    return {
        "name": name,
        "email": email.group(0) if email else "",
        "phone": phone.group(0) if phone else "",
        "skills": list(set(skills)),
        "raw_text": text
    }
