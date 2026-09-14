from typing import List

from pydantic import BaseModel, Field


class ResearchComparisonRequest(BaseModel):
    run_a_id: str
    run_b_id: str


class ResearchComparison(BaseModel):
    run_a_id: str
    run_b_id: str
    query: str
    new_companies: List[str] = Field(default_factory=list)
    new_regulations: List[str] = Field(default_factory=list)
    changed_market_estimates: List[str] = Field(default_factory=list)
    new_risks: List[str] = Field(default_factory=list)
    new_opportunities: List[str] = Field(default_factory=list)
    removed_claims: List[str] = Field(default_factory=list)
    added_claims: List[str] = Field(default_factory=list)
