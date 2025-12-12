"""Tests for ucr_compare tool."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from fastmcp.exceptions import ToolError
from tools.ucr_compare import (
    ucr_compare,
    normalize_offense,
    format_offense_name,
    calculate_percent_change,
    format_comparison_output,
    VALID_OFFENSES,
)

# Access the underlying function for testing (FastMCP decorator pattern)
ucr_compare_fn = ucr_compare.fn


# --- Fixtures for mock API responses ---


@pytest.fixture
def mock_prediction_violent_crime():
    """Mock prediction response for violent-crime."""
    return {
        "offense": "violent-crime",
        "predictions": [
            {"date": "2025-01", "predicted": 85000, "lower": 80000, "upper": 90000},
            {"date": "2025-02", "predicted": 85100, "lower": 79000, "upper": 91000},
            {"date": "2025-03", "predicted": 85200, "lower": 78000, "upper": 92000},
            {"date": "2025-04", "predicted": 85300, "lower": 77000, "upper": 93000},
            {"date": "2025-05", "predicted": 85400, "lower": 76000, "upper": 94000},
            {"date": "2025-06", "predicted": 84800, "lower": 75000, "upper": 95000},
        ],
        "metadata": {
            "model_type": "ARIMA",
            "mape": 9.0,
            "training_end": "Dec 2024",
        },
    }


@pytest.fixture
def mock_history_violent_crime():
    """Mock history response for violent-crime."""
    return {
        "offense": "violent-crime",
        "data": [
            {"date": "2024-12", "count": 85000},
        ],
    }


@pytest.fixture
def mock_prediction_property_crime():
    """Mock prediction response for property-crime."""
    return {
        "offense": "property-crime",
        "predictions": [
            {"date": "2025-01", "predicted": 250000, "lower": 240000, "upper": 260000},
            {"date": "2025-02", "predicted": 249000, "lower": 238000, "upper": 261000},
            {"date": "2025-03", "predicted": 248000, "lower": 236000, "upper": 262000},
            {"date": "2025-04", "predicted": 247000, "lower": 234000, "upper": 263000},
            {"date": "2025-05", "predicted": 246000, "lower": 232000, "upper": 264000},
            {"date": "2025-06", "predicted": 245000, "lower": 230000, "upper": 265000},
        ],
        "metadata": {
            "model_type": "ARIMA",
            "mape": 7.9,
            "training_end": "Dec 2024",
        },
    }


@pytest.fixture
def mock_history_property_crime():
    """Mock history response for property-crime."""
    return {
        "offense": "property-crime",
        "data": [
            {"date": "2024-12", "count": 250000},
        ],
    }


@pytest.fixture
def mock_prediction_homicide():
    """Mock prediction response for homicide."""
    return {
        "offense": "homicide",
        "predictions": [
            {"date": "2025-01", "predicted": 1500, "lower": 1400, "upper": 1600},
            {"date": "2025-02", "predicted": 1480, "lower": 1350, "upper": 1610},
            {"date": "2025-03", "predicted": 1460, "lower": 1300, "upper": 1620},
            {"date": "2025-04", "predicted": 1440, "lower": 1250, "upper": 1630},
            {"date": "2025-05", "predicted": 1420, "lower": 1200, "upper": 1640},
            {"date": "2025-06", "predicted": 1400, "lower": 1150, "upper": 1650},
        ],
        "metadata": {
            "model_type": "Prophet",
            "mape": 8.2,
            "training_end": "Dec 2024",
        },
    }


@pytest.fixture
def mock_history_homicide():
    """Mock history response for homicide."""
    return {
        "offense": "homicide",
        "data": [
            {"date": "2024-12", "count": 1500},
        ],
    }


@pytest.fixture
def mock_prediction_burglary():
    """Mock prediction response for burglary."""
    return {
        "offense": "burglary",
        "predictions": [
            {"date": "2025-01", "predicted": 100000, "lower": 95000, "upper": 105000},
            {"date": "2025-02", "predicted": 99000, "lower": 93000, "upper": 106000},
            {"date": "2025-03", "predicted": 98000, "lower": 91000, "upper": 107000},
            {"date": "2025-04", "predicted": 97000, "lower": 89000, "upper": 108000},
            {"date": "2025-05", "predicted": 96000, "lower": 87000, "upper": 109000},
            {"date": "2025-06", "predicted": 95000, "lower": 85000, "upper": 110000},
        ],
        "metadata": {
            "model_type": "ARIMA",
            "mape": 7.7,
            "training_end": "Dec 2024",
        },
    }


@pytest.fixture
def mock_history_burglary():
    """Mock history response for burglary."""
    return {
        "offense": "burglary",
        "data": [
            {"date": "2024-12", "count": 100000},
        ],
    }


@pytest.fixture
def mock_prediction_mvt():
    """Mock prediction response for motor-vehicle-theft with significant increase."""
    return {
        "offense": "motor-vehicle-theft",
        "predictions": [
            {"date": "2025-01", "predicted": 72000, "lower": 68000, "upper": 76000},
            {"date": "2025-02", "predicted": 74000, "lower": 69000, "upper": 79000},
            {"date": "2025-03", "predicted": 76000, "lower": 70000, "upper": 82000},
            {"date": "2025-04", "predicted": 78000, "lower": 71000, "upper": 85000},
            {"date": "2025-05", "predicted": 80000, "lower": 72000, "upper": 88000},
            {"date": "2025-06", "predicted": 83822, "lower": 73000, "upper": 95000},
        ],
        "metadata": {
            "model_type": "SARIMA",
            "mape": 5.4,
            "training_end": "Dec 2024",
        },
    }


@pytest.fixture
def mock_history_mvt():
    """Mock history response for motor-vehicle-theft."""
    return {
        "offense": "motor-vehicle-theft",
        "data": [
            {"date": "2024-12", "count": 70000},
        ],
    }


def create_mock_response(json_data):
    """Create a mock httpx response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json_data
    mock_response.raise_for_status = MagicMock()
    return mock_response


