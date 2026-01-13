"""Generate crime predictions using FBI UCR data and time-series models.

Returns forecasts with confidence intervals for violent-crime, property-crime,
homicide, burglary, or motor-vehicle-theft.

SUPPORTED SCOPE:
- Geographic: National level + 5 states (CA, TX, FL, NY, IL)
- Offenses: violent-crime, property-crime, homicide, burglary, motor-vehicle-theft
- Time horizon: 1-12 months ahead
- Data source: FBI Uniform Crime Reporting (UCR) Program
- Training data: January 2020 - October 2024

NOT SUPPORTED:
- Other states (coming soon)
- City/county level predictions
- Other offense types (robbery, aggravated assault, larceny, arson)
- Real-time data (data has ~2 month lag)
- Demographic breakdowns
"""

from datetime import datetime
from typing import Annotated

import httpx
from fastmcp.exceptions import ToolError
from pydantic import Field

from core.app import mcp

# Constants
BASE_URL = "https://fbi-ucr-fbi-ucr.apps.cluster-tw52m.tw52m.sandbox448.opentlc.com"
VALID_OFFENSES = frozenset([
    "violent-crime",
    "property-crime",
    "homicide",
    "burglary",
    "motor-vehicle-theft",
])

# Supported states for state-level predictions
VALID_STATES = frozenset(["CA", "TX", "FL", "NY", "IL"])

# State name mapping for display
STATE_NAMES = {
    "CA": "California",
    "TX": "Texas",
    "FL": "Florida",
    "NY": "New York",
    "IL": "Illinois",
}

# Mapping for fuzzy matching (common variations -> canonical form)
OFFENSE_ALIASES = {
    # violent-crime variations
    "violent_crime": "violent-crime",
    "violentcrime": "violent-crime",
    "violent": "violent-crime",
    # property-crime variations
    "property_crime": "property-crime",
    "propertycrime": "property-crime",
    "property": "property-crime",
    # homicide variations
    "murder": "homicide",
    "homicides": "homicide",
    # burglary variations
    "burglaries": "burglary",
    "break-in": "burglary",
    "breaking-and-entering": "burglary",
    # motor-vehicle-theft variations
    "motor_vehicle_theft": "motor-vehicle-theft",
    "motorvehicletheft": "motor-vehicle-theft",
    "vehicle-theft": "motor-vehicle-theft",
    "car-theft": "motor-vehicle-theft",
    "auto-theft": "motor-vehicle-theft",
    "mvt": "motor-vehicle-theft",
}

# Request timeout in seconds
REQUEST_TIMEOUT = 30.0


def normalize_offense(offense: str) -> str:
    """Normalize offense name using fuzzy matching.

    Args:
        offense: The offense name to normalize

    Returns:
        The canonical offense name

    Raises:
        ToolError: If the offense cannot be matched
    """
    cleaned = offense.lower().strip()

    # Check if it's already a valid offense
    if cleaned in VALID_OFFENSES:
        return cleaned

    # Try alias lookup
    if cleaned in OFFENSE_ALIASES:
        return OFFENSE_ALIASES[cleaned]

    # Build helpful error message
    valid_list = ", ".join(sorted(VALID_OFFENSES))
    raise ToolError(
        f"Unknown offense type: '{offense}'. "
        f"Valid options are: {valid_list}. "
        f"Tip: Use hyphens instead of underscores (e.g., 'violent-crime' not 'violent_crime')."
    )


def format_month(date_str: str) -> str:
    """Format date string (YYYY-MM or YYYY-MM-DD) to 'Mon YYYY' format.

    Args:
        date_str: Date string in YYYY-MM or YYYY-MM-DD format

    Returns:
        Formatted string like "Jan 2025"
    """
    try:
        # Handle YYYY-MM format
        if len(date_str) == 7:
            dt = datetime.strptime(date_str, "%Y-%m")
        else:
            # Handle YYYY-MM-DD format
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%b %Y")
    except ValueError:
        # Return original if parsing fails
        return date_str


def determine_trend(predictions: list[dict]) -> tuple[str, float]:
    """Determine the trend direction and percent change from predictions.

    Args:
        predictions: List of prediction dictionaries with 'predicted' values

    Returns:
        Tuple of (trend_description, percent_change)
    """
    if len(predictions) < 2:
        return "Stable", 0.0

    first_value = predictions[0].get("predicted", 0)
    last_value = predictions[-1].get("predicted", 0)

    if first_value == 0:
        return "Stable", 0.0

    percent_change = ((last_value - first_value) / first_value) * 100

    if percent_change > 5:
        return "Increasing", percent_change
    elif percent_change < -5:
        return "Decreasing", percent_change
    else:
        return "Stable", percent_change


