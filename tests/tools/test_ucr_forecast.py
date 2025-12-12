"""Tests for ucr_forecast tool."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest
from fastmcp.exceptions import ToolError

from tools.ucr_forecast import (
    ucr_forecast,
    normalize_offense,
    format_month,
    determine_trend,
    format_number,
    format_summary,
    format_detailed,
    VALID_OFFENSES,
    OFFENSE_ALIASES,
)

# Access the underlying function for testing (FastMCP decorator pattern)
ucr_forecast_fn = ucr_forecast.fn


# ============================================================================
# Test fixtures
# ============================================================================


@pytest.fixture
def sample_prediction_response():
    """Sample successful prediction API response."""
    return {
        "predictions": [
            {"date": "2025-01", "predicted": 85000, "lower": 80000, "upper": 90000},
            {"date": "2025-02", "predicted": 86000, "lower": 81000, "upper": 91000},
            {"date": "2025-03", "predicted": 87500, "lower": 82000, "upper": 93000},
        ],
        "model": {
            "model_type": "SARIMA",
            "mape": 3.5,
            "training_end": "2024-12",
        },
    }


@pytest.fixture
def sample_history_response():
    """Sample successful history API response."""
    return {
        "history": [
            {"date": "2024-10", "incidents": 82000},
            {"date": "2024-11", "incidents": 83500},
            {"date": "2024-12", "incidents": 84000},
        ]
    }


@pytest.fixture
def mock_httpx_client(sample_prediction_response, sample_history_response):
    """Create a mock httpx.AsyncClient for testing."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_prediction_response
    mock_response.raise_for_status = MagicMock()

    mock_history_response = MagicMock()
    mock_history_response.status_code = 200
    mock_history_response.json.return_value = sample_history_response
    mock_history_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_history_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client


# ============================================================================
# Test normalize_offense function
# ============================================================================


class TestNormalizeOffense:
    """Tests for offense name normalization."""

    def test_valid_offense_passthrough(self):
        """Valid offense names should pass through unchanged."""
        for offense in VALID_OFFENSES:
            assert normalize_offense(offense) == offense

    def test_valid_offense_case_insensitive(self):
        """Offense names should be case-insensitive."""
        assert normalize_offense("VIOLENT-CRIME") == "violent-crime"
        assert normalize_offense("Homicide") == "homicide"
        assert normalize_offense("BURGLARY") == "burglary"

    def test_valid_offense_strips_whitespace(self):
        """Offense names should be stripped of whitespace."""
        assert normalize_offense("  violent-crime  ") == "violent-crime"
        assert normalize_offense("\thomicide\n") == "homicide"

    def test_alias_mapping(self):
        """Alias mappings should work correctly."""
        # Underscore to hyphen
        assert normalize_offense("violent_crime") == "violent-crime"
        assert normalize_offense("property_crime") == "property-crime"
        assert normalize_offense("motor_vehicle_theft") == "motor-vehicle-theft"

        # Short names
        assert normalize_offense("violent") == "violent-crime"
        assert normalize_offense("property") == "property-crime"

        # Alternative names
        assert normalize_offense("murder") == "homicide"
        assert normalize_offense("car-theft") == "motor-vehicle-theft"
        assert normalize_offense("mvt") == "motor-vehicle-theft"

    def test_invalid_offense_raises_error(self):
        """Invalid offense names should raise ToolError."""
        with pytest.raises(ToolError) as exc_info:
            normalize_offense("invalid-offense")

        error_message = str(exc_info.value)
        assert "Unknown offense type: 'invalid-offense'" in error_message
        assert "Valid options are:" in error_message
        # Should list all valid options
        for offense in VALID_OFFENSES:
            assert offense in error_message

    def test_invalid_offense_includes_tip(self):
        """Invalid offense error should include helpful tip."""
        with pytest.raises(ToolError) as exc_info:
            normalize_offense("something_wrong")

        assert "Tip:" in str(exc_info.value)


# ============================================================================
# Test format_month function
# ============================================================================


class TestFormatMonth:
    """Tests for date formatting."""

    def test_yyyy_mm_format(self):
        """YYYY-MM format should be converted to Mon YYYY."""
        assert format_month("2025-01") == "Jan 2025"
        assert format_month("2024-12") == "Dec 2024"
        assert format_month("2025-06") == "Jun 2025"

    def test_yyyy_mm_dd_format(self):
        """YYYY-MM-DD format should be converted to Mon YYYY."""
        assert format_month("2025-01-15") == "Jan 2025"
        assert format_month("2024-12-31") == "Dec 2024"

    def test_invalid_date_returns_original(self):
        """Invalid dates should return the original string."""
        assert format_month("invalid") == "invalid"
        assert format_month("") == ""
        assert format_month("2025") == "2025"


# ============================================================================
# Test determine_trend function
# ============================================================================


