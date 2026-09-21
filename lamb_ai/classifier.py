"""
Lamp AI Pipeline
===================
Three transparent, explainable AI components (no black boxes):

1. classify_report()      -> category / subcategory / urgency (keyword + rule
                              based classifier for the PoC; swappable for a
                              fine-tuned transformer in production)
2. find_similar_reports()  -> TF-IDF + cosine similarity duplicate/near-
                              duplicate detection
3. compute_risk_score()    -> documented formula:
                              risk = severity x urgency x (1 + affected/1000) x evidence_confidence
                              normalized to 0-100, always returned WITH its
                              inputs so the score is auditable, never opaque.

Design principle (see README, Step 8/17 - Responsible AI):
Every AI output here is a *recommendation* surfaced to a human verifier.
Nothing in this module auto-publishes an accusation or auto-closes a case.
"""

from dataclasses import dataclass, field
from typing import List, Dict
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CATEGORY_KEYWORDS = {
    "Water Infrastructure": ["water", "borehole", "tap", "pipe", "well"],
    "Electricity/Power": ["electricity", "power", "transformer", "light", "nepa", "phcn"],
    "Road/Transport Infrastructure": ["road", "bridge", "pothole", "highway", "commut"],
    "Healthcare Access": ["clinic", "hospital", "health centre", "nurse", "drugs", "medical"],
    "Education/Infrastructure": ["school", "teacher", "classroom", "pupils", "roof collapsed"],
    "Safety/Security Concern": ["robbery", "armed", "attack", "kidnap", "unsafe", "patrol", "gunmen"],
    "Community Dispute": ["dispute", "boundary", "clash", "tension", "land"],
    "Environmental Hazard": ["waste", "dumpsite", "flooding", "gas flaring", "pollution", "odour"],
    "Suspected Misuse of Public Funds": ["budget", "contractor", "abandoned", "marked complete", "transparency"],
    "Abuse/Protection Concern": ["abuse", "exploitative", "denied access", "minor", "vulnerable"],
}

URGENT_TERMS = ["emergency", "now", "today", "urgent", "immediately", "life", "danger", "attack"]


@dataclass
class ClassificationResult:
    category: str
    urgency_1to5: int
    matched_keywords: List[str]
    confidence: float
    explanation: str


def classify_report(text: str) -> ClassificationResult:
    """Rule-based classifier (PoC). Deliberately simple + inspectable so a
    human reviewer can see exactly why a label was assigned. In production
    this stage is replaced with a fine-tuned multilingual transformer
    (English / Pidgin / Hausa / Yoruba / Igbo), but the *output contract*
    (category, urgency, evidence, confidence, explanation) stays the same
    so nothing downstream needs to change."""
    text_l = text.lower()
    scores: Dict[str, List[str]] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in text_l]
        if hits:
            scores[category] = hits

    if not scores:
        best_category = "Uncategorized - Needs Human Review"
        matched = []
        confidence = 0.3
    else:
        best_category = max(scores, key=lambda c: len(scores[c]))
        matched = scores[best_category]
        confidence = min(0.5 + 0.12 * len(matched), 0.95)

    urgency = 2
    urgent_hits = [t for t in URGENT_TERMS if t in text_l]
    if urgent_hits:
        urgency = min(5, 2 + len(urgent_hits))

    explanation = (
        f"Matched keywords {matched} -> category '{best_category}'. "
        f"Urgency raised by terms {urgent_hits}." if urgent_hits else
        f"Matched keywords {matched} -> category '{best_category}'. No urgency terms detected."
    )

    return ClassificationResult(
        category=best_category,
        urgency_1to5=urgency,
        matched_keywords=matched,
        confidence=round(confidence, 2),
        explanation=explanation,
    )


def find_similar_reports(new_text: str, existing_texts: List[str], threshold: float = 0.45) -> List[Dict]:
    """TF-IDF cosine similarity duplicate/near-duplicate detector.
    Returns candidates above threshold with their similarity score -
    the platform never auto-merges reports, it flags them for a human
    verifier to confirm as 'duplicate' / 'corroborating' / 'unrelated'."""
    if not existing_texts:
        return []
    corpus = existing_texts + [new_text]
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf = vectorizer.fit_transform(corpus)
    sims = cosine_similarity(tfidf[-1], tfidf[:-1]).flatten()

    results = [
        {"index": i, "similarity": round(float(s), 3), "text": existing_texts[i]}
        for i, s in enumerate(sims) if s >= threshold
    ]
    return sorted(results, key=lambda r: -r["similarity"])


def compute_risk_score(severity: int, urgency: int, affected: int, evidence_confidence: float) -> Dict:
    """Documented, auditable formula - never a black box.
    risk = severity x urgency x (1 + affected/1000) x evidence_confidence,
    scaled to 0-100."""
    raw = severity * urgency * (1 + affected / 1000) * evidence_confidence
    score = round(min(raw / 2.5, 100), 1)
    return {
        "risk_score": score,
        "inputs": {
            "severity_1to5": severity,
            "urgency_1to5": urgency,
            "num_affected_est": affected,
            "evidence_confidence": evidence_confidence,
        },
        "formula": "severity x urgency x (1 + affected/1000) x evidence_confidence, scaled to 0-100",
    }
