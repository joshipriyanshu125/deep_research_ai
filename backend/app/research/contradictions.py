"""Day 29 contradiction detection and investigation helpers."""

import re
from dataclasses import dataclass
from typing import List, Sequence, Set, Tuple, Optional, Union

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
_STOPWORDS = {"the", "and", "for", "in", "of", "to", "by", "a", "an", "is", "are", "on", "at", "with", "as"}

# Distinct geographic regions / scopes that cannot contradict each other
_GEO_REGIONS = {
    "india": {"india", "indian", "delhi", "mumbai", "bengaluru", "siam", "pib", "niti", "fame", "emps"},
    "canada": {"canada", "canadian", "quebec", "ontario", "vancouver", "toronto", "montreal"},
    "usa": {"us", "usa", "united states", "america", "american", "california", "texas", "sec"},
    "china": {"china", "chinese", "beijing", "shanghai", "byd"},
    "europe": {"europe", "european", "eu", "germany", "german", "uk", "britain", "british", "france", "norway"},
    "japan": {"japan", "japanese", "toyota", "nissan", "honda"},
}

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
        claim: Union[str, Sequence[Evidence]],
        evidence: Optional[Sequence[Evidence]] = None,
    ) -> List[ContradictionFinding]:
        """
        Detect contradictions for a single claim against an evidence sequence,
        or across an entire evidence sequence when called as detect(all_evidence).
        """
        if isinstance(claim, (list, tuple)) and evidence is None:
            return self.detect_all(claim)

        if not isinstance(claim, str) or not evidence:
            return []

        findings: List[ContradictionFinding] = []
        claim_tokens = self._tokens(claim)
        claim_numbers = self._numbers(claim)
        claim_polarity = self._polarity(claim)
        claim_region = self._detect_region(claim)

        for candidate in evidence:
            cand_claim = candidate.claim.strip()
            if not cand_claim or cand_claim.lower() == claim.strip().lower():
                continue

            # Scope / Regional check: different regions cannot contradict
            cand_region = self._detect_region(cand_claim)
            if claim_region and cand_region and claim_region != cand_region:
                continue

            candidate_tokens = self._tokens(cand_claim)
            shared_tokens = claim_tokens.intersection(candidate_tokens)
            if len(shared_tokens) < 2:
                continue

            candidate_numbers = self._numbers(cand_claim)
            candidate_polarity = self._polarity(cand_claim)

            is_disputed = candidate.verification_status in ("disputed", "refuted")
            polarity_conflict = bool(claim_polarity and candidate_polarity and claim_polarity != candidate_polarity)
            numeric_conflict = bool(
                claim_numbers
                and candidate_numbers
                and claim_numbers != candidate_numbers
                and polarity_conflict
            )

            if not (numeric_conflict or polarity_conflict or is_disputed):
                continue

            cause = self._investigate_cause(claim, cand_claim)
            findings.append(ContradictionFinding(claim, cand_claim, cause))
            if len(findings) >= 5:
                break

        return self._deduplicate(findings)[:5]

    def detect_all(self, evidence: Sequence[Evidence]) -> List[ContradictionFinding]:
        """
        Compares all pairs in the evidence sequence once, with global deduplication.
        """
        if not evidence or len(evidence) < 2:
            return []

        all_findings: List[ContradictionFinding] = []
        n = len(evidence)
        for i in range(n):
            for j in range(i + 1, n):
                claim_a = evidence[i].claim.strip()
                claim_b = evidence[j].claim.strip()
                if not claim_a or not claim_b or claim_a.lower() == claim_b.lower():
                    continue

                # Scope / Regional check
                region_a = self._detect_region(claim_a)
                region_b = self._detect_region(claim_b)
                if region_a and region_b and region_a != region_b:
                    continue

                tokens_a = self._tokens(claim_a)
                tokens_b = self._tokens(claim_b)
                shared = tokens_a.intersection(tokens_b)
                if len(shared) < 2:
                    continue

                polarity_a = self._polarity(claim_a)
                polarity_b = self._polarity(claim_b)
                numbers_a = self._numbers(claim_a)
                numbers_b = self._numbers(claim_b)

                is_disputed = (
                    evidence[i].verification_status in ("disputed", "refuted")
                    or evidence[j].verification_status in ("disputed", "refuted")
                )
                polarity_conflict = bool(polarity_a and polarity_b and polarity_a != polarity_b)
                numeric_conflict = bool(
                    numbers_a
                    and numbers_b
                    and numbers_a != numbers_b
                    and polarity_conflict
                )

                if numeric_conflict or polarity_conflict or is_disputed:
                    cause = self._investigate_cause(claim_a, claim_b)
                    all_findings.append(ContradictionFinding(claim_a, claim_b, cause))
                    if len(all_findings) >= 8:
                        break
            if len(all_findings) >= 8:
                break

        return self._deduplicate(all_findings)[:5]

    def _detect_region(self, text: str) -> Optional[str]:
        tokens = set(re.findall(r"[a-z]+", text.lower()))
        for region_name, region_keywords in _GEO_REGIONS.items():
            if tokens.intersection(region_keywords):
                return region_name
        return None

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
    def _tokens(text: str) -> Set[str]:
        return {
            token for token in _TOKEN_PATTERN.findall(text.lower())
            if len(token) >= 2 and token not in _STOPWORDS
        }

    @staticmethod
    def _numbers(text: str) -> Set[str]:
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
            key = tuple(sorted((finding.left_claim.strip().lower(), finding.right_claim.strip().lower())))
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        return unique


contradiction_detector = ContradictionDetector()