# --- Unit Tests for Helper Functions ---


class TestNormalizeOffense:
    """Tests for normalize_offense function."""

    def test_valid_offenses(self):
        """Test that valid offenses are returned unchanged."""
        for offense in VALID_OFFENSES:
            assert normalize_offense(offense) == offense

    def test_alias_violent(self):
        """Test violent crime aliases."""
        assert normalize_offense("violent") == "violent-crime"
        assert normalize_offense("violent crime") == "violent-crime"
        assert normalize_offense("violent_crime") == "violent-crime"

    def test_alias_property(self):
        """Test property crime aliases."""
        assert normalize_offense("property") == "property-crime"
        assert normalize_offense("property crime") == "property-crime"
        assert normalize_offense("property_crime") == "property-crime"

    def test_alias_homicide(self):
        """Test homicide aliases."""
        assert normalize_offense("murder") == "homicide"

    def test_alias_mvt(self):
        """Test motor vehicle theft aliases."""
        assert normalize_offense("mvt") == "motor-vehicle-theft"
        assert normalize_offense("vehicle theft") == "motor-vehicle-theft"
        assert normalize_offense("car theft") == "motor-vehicle-theft"

    def test_case_insensitive(self):
        """Test that normalization is case insensitive."""
        assert normalize_offense("VIOLENT-CRIME") == "violent-crime"
        assert normalize_offense("Property-Crime") == "property-crime"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        assert normalize_offense("  homicide  ") == "homicide"

    def test_invalid_offense_raises(self):
        """Test that invalid offenses raise ValueError."""
        with pytest.raises(ValueError):
            normalize_offense("invalid-offense")


class TestFormatOffenseName:
    """Tests for format_offense_name function."""

    def test_formats_correctly(self):
        """Test offense name formatting."""
        assert format_offense_name("violent-crime") == "Violent Crime"
        assert format_offense_name("property-crime") == "Property Crime"
        assert format_offense_name("motor-vehicle-theft") == "Motor Vehicle Theft"
        assert format_offense_name("homicide") == "Homicide"
        assert format_offense_name("burglary") == "Burglary"


