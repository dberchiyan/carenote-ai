"""Small controlled vocabularies for symptoms, medications and routes (synthetic demo scope)."""

# Canonical symptom -> phrasings a nurse might use (lowercase).
SYMPTOMS: dict[str, tuple[str, ...]] = {
    "headache": ("headache", "head pain", "head ache"),
    "nausea": ("nausea", "nauseous", "nauseated", "feeling sick"),
    "dizziness": ("dizziness", "dizzy", "lightheaded", "light-headed"),
    "chest pain": ("chest pain", "pain in the chest", "chest discomfort", "chest tightness"),
    "shortness of breath": (
        "shortness of breath",
        "short of breath",
        "breathless",
        "dyspnea",
        "sob",
    ),
    "abdominal pain": ("abdominal pain", "tummy pain", "stomach ache", "stomachache", "belly pain"),
    "fatigue": ("fatigue", "tiredness", "tired", "exhausted", "lethargic"),
    "cough": ("cough", "coughing"),
    "vomiting": ("vomiting", "vomited", "threw up", "emesis"),
    "back pain": ("back pain", "backache", "pain in the back"),
    "confusion": ("confusion", "confused", "disoriented", "disorientated"),
    "insomnia": ("insomnia", "couldn't sleep", "could not sleep", "trouble sleeping", "poor sleep"),
}

# Canonical medication -> typical (dose, route) pairs used by the dataset generator.
MEDICATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "paracetamol": (("500 mg", "oral"), ("1 g", "oral"), ("1 g", "iv")),
    "ibuprofen": (("400 mg", "oral"), ("200 mg", "oral")),
    "metoprolol": (("25 mg", "oral"), ("50 mg", "oral")),
    "furosemide": (("40 mg", "iv"), ("20 mg", "oral")),
    "insulin aspart": (("4 units", "subcutaneous"), ("6 units", "subcutaneous")),
    "morphine": (("2 mg", "iv"), ("5 mg", "subcutaneous")),
    "ondansetron": (("4 mg", "iv"), ("4 mg", "oral")),
    "salbutamol": (("2 puffs", "inhaled"), ("5 mg", "inhaled")),
    "enoxaparin": (("40 mg", "subcutaneous"),),
    "amlodipine": (("5 mg", "oral"),),
}

# Canonical route -> phrasings (lowercase).
ROUTES: dict[str, tuple[str, ...]] = {
    "oral": ("orally", "by mouth", "po", "p.o.", "oral"),
    "iv": ("iv", "i.v.", "intravenously", "intravenous"),
    "subcutaneous": ("subcutaneously", "sc", "s.c.", "subcut", "subcutaneous"),
    "inhaled": ("inhaled", "via inhaler", "nebulised", "nebulized"),
}
