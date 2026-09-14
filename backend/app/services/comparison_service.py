import re
from typing import Iterable, List, Sequence, Tuple

from fastapi import HTTPException

from app.database.models.comparison import ResearchComparison
from app.database.repositories.evidence_repo import evidence_repo
from app.database.repositories.report_repo import report_repo
from app.database.repositories.research_repo import research_repo


_COMPANY_TERMS = ("company", "corporation", "inc.", "corp.", "ltd", "startup", "manufacturer")
_REGULATION_TERMS = ("regulation", "law", "legislation", "policy", "directive", "compliance", "rule")
_RISK_TERMS = ("risk", "threat", "challenge", "uncertainty", "barrier")
_OPPORTUNITY_TERMS = ("opportunity", "growth", "potential", "investment", "upside")
_NUMBER_PATTERN = re.compile(r"(?:[$€£]\s?\d[\d,.]*\s?(?:m|b|million|billion)?|\d[\d,.]*\s?%)", re.I)


def _clean_values(values: Iterable[str]) -> List[str]:
    return [value.strip() for value in values if value and value.strip()]


def _key(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold()).strip()


def _difference(left: Sequence[str], right: Sequence[str]) -> Tuple[List[str], List[str]]:
    left_by_key = {_key(value): value for value in left}
    right_by_key = {_key(value): value for value in right}
    return (
        [right_by_key[key] for key in right_by_key.keys() - left_by_key.keys()],
        [left_by_key[key] for key in left_by_key.keys() - right_by_key.keys()],
    )


def _classify_claims(claims: Iterable[str], terms: Sequence[str]) -> List[str]:
    return [claim for claim in claims if any(term in claim.casefold() for term in terms)]


class ComparisonService:
    async def compare(self, run_a_id: str, run_b_id: str) -> ResearchComparison:
        run_a = await research_repo.get_job(run_a_id)
        run_b = await research_repo.get_job(run_b_id)
        if not run_a or not run_b:
            raise HTTPException(status_code=404, detail="One or both research runs were not found")
        if run_a.user_id != run_b.user_id:
            raise HTTPException(status_code=403, detail="Research runs must belong to the same user")

        report_a = await report_repo.get_by_research_id(run_a_id)
        report_b = await report_repo.get_by_research_id(run_b_id)
        if not report_a or not report_b:
            raise HTTPException(status_code=422, detail="Both research runs must have completed reports")

        claims_a = _clean_values(
            list(report_a.key_findings)
            + [fact.claim for fact in report_a.fact_checks]
        )
        claims_b = _clean_values(
            list(report_b.key_findings)
            + [fact.claim for fact in report_b.fact_checks]
        )
        added_claims, removed_claims = _difference(claims_a, claims_b)
        new_opportunities, _ = _difference(report_a.opportunities, report_b.opportunities)
        new_risks, _ = _difference(report_a.risks, report_b.risks)
        _, market_removed = _difference(
            [report_a.market_analysis or ""],
            [report_b.market_analysis or ""],
        )
        changed_market_estimates = [
            statement for statement in [report_b.market_analysis or ""]
            if statement and _NUMBER_PATTERN.search(statement)
        ] if market_removed else []

        return ResearchComparison(
            run_a_id=run_a_id,
            run_b_id=run_b_id,
            query=run_b.query,
            new_companies=_classify_claims(added_claims, _COMPANY_TERMS),
            new_regulations=_classify_claims(added_claims, _REGULATION_TERMS),
            changed_market_estimates=changed_market_estimates,
            new_risks=new_risks,
            new_opportunities=new_opportunities,
            removed_claims=removed_claims,
            added_claims=added_claims,
        )


comparison_service = ComparisonService()
