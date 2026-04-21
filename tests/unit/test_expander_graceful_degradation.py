"""Expander: presence filter before cap; empty terms instead of hard error when nothing in Census."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cxg_census_mcp.errors import ExpansionTooWideError
from cxg_census_mcp.models.ontology import TermDefinition
from cxg_census_mcp.ontology.expander import expand
from cxg_census_mcp.ontology.presence import PresenceIndex


@pytest.fixture
def mock_ols_term() -> AsyncMock:
    return AsyncMock(
        return_value=TermDefinition(curie="CL:0000625", label="CD8 T cell", ontology="cl")
    )


def _patch_presence(known: set[str]) -> None:
    """Pin the presence index to a known set of CURIEs for this test."""
    PresenceIndex.known_terms = lambda self, *, column, census_version, organism: known  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_descendants_returns_empty_when_all_dropped(mock_ols_term: AsyncMock) -> None:
    _patch_presence(known={"UNRELATED:0000001"})
    client = AsyncMock()
    client.get_term = mock_ols_term
    client.get_descendants = AsyncMock(return_value=["CL:0000111", "CL:0000222"])

    result = await expand(
        "CL:0000625",
        direction="descendants_inclusive",
        in_census_only=True,
        facet="cell_type",
        client=client,
    )

    assert result.terms == []
    assert result.terms_present_in_census == 0
    assert set(result.terms_missing_from_census) >= {"CL:0000625", "CL:0000111", "CL:0000222"}
    assert result.truncation_reason == "all_terms_absent_from_census"


@pytest.mark.asyncio
async def test_exact_returns_empty_when_term_absent(mock_ols_term: AsyncMock) -> None:
    _patch_presence(known={"UNRELATED:0000001"})
    client = AsyncMock()
    client.get_term = mock_ols_term
    client.get_descendants = AsyncMock(return_value=[])

    result = await expand(
        "CL:0000625",
        direction="exact",
        in_census_only=True,
        facet="cell_type",
        client=client,
    )

    assert result.terms == []
    assert result.terms_missing_from_census == ["CL:0000625"]


@pytest.mark.asyncio
async def test_cap_applies_after_presence_filtering(mock_ols_term: AsyncMock) -> None:
    """346 OLS descendants but only 20 present in Census -> plan succeeds."""
    in_census = {f"UBERON:{i:07d}" for i in range(20)}
    in_census.add("UBERON:0000160")
    _patch_presence(known=in_census)
    client = AsyncMock()
    client.get_term = AsyncMock(
        return_value=TermDefinition(curie="UBERON:0000160", label="intestine", ontology="uberon")
    )
    huge = [f"UBERON:{i:07d}" for i in range(500)]
    client.get_descendants = AsyncMock(return_value=huge)

    with patch("cxg_census_mcp.ontology.expander.get_settings") as mock_settings:
        mock_settings.return_value.max_expansion_terms = 256
        result = await expand(
            "UBERON:0000160",
            direction="descendants_inclusive",
            in_census_only=True,
            facet="tissue",
            client=client,
        )

    assert len(result.terms) == 21
    assert result.terms_present_in_census == 21


@pytest.mark.asyncio
async def test_cap_still_refuses_when_in_census_count_exceeds_cap(
    mock_ols_term: AsyncMock,
) -> None:
    """If even the in-Census subset is too large, refuse loudly."""
    in_census = {f"CL:{i:07d}" for i in range(300)}
    _patch_presence(known=in_census)
    client = AsyncMock()
    client.get_term = mock_ols_term
    client.get_descendants = AsyncMock(return_value=[f"CL:{i:07d}" for i in range(300)])

    with patch("cxg_census_mcp.ontology.expander.get_settings") as mock_settings:
        mock_settings.return_value.max_expansion_terms = 256
        with pytest.raises(ExpansionTooWideError) as ei:
            await expand(
                "CL:0000625",
                direction="descendants_inclusive",
                in_census_only=True,
                facet="cell_type",
                client=client,
            )
        assert "exceeding cap 256" in str(ei.value)
