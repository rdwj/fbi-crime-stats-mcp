"""Tests for ucr_history tool."""

import pytest
from unittest.mock import AsyncMock, patch
from fastmcp.exceptions import ToolError

from tools.ucr_history import (
    ucr_history,
    normalize_offense,
    normalize_state,
    calculate_trend,
    calculate_yearly_totals,
    format_number,
    parse_api_date,
)

# Access the underlying function for testing (FastMCP decorator pattern)
ucr_history_fn = ucr_history.fn


class TestNormalizeOffense:
    """Tests for offense normalization."""

    def test_valid_offense_unchanged(self):
        """Valid offense names should be returned as-is."""
        assert normalize_offense("violent-crime") == "violent-crime"
        assert normalize_offense("homicide") == "homicide"

    def test_offense_aliases(self):
        """Offense aliases should be normalized to canonical form."""
        assert normalize_offense("murder") == "homicide"
        assert normalize_offense("violent_crime") == "violent-crime"
        assert normalize_offense("car-theft") == "motor-vehicle-theft"

    def test_case_insensitive(self):
        """Offense names should be case insensitive."""
        assert normalize_offense("VIOLENT-CRIME") == "violent-crime"
        assert normalize_offense("Homicide") == "homicide"

    def test_invalid_offense(self):
        """Invalid offense should raise ToolError."""
        with pytest.raises(ToolError, match="Unknown offense type"):
            normalize_offense("robbery")


class TestNormalizeState:
    """Tests for state normalization."""

    def test_valid_state_unchanged(self):
        """Valid state codes should be normalized to uppercase."""
        assert normalize_state("CA") == "CA"
        assert normalize_state("tx") == "TX"

    def test_none_returns_none(self):
        """None state should return None."""
        assert normalize_state(None) is None

    def test_invalid_state(self):
        """Invalid state should raise ToolError."""
        with pytest.raises(ToolError, match="Unknown state code"):
            normalize_state("ZZ")


class TestCalculateTrend:
    """Tests for trend calculation."""

    def test_increasing_trend(self):
        """Should detect increasing trend."""
        data = [
            {"actual": 100},
            {"actual": 150},
            {"actual": 200},
        ]
        direction, change = calculate_trend(data)
        assert direction == "Increasing"
        assert change > 5

    def test_decreasing_trend(self):
        """Should detect decreasing trend."""
        data = [
            {"actual": 200},
            {"actual": 150},
            {"actual": 100},
        ]
        direction, change = calculate_trend(data)
        assert direction == "Decreasing"
        assert change < -5

    def test_stable_trend(self):
        """Should detect stable trend."""
        data = [
            {"actual": 100},
            {"actual": 102},
            {"actual": 101},
        ]
        direction, change = calculate_trend(data)
        assert direction == "Stable"
        assert -5 <= change <= 5

    def test_insufficient_data(self):
        """Should return stable for insufficient data."""
        data = [{"actual": 100}]
        direction, change = calculate_trend(data)
        assert direction == "Stable"
        assert change == 0.0


class TestCalculateYearlyTotals:
    """Tests for yearly totals calculation."""

    def test_yearly_aggregation(self):
        """Should aggregate monthly data into yearly totals."""
        data = [
            {"date": "2020-01", "actual": 100},
            {"date": "2020-02", "actual": 150},
            {"date": "2021-01", "actual": 200},
            {"date": "2021-02", "actual": 250},
        ]
        totals = calculate_yearly_totals(data)
        assert totals[2020] == 250
        assert totals[2021] == 450

    def test_empty_data(self):
        """Should return empty dict for empty data."""
        assert calculate_yearly_totals([]) == {}


class TestHelperFunctions:
    """Tests for utility functions."""

    def test_format_number(self):
        """Should format numbers with commas."""
        assert format_number(1000) == "1,000"
        assert format_number(1000000) == "1,000,000"
        assert format_number(500.7) == "501"

    def test_parse_api_date(self):
        """Should convert MM-YYYY to YYYY-MM format."""
        assert parse_api_date("01-2020") == "2020-01"
        assert parse_api_date("12-2021") == "2021-12"
        # Should handle already normalized dates
        assert parse_api_date("2020-01") == "2020-01"


class TestUcrHistoryValidation:
    """Tests for ucr_history parameter validation."""

    @pytest.mark.asyncio
    async def test_invalid_offense_raises_error(self):
        """Should raise ToolError for invalid offense."""
        with pytest.raises(ToolError, match="Unknown offense type"):
            await ucr_history_fn(
                offense="invalid-crime",
                from_year=2020,
                to_year=2021,
            )

    @pytest.mark.asyncio
    async def test_invalid_state_raises_error(self):
        """Should raise ToolError for invalid state."""
        with pytest.raises(ToolError, match="Unknown state code"):
            await ucr_history_fn(
                offense="violent-crime",
                from_year=2020,
                to_year=2021,
                state="ZZ",
            )

    @pytest.mark.asyncio
    async def test_invalid_year_range_raises_error(self):
        """Should raise ToolError when from_year > to_year."""
        with pytest.raises(ToolError, match="must be less than or equal"):
            await ucr_history_fn(
                offense="violent-crime",
                from_year=2022,
                to_year=2020,
            )

    @pytest.mark.asyncio
    async def test_year_before_2015_raises_error(self):
        """Should raise ToolError for year before 2015."""
        with pytest.raises(ToolError, match="2015 or later"):
            await ucr_history_fn(
                offense="violent-crime",
                from_year=2010,
                to_year=2020,
            )

    @pytest.mark.asyncio
    async def test_invalid_format_raises_error(self):
        """Should raise ToolError for invalid format."""
        with pytest.raises(ToolError, match="Invalid format"):
            await ucr_history_fn(
                offense="violent-crime",
                from_year=2020,
                to_year=2021,
                format="invalid",
            )


class TestUcrHistoryIntegration:
    """Integration tests for ucr_history (require FBI API)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_national_history_summary(self):
        """Test fetching national history in summary format."""
        result = await ucr_history_fn(
            offense="violent-crime",
            from_year=2020,
            to_year=2022,
            format="summary",
        )
        assert "Violent Crime Historical Data" in result
        assert "United States" in result
        assert "Annual Totals:" in result
        assert "2020" in result or "2021" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_national_history_detailed(self):
        """Test fetching national history in detailed format."""
        import json

        result = await ucr_history_fn(
            offense="homicide",
            from_year=2020,
            to_year=2022,
            format="detailed",
        )
        data = json.loads(result)
        assert data["offense"] == "homicide"
        assert data["location"] == "national"
        assert "monthly_data" in data
        assert "yearly_totals" in data
        assert "trend" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_state_history(self):
        """Test fetching state-level history."""
        result = await ucr_history_fn(
            offense="burglary",
            from_year=2020,
            to_year=2022,
            state="CA",
            format="summary",
        )
        assert "California" in result
        assert "Burglary Historical Data" in result
