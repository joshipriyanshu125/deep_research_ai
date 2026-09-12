"""Day 29 contradiction detection and investigation helpers."""

import re
from dataclasses import dataclass
from typing import List, Sequence

from app.database.models.evidence import Evidence


_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
_NUMBER_PATTERN = re.compile(
    r"(?:[$₹€£¥]\s*)?\b\d+(?:,\d{3})*(?:\.\d+)?\s*"
    r"(?:%|million|billion|trillion|crore|lakh|units?|vehicles?|"
    r"gw|mw|kw|kwh|wh/kg|kg|tons?|tonnes?|cagr|bps)?\b",
    re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_POSITIVE = {"increase", "increased", "growth", "grew", "rose", "risen", "expanded", "surged", "higher"}
_NEGATIVE = {"decrease", "decreased", "decline", "declined", "fell", "dropped", "shrank", "collapsed", "lower"}
_STOPWORDS = {"the", "and", "for", "in", "of", "to", "by", "a", "an", "is", "are"}
_CAUSE_PATTERNS = {
    "different years": re.compile(r"\b(?:19|20)\d{2}\b"),
    "different definitions": re.compile(
        r"\b(?:definition|defined|includes?|excludes?|scope|segment|passenger|commercial|"
        r"nominal|real|reported|adjusted|calendar year|fiscal year)\b", re.IGNORECASE
    ),
    "different datasets": re.compile(
        r"\b(?:dataset|data\s*set|survey|census|registry|database|sample|source data)\b", re.IGNORECASE
    ),
    "different methodologies": re.compile(
        r"\b(?:methodolog|estimate|estimated|projected|forecast|measured|modeled|modelled|"
        r"experimental|trial|benchmark|calculation)\w*\b", re.IGNORECASE
    ),
}


@dataclass(frozen=True)
class ContradictionFinding:
    """A conflict that must be surfaced rather than resolved by selection."""

    left_claim: str
    right_claim: str
    cause: str

    def format(self) -> str:
        return (
            f"CONTRADICTION: '{self.left_claim}' conflicts with '{self.right_claim}'. "
            f"Likely cause: {self.cause}. Investigate the underlying sources before choosing an estimate."
        )


class ContradictionDetector:
    """Detects competing claims and records plausible reasons for the disagreement."""

    def detect(
        self,
        claim: str,
        evidence: Sequence[Evidence],
    ) -> List[ContradictionFinding]:
        findings: List[ContradictionFinding] = []
        claim_tokens = self._tokens(claim)
        claim_numbers = self._numbers(claim)
        claim_polarity = self._polarity(claim)

        for candidate in evidence:
            candidate_tokens = self._tokens(candidate.claim)
            shared_tokens = claim_tokens.intersection(candidate_tokens)
            if len(shared_tokens) < 2 or candidate.claim.strip().lower() == claim.strip().lower():
                continue

            candidate_numbers = self._numbers(candidate.claim)
            candidate_polarity = self._polarity(candidate.claim)
            aligned_trend = bool(claim_polarity and candidate_polarity and claim_polarity == candidate_polarity)
            if aligned_trend and not candidate.verification_status in ("disputed", "refuted"):
                continue

            numeric_conflict = bool(
                claim_numbers
                and candidate_numbers
                and claim_polarity
                and candidate_polarity
                and claim_polarity != candidate_polarity
            )
            polarity_conflict = claim_polarity and candidate_polarity and claim_polarity != candidate_polarity
            if not (numeric_conflict or polarity_conflict or candidate.verification_status in ("disputed", "refuted")):
                continue

            cause = self._investigate_cause(claim, candidate.claim)
            findings.append(ContradictionFinding(claim, candidate.claim, cause))

        return self._deduplicate(findings)

    def _investigate_cause(self, left: str, right: str) -> str:
        causes = []
        left_years = set(_YEAR_PATTERN.findall(left))
        right_years = set(_YEAR_PATTERN.findall(right))
        if left_years and right_years and left_years != right_years:
            causes.append("different years")

        combined = f"{left} {right}"
        for name, pattern in _CAUSE_PATTERNS.items():
            if name != "different years" and pattern.search(combined):
                causes.append(name)
        return ", ".join(causes) if causes else "an unresolved difference in reported values or direction"

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token for token in _TOKEN_PATTERN.findall(text.lower())
            if len(token) >= 2 and token not in _STOPWORDS
        }

    @staticmethod
    def _numbers(text: str) -> set[str]:
        return {number.lower().replace(",", "") for number in _NUMBER_PATTERN.findall(text)}

    @staticmethod
    def _polarity(text: str) -> str:
        tokens = set(_TOKEN_PATTERN.findall(text.lower()))
        positive = bool(tokens.intersection(_POSITIVE))
        negative = bool(tokens.intersection(_NEGATIVE))
        if positive and not negative:
            return "positive"
        if negative and not positive:
            return "negative"
        return ""

    @staticmethod
    def _deduplicate(findings: List[ContradictionFinding]) -> List[ContradictionFinding]:
        seen = set()
        unique = []
        for finding in findings:
            key = tuple(sorted((finding.left_claim, finding.right_claim)))
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        return unique


contradiction_detector = ContradictionDetector()
