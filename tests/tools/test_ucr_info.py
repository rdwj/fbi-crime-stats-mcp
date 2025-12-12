"""Tests for ucr_info tool."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx
from fastmcp.exceptions import ToolError
from tools.ucr_info import ucr_info, _format_month, _format_model_type, _format_all_models, _format_model_details

# Access the underlying function for testing (FastMCP decorator pattern)
ucr_info_fn = ucr_info.fn


# Sample API response data
SAMPLE_MODELS_RESPONSE = {
    "models": [
        {
            "offense": "violent-crime",
            "model_type": "ARIMA",
            "mape": 9.0,
            "training_end": "2024-12",
            "parameters": {"order": [1, 1, 1]},
        },
        {
            "offense": "property-crime",
            "model_type": "ARIMA",
            "mape": 7.9,
            "training_end": "2024-12",
            "parameters": {"order": [1, 1, 1]},
        },
        {
            "offense": "homicide",
            "model_type": "Prophet",
            "mape": 8.2,
            "training_end": "2024-12",
            "parameters": {},
        },
        {
            "offense": "burglary",
            "model_type": "ARIMA",
            "mape": 7.7,
            "training_end": "2024-12",
            "parameters": {"order": [1, 1, 1]},
        },
        {
            "offense": "motor-vehicle-theft",
            "model_type": "SARIMA",
            "mape": 5.4,
            "training_end": "2024-12",
            "parameters": {"order": [1, 1, 1], "seasonal_order": [1, 1, 1, 12]},
        },
    ]
}


class MockResponse:
    """Mock httpx response object."""

    def __init__(self, status_code: int, json_data: dict | None = None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


# --- Helper Function Tests ---


class TestFormatMonth:
    """Tests for _format_month helper function."""

    def test_format_valid_date(self):
        """Test formatting a valid date string."""
        assert _format_month("2024-12") == "December 2024"
        assert _format_month("2024-01") == "January 2024"
        assert _format_month("2023-06") == "June 2023"

    def test_format_invalid_date(self):
        """Test formatting invalid date strings returns original."""
        assert _format_month("invalid") == "invalid"
        assert _format_month("2024") == "2024"
        assert _format_month("") == ""

    def test_format_edge_months(self):
        """Test edge case months."""
        assert _format_month("2024-13") == "2024-13"  # Invalid month
        assert _format_month("2024-00") == "2024-00"  # Invalid month


class TestFormatModelType:
    """Tests for _format_model_type helper function."""

    def test_regular_model(self):
        """Test formatting a regular model without seasonal parameters."""
        model = {"model_type": "ARIMA", "parameters": {"order": [1, 1, 1]}}
        assert _format_model_type(model) == "ARIMA"

    def test_seasonal_model(self):
        """Test formatting a model with seasonal parameters."""
        model = {
            "model_type": "SARIMA",
            "parameters": {"order": [1, 1, 1], "seasonal_order": [1, 1, 1, 12]},
        }
        assert _format_model_type(model) == "SARIMA (seasonal)"

    def test_unknown_model(self):
        """Test formatting when model_type is missing."""
        model = {"parameters": {}}
        assert _format_model_type(model) == "Unknown"


class TestFormatAllModels:
    """Tests for _format_all_models helper function."""

    def test_format_multiple_models(self):
        """Test formatting all models output."""
        result = _format_all_models(SAMPLE_MODELS_RESPONSE["models"])

        # Check header
        assert "FBI UCR Crime Forecasting Models" in result
        assert "Available Models:" in result

        # Check all offenses are listed
        assert "violent-crime" in result
        assert "property-crime" in result
        assert "homicide" in result
        assert "burglary" in result
        assert "motor-vehicle-theft" in result

        # Check accuracy is calculated correctly (100 - MAPE)
        assert "91.0%" in result  # violent-crime: 100 - 9.0
        assert "92.1%" in result  # property-crime: 100 - 7.9
        assert "94.6%" in result  # motor-vehicle-theft: 100 - 5.4

        # Check footer info
        assert "FBI Uniform Crime Reporting (UCR) Program" in result
        assert "National level" in result
        assert "Up to 12 months" in result

    def test_format_empty_models(self):
        """Test formatting with empty models list."""
        result = _format_all_models([])
        assert "FBI UCR Crime Forecasting Models" in result
        assert "Available Models:" in result


class TestFormatModelDetails:
    """Tests for _format_model_details helper function."""

    def test_format_single_model(self):
        """Test formatting detailed view for a single model."""
        model = {
            "offense": "motor-vehicle-theft",
            "model_type": "SARIMA",
            "mape": 5.4,
            "training_end": "2024-12",
            "parameters": {"order": [1, 1, 1], "seasonal_order": [1, 1, 1, 12]},
        }
        result = _format_model_details(model)

        assert "Motor Vehicle Theft Forecasting Model" in result
        assert "Theft or attempted theft of motor vehicles" in result
        assert "SARIMA" in result
        assert "94.6%" in result  # 100 - 5.4
        assert "December 2024" in result
        assert 'ucr_forecast(offense="motor-vehicle-theft")' in result

    def test_format_model_with_why(self):
        """Test that 'Why model' explanation is included."""
        model = {
            "offense": "motor-vehicle-theft",
            "model_type": "SARIMA",
            "mape": 5.4,
            "training_end": "2024-12",
            "parameters": {},
        }
        result = _format_model_details(model)
        assert "Why SARIMA:" in result
        assert "seasonal patterns" in result


# --- Main Tool Function Tests ---


@pytest.mark.asyncio
async def test_ucr_info_list_all_models():
    """Test listing all models when no offense is specified."""
    mock_response = MockResponse(200, SAMPLE_MODELS_RESPONSE)

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = await ucr_info_fn(offense=None)

        assert "FBI UCR Crime Forecasting Models" in result
        assert "violent-crime" in result
        assert "property-crime" in result
        assert "homicide" in result
        assert "burglary" in result
        assert "motor-vehicle-theft" in result


@pytest.mark.asyncio
async def test_ucr_info_specific_offense():
    """Test getting info for a specific offense."""
    mock_response = MockResponse(200, SAMPLE_MODELS_RESPONSE)

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = await ucr_info_fn(offense="motor-vehicle-theft")

        assert "Motor Vehicle Theft Forecasting Model" in result
        assert "SARIMA" in result
        assert "94.6%" in result


@pytest.mark.asyncio
async def test_ucr_info_case_insensitive_offense():
    """Test that offense lookup is case insensitive."""
    mock_response = MockResponse(200, SAMPLE_MODELS_RESPONSE)

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = await ucr_info_fn(offense="MOTOR-VEHICLE-THEFT")

        assert "Motor Vehicle Theft Forecasting Model" in result


@pytest.mark.asyncio
async def test_ucr_info_invalid_offense():
    """Test error handling for invalid offense."""
    mock_response = MockResponse(200, SAMPLE_MODELS_RESPONSE)

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        with pytest.raises(ToolError, match="not found"):
            await ucr_info_fn(offense="invalid-offense")


@pytest.mark.asyncio
async def test_ucr_info_invalid_offense_shows_available():
    """Test that invalid offense error lists available offenses."""
    mock_response = MockResponse(200, SAMPLE_MODELS_RESPONSE)

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        with pytest.raises(ToolError) as exc_info:
            await ucr_info_fn(offense="invalid-offense")

        error_message = str(exc_info.value)
        assert "violent-crime" in error_message
        assert "property-crime" in error_message


@pytest.mark.asyncio
async def test_ucr_info_api_error():
    """Test handling of API errors."""
    mock_response = MockResponse(500)

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        with pytest.raises(ToolError, match="HTTP 500"):
            await ucr_info_fn()


@pytest.mark.asyncio
async def test_ucr_info_empty_models():
    """Test handling when API returns no models."""
    mock_response = MockResponse(200, {"models": []})

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        with pytest.raises(ToolError, match="No models available"):
            await ucr_info_fn()


@pytest.mark.asyncio
async def test_ucr_info_timeout():
    """Test handling of request timeout."""
    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.side_effect = httpx.TimeoutException("Timeout")
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        with pytest.raises(ToolError, match="timed out"):
            await ucr_info_fn()


@pytest.mark.asyncio
async def test_ucr_info_network_error():
    """Test handling of network errors."""
    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.side_effect = httpx.RequestError("Connection failed")
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        with pytest.raises(ToolError, match="Network error"):
            await ucr_info_fn()


@pytest.mark.asyncio
async def test_ucr_info_homicide_offense():
    """Test getting info for homicide offense."""
    mock_response = MockResponse(200, SAMPLE_MODELS_RESPONSE)

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = await ucr_info_fn(offense="homicide")

        assert "Homicide Forecasting Model" in result
        assert "Prophet" in result
        assert "91.8%" in result  # 100 - 8.2


@pytest.mark.asyncio
async def test_ucr_info_burglary_offense():
    """Test getting info for burglary offense."""
    mock_response = MockResponse(200, SAMPLE_MODELS_RESPONSE)

    with patch("tools.ucr_info.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = await ucr_info_fn(offense="burglary")

        assert "Burglary Forecasting Model" in result
        assert "ARIMA" in result
        assert "92.3%" in result  # 100 - 7.7