def format_number(value: float) -> str:
    """Format a number with thousands separators.

    Args:
        value: The number to format

    Returns:
        Formatted string with commas
    """
    return f"{int(round(value)):,}"


def normalize_state(state: str | None) -> str | None:
    """Normalize state code to uppercase.

    Args:
        state: The state code to normalize (or None)

    Returns:
        Normalized state code (uppercase) or None

    Raises:
        ToolError: If the state is not valid
    """
    if state is None:
        return None

    cleaned = state.upper().strip()

    if cleaned in VALID_STATES:
        return cleaned

    # Build helpful error message
    valid_list = ", ".join(sorted(VALID_STATES))
    raise ToolError(
        f"Unknown state code: '{state}'. "
        f"Valid options are: {valid_list}. "
        f"Use 2-letter state codes (e.g., 'CA' for California)."
    )


def format_summary(
    offense: str,
    months_ahead: int,
    predictions: list[dict],
    model_info: dict,
    history: list[dict] | None = None,
    state: str | None = None,
) -> str:
    """Format forecast data as a human-readable summary.

    Args:
        offense: The offense type
        months_ahead: Number of months forecasted
        predictions: List of prediction dictionaries
        model_info: Model metadata dictionary
        history: Optional list of historical data points
        state: Optional state code for state-level forecast

    Returns:
        Formatted summary string
    """
    lines = []

    # Header - include state if provided
    offense_display = offense.replace("-", " ").title()
    if state:
        location = STATE_NAMES.get(state, state)
        lines.append(f"{offense_display} Forecast ({location}, next {months_ahead} months):")
    else:
        lines.append(f"{offense_display} Forecast (National, next {months_ahead} months):")
    lines.append("")

    # Include history if provided
    if history:
        lines.append("Recent History:")
        for entry in history[-3:]:  # Last 3 months of history
            month = format_month(entry.get("date", entry.get("month", "")))
            # API returns 'actual' field for historical incidents
            incidents = format_number(entry.get("actual", entry.get("incidents", entry.get("value", 0))))
            lines.append(f"- {month}: {incidents}")
        lines.append("")

    # Predictions
    lines.append("Predicted Incidents:")
    for pred in predictions:
        month = format_month(pred.get("date", pred.get("month", "")))
        predicted = format_number(pred.get("predicted", 0))
        lower = format_number(pred.get("lower", pred.get("lower_bound", 0)))
        upper = format_number(pred.get("upper", pred.get("upper_bound", 0)))
        lines.append(f"- {month}: ~{predicted} (range: {lower} - {upper})")

    lines.append("")

    # Trend analysis
    trend, percent_change = determine_trend(predictions)
    lines.append(f"Trend: {trend} ({percent_change:+.1f}%)")

    # Model info
    model_type = model_info.get("model_type", model_info.get("model", "Unknown"))
    mape = model_info.get("mape", model_info.get("error_rate", 0))
    accuracy = 100 - mape if mape else model_info.get("accuracy", 0)
    training_end = format_month(model_info.get("training_end", model_info.get("data_through", "")))

    lines.append(f"Model: {model_type} | Accuracy: {accuracy:.1f}% | Data through: {training_end}")

    return "\n".join(lines)


