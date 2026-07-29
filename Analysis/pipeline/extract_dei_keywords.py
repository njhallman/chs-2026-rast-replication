"""Keyword definitions used to measure DEI language in proxy statements."""

import re


DEI_WORDS = re.compile(
    r"\b(?:diversity|diverse|inclusion|inclusive|equity|equitable|dei)\b",
    re.IGNORECASE,
)

GENDER_WORDS = re.compile(
    r"\b(?:gender|women|woman|female|girls)\b",
    re.IGNORECASE,
)

WORKFORCE_DEI_WORDS = re.compile(
    r"\b(?:retention|pipeline|recruit|hire|hiring|talent|"
    r"workforce\s+diversity|pay\s+equity|pay\s+gap|"
    r"parental\s+leave|family\s+leave|mentoring|sponsorship)\b",
    re.IGNORECASE,
)

ANY_DEI = re.compile(
    r"\b(?:diversity|diverse|inclusion|inclusive|equity|equitable|dei|"
    r"gender|women|woman|female|girls|"
    r"retention|pipeline|recruit|hire|hiring|talent|"
    r"mentoring|sponsorship)\b|"
    r"\b(?:workforce\s+diversity|pay\s+equity|pay\s+gap|"
    r"parental\s+leave|family\s+leave)\b",
    re.IGNORECASE,
)


def compute_measures(text: str) -> dict:
    """Compute DEI keyword measures for one proxy statement."""
    paragraphs = re.split(r"\n\s*\n", text)
    matching_paragraphs = [para for para in paragraphs if ANY_DEI.search(para)]
    return {
        "dei_word_count": len(DEI_WORDS.findall(text)),
        "gender_word_count": len(GENDER_WORDS.findall(text)),
        "dei_char_length": sum(len(para) for para in matching_paragraphs),
        "dei_section_count": len(matching_paragraphs),
        "workforce_dei_count": len(WORKFORCE_DEI_WORDS.findall(text)),
        "total_doc_length": len(text),
    }
