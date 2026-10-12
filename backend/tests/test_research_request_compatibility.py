"""Offline compatibility tests for frontend research submissions."""

import pytest
from pydantic import ValidationError

from app.database.models.research import ResearchRequest
from app.research.research_modes import get_mode_config


@pytest.mark.parametrize("alias", ["quick", "standard", "deep"])
def test_depth_aliases_use_research_mode_defaults(alias):
    request = ResearchRequest(query="compatibility test", depth=alias)

    assert request.depth == get_mode_config(alias).depth


@pytest.mark.parametrize("depth", [1, 2, 3, 5])
def test_numeric_depth_remains_supported(depth):
    request = ResearchRequest(query="compatibility test", depth=depth)

    assert request.depth == depth


@pytest.mark.parametrize("depth", [0, 6, "expert", "not-a-depth"])
def test_invalid_depth_is_rejected(depth):
    with pytest.raises(ValidationError):
        ResearchRequest(query="compatibility test", depth=depth)


def test_explicit_research_mode_is_not_overwritten_by_depth_alias():
    request = ResearchRequest(
        query="compatibility test",
        depth="quick",
        research_mode="deep",
    )

    assert request.depth == get_mode_config("quick").depth
    assert request.research_mode == "deep"