def format_detailed(
    offense: str,
    months_ahead: int,
    predictions: list[dict],
    model_info: dict,
    history: list[dict] | None = None,
    state: str | None = None,
    explanation: dict | None = None,
) -> str:
    """Format forecast data as detailed JSON-like output.

    Args:
        offense: The offense type
        months_ahead: Number of months forecasted
        predictions: List of prediction dictionaries
        model_info: Model metadata dictionary
        history: Optional list of historical data points
        state: Optional state code for state-level forecast
        explanation: Optional explanation data from API

    Returns:
        Formatted detailed JSON string
    """
    import json

    trend, percent_change = determine_trend(predictions)

    result = {
        "offense": offense,
        "location": state if state else "national",
        "months_forecasted": months_ahead,
        "predictions": predictions,
        "trend": {
            "direction": trend,
            "percent_change": round(percent_change, 2),
        },
        "model": model_info,
    }

    if history:
        result["history"] = history

    # Include explanation in detailed format
    if explanation:
        result["explanation"] = explanation

    return json.dumps(result, indent=2)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ucr_forecast(
    offense: Annotated[
        str,
        Field(
            description=(
                "Crime type to forecast. Must be one of: violent-crime, "
                "property-crime, homicide, burglary, motor-vehicle-theft"
            )
        ),
    ],
    months_ahead: Annotated[
        int,
        Field(
            default=6,
            ge=1,
            le=12,
            description="How many months to forecast (1-12, default: 6)",
        ),
    ] = 6,
    include_history: Annotated[
        bool,
        Field(
            default=False,
            description="Include recent historical data for context",
        ),
    ] = False,
    format: Annotated[
        str,
        Field(
            default="summary",
            description="Output format: 'summary' for prose, 'detailed' for full JSON",
        ),
    ] = "summary",
    state: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "State code for state-level forecast (CA, TX, FL, NY, IL). "
                "If omitted, returns national-level forecast."
            ),
        ),
    ] = None,
) -> str:
    """Generate crime predictions using FBI UCR data and time-series models.

    Returns forecasts with confidence intervals for violent-crime, property-crime,
    homicide, burglary, or motor-vehicle-theft. Supports both national and state-level
    forecasts for California, Texas, Florida, New York, and Illinois.

    Args:
        offense: Crime type to forecast (e.g., 'violent-crime', 'homicide')
        months_ahead: Number of months to forecast (1-12)
        include_history: Whether to include recent historical data
        format: Output format - 'summary' or 'detailed'
        state: Optional state code (CA, TX, FL, NY, IL) for state-level forecast

    Returns:
        Forecast results in the requested format

    Raises:
        ToolError: If validation fails or the API is unavailable
    """
    # Validate and normalize offense
    normalized_offense = normalize_offense(offense)

    # Validate and normalize state if provided
    normalized_state = normalize_state(state)

    # Validate months_ahead (Pydantic handles this, but belt and suspenders)
    if not 1 <= months_ahead <= 12:
        raise ToolError(
            f"months_ahead must be between 1 and 12, got {months_ahead}. "
            "For forecasts beyond 12 months, accuracy decreases significantly."
        )

    # Validate format
    format_lower = format.lower().strip()
    if format_lower not in ("summary", "detailed"):
        raise ToolError(
            f"Invalid format '{format}'. Use 'summary' for prose output or "
            "'detailed' for full JSON data."
        )

    # Make API requests
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        # Build query params for state-level requests
        query_params = {}
        if normalized_state:
            query_params["state"] = normalized_state

        # Get predictions
        try:
            predict_url = f"{BASE_URL}/api/v1/predict/{normalized_offense}"
            predict_response = await client.post(
                predict_url,
                json={"months": months_ahead},
                params=query_params,
            )
            predict_response.raise_for_status()
            predict_data = predict_response.json()
        except httpx.TimeoutException:
            raise ToolError(
                "The FBI UCR prediction service is not responding. "
                "Please try again later or check service status."
            )
        except httpx.HTTPStatusError as e:
            location = STATE_NAMES.get(normalized_state, normalized_state) if normalized_state else "national"
            if e.response.status_code == 404:
                raise ToolError(
                    f"No prediction model found for '{normalized_offense}' ({location}). "
                    f"The model may not be available yet."
                )
            elif e.response.status_code >= 500:
                raise ToolError(
                    "The FBI UCR prediction service is experiencing issues. "
                    "Please try again later."
                )
            else:
                raise ToolError(
                    f"Failed to get predictions: {e.response.status_code} - "
                    f"{e.response.text}"
                )
        except httpx.RequestError as e:
            raise ToolError(
                f"Could not connect to the FBI UCR prediction service: {str(e)}. "
                "The service may be temporarily unavailable."
            )

        # Get history if requested
        history_data = None
        if include_history:
            try:
                history_url = f"{BASE_URL}/api/v1/history/{normalized_offense}"
                history_params = {"months": 6}  # Get last 6 months of history
                if normalized_state:
                    history_params["state"] = normalized_state
                history_response = await client.get(
                    history_url,
                    params=history_params,
                )
                history_response.raise_for_status()
                history_data = history_response.json()
            except (httpx.HTTPStatusError, httpx.RequestError):
                # History is optional, don't fail if it's not available
                history_data = None

    # Extract predictions and model info from response
    predictions = predict_data.get("predictions", predict_data.get("forecast", []))
    # API returns metadata in 'metadata' key, not 'model' or 'model_info'
    model_info = predict_data.get("metadata", predict_data.get("model", predict_data.get("model_info", {})))
    # Extract explanation (available in detailed format)
    explanation = predict_data.get("explanation")

    # Handle case where history_data might be a dict with a 'history' key
    if isinstance(history_data, dict):
        history_data = history_data.get("history", history_data.get("data", []))

    # Format output
    if format_lower == "summary":
        return format_summary(
            offense=normalized_offense,
            months_ahead=months_ahead,
            predictions=predictions,
            model_info=model_info,
            history=history_data if include_history else None,
            state=normalized_state,
        )
    else:
        return format_detailed(
            offense=normalized_offense,
            months_ahead=months_ahead,
            predictions=predictions,
            model_info=model_info,
            history=history_data if include_history else None,
            state=normalized_state,
            explanation=explanation,
        )