class TestCalculatePercentChange:
    """Tests for calculate_percent_change function."""

    def test_positive_change(self):
        """Test positive percent change."""
        assert calculate_percent_change(100, 110) == 10.0

    def test_negative_change(self):
        """Test negative percent change."""
        assert calculate_percent_change(100, 90) == -10.0

    def test_no_change(self):
        """Test no percent change."""
        assert calculate_percent_change(100, 100) == 0.0

    def test_zero_current(self):
        """Test with zero current value."""
        assert calculate_percent_change(0, 0) == 0.0
        assert calculate_percent_change(0, 100) == float("inf")


# --- Integration Tests with Mocked HTTP ---


@pytest.mark.asyncio
async def test_ucr_compare_two_offenses(
    mock_prediction_violent_crime,
    mock_history_violent_crime,
    mock_prediction_property_crime,
    mock_history_property_crime,
):
    """Test comparing 2 offenses."""

    def route_request(url, **kwargs):
        """Route mock request based on URL."""
        if "predict/violent-crime" in url:
            return create_mock_response(mock_prediction_violent_crime)
        elif "history/violent-crime" in url:
            return create_mock_response(mock_history_violent_crime)
        elif "predict/property-crime" in url:
            return create_mock_response(mock_prediction_property_crime)
        elif "history/property-crime" in url:
            return create_mock_response(mock_history_property_crime)
        raise ValueError(f"Unexpected URL: {url}")

    with patch("tools.ucr_compare.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = route_request
        mock_client.get.side_effect = route_request
        mock_client_class.return_value = mock_client

        result = await ucr_compare_fn(
            offenses=["violent-crime", "property-crime"],
            months_ahead=6,
            metric="percent_change",
        )

        # Verify output contains expected elements
        assert "Crime Trend Comparison (6-month forecast):" in result
        assert "Violent Crime" in result
        assert "Property Crime" in result
        assert "ARIMA" in result
        assert "Dec 2024" in result


@pytest.mark.asyncio
async def test_ucr_compare_five_offenses(
    mock_prediction_violent_crime,
    mock_history_violent_crime,
    mock_prediction_property_crime,
    mock_history_property_crime,
    mock_prediction_homicide,
    mock_history_homicide,
    mock_prediction_burglary,
    mock_history_burglary,
    mock_prediction_mvt,
    mock_history_mvt,
):
    """Test comparing 5 offenses (maximum)."""

    def route_request(url, **kwargs):
        """Route mock request based on URL."""
        if "predict/violent-crime" in url:
            return create_mock_response(mock_prediction_violent_crime)
        elif "history/violent-crime" in url:
            return create_mock_response(mock_history_violent_crime)
        elif "predict/property-crime" in url:
            return create_mock_response(mock_prediction_property_crime)
        elif "history/property-crime" in url:
            return create_mock_response(mock_history_property_crime)
        elif "predict/homicide" in url:
            return create_mock_response(mock_prediction_homicide)
        elif "history/homicide" in url:
            return create_mock_response(mock_history_homicide)
        elif "predict/burglary" in url:
            return create_mock_response(mock_prediction_burglary)
        elif "history/burglary" in url:
            return create_mock_response(mock_history_burglary)
        elif "predict/motor-vehicle-theft" in url:
            return create_mock_response(mock_prediction_mvt)
        elif "history/motor-vehicle-theft" in url:
            return create_mock_response(mock_history_mvt)
        raise ValueError(f"Unexpected URL: {url}")

    with patch("tools.ucr_compare.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = route_request
        mock_client.get.side_effect = route_request
        mock_client_class.return_value = mock_client

        result = await ucr_compare_fn(
            offenses=[
                "violent-crime",
                "property-crime",
                "homicide",
                "burglary",
                "motor-vehicle-theft",
            ],
            months_ahead=6,
            metric="percent_change",
        )

        # Verify output contains all offenses
        assert "Violent Crime" in result
        assert "Property Crime" in result
        assert "Homicide" in result
        assert "Burglary" in result
        assert "Motor Vehicle Theft" in result

        # Motor vehicle theft has >10% increase, should show warning
        assert "\u26a0\ufe0f" in result or "warning" in result.lower()


@pytest.mark.asyncio
async def test_ucr_compare_absolute_metric(
    mock_prediction_violent_crime,
    mock_history_violent_crime,
    mock_prediction_property_crime,
    mock_history_property_crime,
):
    """Test with absolute metric (no percent change column)."""

    def route_request(url, **kwargs):
        """Route mock request based on URL."""
        if "predict/violent-crime" in url:
            return create_mock_response(mock_prediction_violent_crime)
        elif "history/violent-crime" in url:
            return create_mock_response(mock_history_violent_crime)
        elif "predict/property-crime" in url:
            return create_mock_response(mock_prediction_property_crime)
        elif "history/property-crime" in url:
            return create_mock_response(mock_history_property_crime)
        raise ValueError(f"Unexpected URL: {url}")

    with patch("tools.ucr_compare.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = route_request
        mock_client.get.side_effect = route_request
        mock_client_class.return_value = mock_client

        result = await ucr_compare_fn(
            offenses=["violent-crime", "property-crime"],
            months_ahead=6,
            metric="absolute",
        )

        # Should NOT contain Change column header for absolute metric
        assert "Change" not in result.split("\n")[2]  # Header row
        assert "Current" in result
        assert "Forecast" in result


@pytest.mark.asyncio
async def test_ucr_compare_with_significant_change_warning(
    mock_prediction_violent_crime,
    mock_history_violent_crime,
    mock_prediction_mvt,
    mock_history_mvt,
):
    """Test that significant changes (>10%) show warning."""

    def route_request(url, **kwargs):
        """Route mock request based on URL."""
        if "predict/violent-crime" in url:
            return create_mock_response(mock_prediction_violent_crime)
        elif "history/violent-crime" in url:
            return create_mock_response(mock_history_violent_crime)
        elif "predict/motor-vehicle-theft" in url:
            return create_mock_response(mock_prediction_mvt)
        elif "history/motor-vehicle-theft" in url:
            return create_mock_response(mock_history_mvt)
        raise ValueError(f"Unexpected URL: {url}")

    with patch("tools.ucr_compare.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = route_request
        mock_client.get.side_effect = route_request
        mock_client_class.return_value = mock_client

        result = await ucr_compare_fn(
            offenses=["violent-crime", "motor-vehicle-theft"],
            months_ahead=6,
            metric="percent_change",
        )

        # Motor vehicle theft has >10% increase (70000 -> 83822 = +19.7%)
        assert "Motor Vehicle Theft shows significant projected increase" in result


# --- Error Handling Tests ---


@pytest.mark.asyncio
async def test_ucr_compare_too_few_offenses():
    """Test error when less than 2 offenses provided."""
    with pytest.raises(ToolError) as exc_info:
        await ucr_compare_fn(
            offenses=["violent-crime"],
            months_ahead=6,
            metric="percent_change",
        )

    assert "At least 2 offenses are required" in str(exc_info.value)
    assert "You provided 1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ucr_compare_too_many_offenses():
    """Test error when more than 5 offenses provided."""
    with pytest.raises(ToolError) as exc_info:
        await ucr_compare_fn(
            offenses=[
                "violent-crime",
                "property-crime",
                "homicide",
                "burglary",
                "motor-vehicle-theft",
                "violent-crime",  # 6th offense
            ],
            months_ahead=6,
            metric="percent_change",
        )

    assert "Maximum 5 offenses" in str(exc_info.value)
    assert "You provided 6" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ucr_compare_empty_offenses_list():
    """Test error when empty offenses list provided."""
    with pytest.raises(ToolError) as exc_info:
        await ucr_compare_fn(
            offenses=[],
            months_ahead=6,
            metric="percent_change",
        )

    assert "At least 2 offenses are required" in str(exc_info.value)
    assert "You provided 0" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ucr_compare_invalid_offense():
    """Test error when invalid offense is in the list."""
    with pytest.raises(ToolError) as exc_info:
        await ucr_compare_fn(
            offenses=["violent-crime", "invalid-offense"],
            months_ahead=6,
            metric="percent_change",
        )

    assert "Invalid offense(s)" in str(exc_info.value)
    assert '"invalid-offense" is not recognized' in str(exc_info.value)


@pytest.mark.asyncio
async def test_ucr_compare_underscore_suggestion():
    """Test that underscore offense names get helpful suggestion."""
    # Note: violent_crime and property_crime are aliases that work
    # Let's test with an underscore name that doesn't have an alias
    with pytest.raises(ToolError) as exc_info:
        await ucr_compare_fn(
            offenses=["violent-crime", "burglary_crime"],  # burglary_crime isn't an alias
            months_ahead=6,
            metric="percent_change",
        )

    error_msg = str(exc_info.value)
    assert "is not recognized" in error_msg
    assert "Use hyphens, not underscores" in error_msg


@pytest.mark.asyncio
async def test_ucr_compare_api_unavailable():
    """Test error handling when API is unavailable."""

    def raise_connect_error(url, **kwargs):
        """Raise connection error for any request."""
        raise httpx.ConnectError("Connection refused")

    with patch("tools.ucr_compare.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = raise_connect_error
        mock_client.get.side_effect = raise_connect_error
        mock_client_class.return_value = mock_client

        with pytest.raises(ToolError) as exc_info:
            await ucr_compare_fn(
                offenses=["violent-crime", "property-crime"],
                months_ahead=6,
                metric="percent_change",
            )

        assert "temporarily unavailable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ucr_compare_offense_aliases(
    mock_prediction_violent_crime,
    mock_history_violent_crime,
    mock_prediction_property_crime,
    mock_history_property_crime,
):
    """Test that offense aliases work correctly."""

    def route_request(url, **kwargs):
        """Route mock request based on URL."""
        if "predict/violent-crime" in url:
            return create_mock_response(mock_prediction_violent_crime)
        elif "history/violent-crime" in url:
            return create_mock_response(mock_history_violent_crime)
        elif "predict/property-crime" in url:
            return create_mock_response(mock_prediction_property_crime)
        elif "history/property-crime" in url:
            return create_mock_response(mock_history_property_crime)
        raise ValueError(f"Unexpected URL: {url}")

    with patch("tools.ucr_compare.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = route_request
        mock_client.get.side_effect = route_request
        mock_client_class.return_value = mock_client

        # Use aliases instead of canonical names
        result = await ucr_compare_fn(
            offenses=["violent", "property"],  # aliases
            months_ahead=6,
            metric="percent_change",
        )

        # Should work and show proper names
        assert "Violent Crime" in result
        assert "Property Crime" in result


# --- Format Output Tests ---


class TestFormatComparisonOutput:
    """Tests for format_comparison_output function."""

    def test_format_with_no_data(self):
        """Test formatting with empty results (all errors)."""
        results = [
            ("violent-crime", None, None, "API error: 500"),
            ("property-crime", None, None, "Connection timeout"),
        ]
        output = format_comparison_output(results, 6, "percent_change")

        assert "Crime Trend Comparison" in output
        assert "Error:" in output

    def test_format_with_partial_data(self):
        """Test formatting when some requests succeed and some fail."""
        results = [
            (
                "violent-crime",
                {
                    "predictions": [{"predicted": 85000}],
                    "metadata": {"model_type": "ARIMA", "training_end": "Dec 2024"},
                },
                {"data": [{"count": 84000}]},
                None,
            ),
            ("property-crime", None, None, "API error: 500"),
        ]
        output = format_comparison_output(results, 6, "percent_change")

        assert "Violent Crime" in output
        assert "Error: Property Crime: API error: 500" in output