class TestDetermineTrend:
    """Tests for trend determination."""

    def test_increasing_trend(self):
        """Predictions with >5% increase should be 'Increasing'."""
        predictions = [
            {"predicted": 100},
            {"predicted": 110},
        ]
        trend, percent = determine_trend(predictions)
        assert trend == "Increasing"
        assert percent == pytest.approx(10.0)

    def test_decreasing_trend(self):
        """Predictions with >5% decrease should be 'Decreasing'."""
        predictions = [
            {"predicted": 100},
            {"predicted": 90},
        ]
        trend, percent = determine_trend(predictions)
        assert trend == "Decreasing"
        assert percent == pytest.approx(-10.0)

    def test_stable_trend(self):
        """Predictions with <5% change should be 'Stable'."""
        predictions = [
            {"predicted": 100},
            {"predicted": 102},
        ]
        trend, percent = determine_trend(predictions)
        assert trend == "Stable"
        assert percent == pytest.approx(2.0)

    def test_single_prediction(self):
        """Single prediction should be 'Stable' with 0%."""
        predictions = [{"predicted": 100}]
        trend, percent = determine_trend(predictions)
        assert trend == "Stable"
        assert percent == 0.0

    def test_empty_predictions(self):
        """Empty predictions should be 'Stable' with 0%."""
        trend, percent = determine_trend([])
        assert trend == "Stable"
        assert percent == 0.0

    def test_zero_first_value(self):
        """Zero first value should be 'Stable' to avoid division by zero."""
        predictions = [{"predicted": 0}, {"predicted": 100}]
        trend, percent = determine_trend(predictions)
        assert trend == "Stable"
        assert percent == 0.0


# ============================================================================
# Test format_number function
# ============================================================================


class TestFormatNumber:
    """Tests for number formatting."""

    def test_thousands_separator(self):
        """Numbers should have thousands separators."""
        assert format_number(1000) == "1,000"
        assert format_number(1000000) == "1,000,000"
        assert format_number(85000) == "85,000"

    def test_rounding(self):
        """Floating point numbers should be rounded."""
        assert format_number(1000.6) == "1,001"
        assert format_number(1000.4) == "1,000"

    def test_small_numbers(self):
        """Small numbers should not have separators."""
        assert format_number(100) == "100"
        assert format_number(0) == "0"


# ============================================================================
# Test format_summary function
# ============================================================================


class TestFormatSummary:
    """Tests for summary formatting."""

    def test_basic_summary(self):
        """Test basic summary output format."""
        predictions = [
            {"date": "2025-01", "predicted": 85000, "lower": 80000, "upper": 90000},
        ]
        model_info = {
            "model_type": "SARIMA",
            "mape": 3.5,
            "training_end": "2024-12",
        }

        result = format_summary("violent-crime", 1, predictions, model_info)

        assert "Violent Crime Forecast" in result
        assert "next 1 months" in result
        assert "Jan 2025" in result
        assert "~85,000" in result
        assert "range: 80,000 - 90,000" in result
        assert "SARIMA" in result
        assert "96.5%" in result  # 100 - 3.5 mape

    def test_summary_with_history(self):
        """Test summary includes history when provided."""
        predictions = [
            {"date": "2025-01", "predicted": 85000, "lower": 80000, "upper": 90000},
        ]
        history = [
            {"date": "2024-12", "incidents": 84000},
        ]
        model_info = {"model_type": "SARIMA", "mape": 3.5, "training_end": "2024-12"}

        result = format_summary("homicide", 1, predictions, model_info, history=history)

        assert "Recent History:" in result
        assert "Dec 2024" in result
        assert "84,000" in result

    def test_offense_name_formatting(self):
        """Test offense names are formatted nicely."""
        predictions = [{"date": "2025-01", "predicted": 1000, "lower": 900, "upper": 1100}]
        model_info = {"model_type": "Test", "mape": 0, "training_end": "2024-12"}

        result = format_summary("motor-vehicle-theft", 1, predictions, model_info)
        assert "Motor Vehicle Theft Forecast" in result


# ============================================================================
# Test format_detailed function
# ============================================================================


class TestFormatDetailed:
    """Tests for detailed JSON formatting."""

    def test_detailed_json_structure(self):
        """Test detailed output is valid JSON with expected structure."""
        predictions = [
            {"date": "2025-01", "predicted": 85000, "lower": 80000, "upper": 90000},
        ]
        model_info = {"model_type": "SARIMA", "mape": 3.5, "training_end": "2024-12"}

        result = format_detailed("violent-crime", 1, predictions, model_info)
        data = json.loads(result)

        assert data["offense"] == "violent-crime"
        assert data["months_forecasted"] == 1
        assert "predictions" in data
        assert "trend" in data
        assert "model" in data

    def test_detailed_includes_history(self):
        """Test detailed output includes history when provided."""
        predictions = [{"date": "2025-01", "predicted": 85000, "lower": 80000, "upper": 90000}]
        history = [{"date": "2024-12", "incidents": 84000}]
        model_info = {"model_type": "SARIMA", "mape": 3.5, "training_end": "2024-12"}

        result = format_detailed("homicide", 1, predictions, model_info, history=history)
        data = json.loads(result)

        assert "history" in data
        assert len(data["history"]) == 1


# ============================================================================
# Test ucr_forecast tool function
# ============================================================================


class TestUcrForecastTool:
    """Tests for the main ucr_forecast tool function."""

    @pytest.mark.asyncio
    async def test_valid_offense_prediction(self, mock_httpx_client, sample_prediction_response):
        """Test successful prediction for valid offense."""
        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_httpx_client):
            result = await ucr_forecast_fn(offense="violent-crime", months_ahead=3)

        assert "Violent Crime Forecast" in result
        assert "next 3 months" in result
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_offense_alias_works(self, mock_httpx_client):
        """Test that offense aliases are properly normalized."""
        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_httpx_client):
            result = await ucr_forecast_fn(offense="murder")  # alias for homicide

        # Verify the API was called with the normalized offense
        call_args = mock_httpx_client.post.call_args
        assert "homicide" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_invalid_offense_error(self):
        """Test that invalid offense raises helpful error."""
        with pytest.raises(ToolError) as exc_info:
            await ucr_forecast_fn(offense="invalid-crime-type")

        error_message = str(exc_info.value)
        assert "Unknown offense type" in error_message
        assert "Valid options are" in error_message

    @pytest.mark.asyncio
    async def test_invalid_months_ahead(self, mock_httpx_client):
        """Test that invalid months_ahead raises error."""
        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_httpx_client):
            with pytest.raises(ToolError) as exc_info:
                await ucr_forecast_fn(offense="homicide", months_ahead=15)

            assert "must be between 1 and 12" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_summary_format_output(self, mock_httpx_client):
        """Test summary format produces prose output."""
        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_httpx_client):
            result = await ucr_forecast_fn(offense="burglary", format="summary")

        # Should be prose, not JSON
        assert "Burglary Forecast" in result
        assert "Predicted Incidents:" in result
        assert "Trend:" in result
        assert "Model:" in result

    @pytest.mark.asyncio
    async def test_detailed_format_output(self, mock_httpx_client):
        """Test detailed format produces valid JSON."""
        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_httpx_client):
            result = await ucr_forecast_fn(offense="burglary", format="detailed")

        # Should be valid JSON
        data = json.loads(result)
        assert "offense" in data
        assert "predictions" in data
        assert "trend" in data
        assert "model" in data

    @pytest.mark.asyncio
    async def test_include_history(self, mock_httpx_client):
        """Test that include_history fetches historical data."""
        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_httpx_client):
            result = await ucr_forecast_fn(
                offense="property-crime",
                include_history=True,
            )

        # Should have made both prediction and history requests
        mock_httpx_client.post.assert_called_once()
        mock_httpx_client.get.assert_called_once()
        assert "Recent History:" in result

    @pytest.mark.asyncio
    async def test_invalid_format_error(self, mock_httpx_client):
        """Test that invalid format raises error."""
        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_httpx_client):
            with pytest.raises(ToolError) as exc_info:
                await ucr_forecast_fn(offense="homicide", format="invalid")

            assert "Invalid format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_timeout_error(self):
        """Test handling of API timeout."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await ucr_forecast_fn(offense="homicide")

            assert "not responding" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_404_error(self):
        """Test handling of 404 from API."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await ucr_forecast_fn(offense="homicide")

            assert "No prediction model found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_500_error(self):
        """Test handling of 500 from API."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await ucr_forecast_fn(offense="homicide")

            assert "experiencing issues" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_connection_error(self):
        """Test handling of connection error."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.RequestError("Connection failed")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await ucr_forecast_fn(offense="homicide")

            assert "Could not connect" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_history_failure_does_not_break(self, sample_prediction_response):
        """Test that history fetch failure doesn't break the main prediction."""
        mock_pred_response = MagicMock()
        mock_pred_response.status_code = 200
        mock_pred_response.json.return_value = sample_prediction_response
        mock_pred_response.raise_for_status = MagicMock()

        mock_history_response = MagicMock()
        mock_history_response.status_code = 500
        mock_history_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=mock_history_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_pred_response)
        mock_client.get = AsyncMock(return_value=mock_history_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_client):
            # Should not raise, just omit history
            result = await ucr_forecast_fn(offense="homicide", include_history=True)

        assert "Homicide Forecast" in result
        assert "Recent History:" not in result  # History should be omitted

    @pytest.mark.asyncio
    async def test_default_parameters(self, mock_httpx_client):
        """Test that default parameters are used correctly."""
        with patch("tools.ucr_forecast.httpx.AsyncClient", return_value=mock_httpx_client):
            result = await ucr_forecast_fn(offense="burglary")

        # Should use default months_ahead=6 and format="summary"
        call_args = mock_httpx_client.post.call_args
        assert call_args[1]["json"] == {"months": 6}
        assert "Burglary Forecast" in result
