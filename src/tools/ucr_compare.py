"""Compare crime trend forecasts across multiple offense types.

Returns side-by-side comparison with percent change and highlights significant changes.

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

import asyncio
from typing import Literal

import httpx
from fastmcp.exceptions import ToolError
from pydantic import Field

from core.app import mcp

# Backend API configuration
API_BASE = "https://fbi-ucr-fbi-ucr.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com"

# Valid offense types
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

# Common aliases for offense names
OFFENSE_ALIASES: dict[str, str] = {
    "violent": "violent-crime",
    "violent crime": "violent-crime",
    "violent_crime": "violent-crime",
    "property": "property-crime",
    "property crime": "property-crime",
    "property_crime": "property-crime",
    "murder": "homicide",
    "mvt": "motor-vehicle-theft",
    "vehicle theft": "motor-vehicle-theft",
    "vehicle-theft": "motor-vehicle-theft",
    "car theft": "motor-vehicle-theft",
    "motor vehicle theft": "motor-vehicle-theft",
    "motor_vehicle_theft": "motor-vehicle-theft",
}


def normalize_offense(offense: str) -> str:
    """Normalize offense name to valid API format.

    Args:
        offense: User-provided offense name

    Returns:
        Normalized offense name

    Raises:
        ValueError: If offense is not recognized
    """
    normalized = offense.lower().strip()
    if normalized in VALID_OFFENSES:
        return normalized
    if normalized in OFFENSE_ALIASES:
        return OFFENSE_ALIASES[normalized]
    raise ValueError(offense)


def normalize_state(state: str | None) -> str | None:
    """Normalize state code to uppercase.

    Args:
        state: The state code to normalize (or None)

    Returns:
        Normalized state code (uppercase) or None

    Raises:
        ValueError: If the state is not valid
    """
    if state is None:
        return None

    cleaned = state.upper().strip()

    if cleaned in VALID_STATES:
        return cleaned

    raise ValueError(state)


def format_offense_name(offense: str) -> str:
    """Format offense name for display (e.g., 'motor-vehicle-theft' -> 'Motor Vehicle Theft').

    Args:
        offense: API offense name with hyphens

    Returns:
        Human-readable offense name
    """
    return offense.replace("-", " ").title()


async def fetch_prediction(
    client: httpx.AsyncClient,
    offense: str,
    months: int,
    state: str | None = None,
) -> dict:
    """Fetch prediction from the API.

    Args:
        client: HTTP client
        offense: Normalized offense name
        months: Number of months to forecast
        state: Optional state code for state-level prediction

    Returns:
        API response as dict

    Raises:
        httpx.HTTPError: If request fails
    """
    params = {}
    if state:
        params["state"] = state

    response = await client.post(
        f"{API_BASE}/api/v1/predict/{offense}",
        json={"months": months},
        params=params,
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


async def fetch_history(
    client: httpx.AsyncClient,
    offense: str,
    months: int = 1,
    state: str | None = None,
) -> dict:
    """Fetch historical data from the API.

    Args:
        client: HTTP client
        offense: Normalized offense name
        months: Number of months of history to retrieve
        state: Optional state code for state-level history

    Returns:
        API response as dict

    Raises:
        httpx.HTTPError: If request fails
    """
    params = {"months": months}
    if state:
        params["state"] = state

    response = await client.get(
        f"{API_BASE}/api/v1/history/{offense}",
        params=params,
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


async def fetch_offense_data(
    client: httpx.AsyncClient,
    offense: str,
    months: int,
    state: str | None = None,
) -> tuple[str, dict | None, dict | None, str | None]:
    """Fetch both prediction and history for an offense.

    Args:
        client: HTTP client
        offense: Normalized offense name
        months: Number of months to forecast
        state: Optional state code for state-level data

    Returns:
        Tuple of (offense, prediction, history, error_message)
    """
    try:
        prediction, history = await asyncio.gather(
            fetch_prediction(client, offense, months, state),
            fetch_history(client, offense, 1, state),
        )
        return (offense, prediction, history, None)
    except httpx.HTTPStatusError as e:
        return (offense, None, None, f"API error: {e.response.status_code}")
    except httpx.TimeoutException:
        return (offense, None, None, "Request timed out")
    except httpx.RequestError as e:
        return (offense, None, None, f"Connection error: {str(e)}")


def calculate_percent_change(current: float, forecast: float) -> float:
    """Calculate percent change between current and forecast values.

    Args:
        current: Current value
        forecast: Forecast value

    Returns:
        Percent change
    """
    if current == 0:
        return 0.0 if forecast == 0 else float("inf")
    return ((forecast - current) / current) * 100


def format_comparison_output(
    results: list[tuple[str, dict | None, dict | None, str | None]],
    months_ahead: int,
    metric: str,
    state: str | None = None,
) -> str:
    """Format the comparison results as a human-readable string.

    Args:
        results: List of (offense, prediction, history, error) tuples
        months_ahead: Forecast horizon
        metric: 'absolute' or 'percent_change'
        state: Optional state code for state-level comparison

    Returns:
        Formatted comparison string
    """
    if state:
        location = STATE_NAMES.get(state, state)
        lines = [f"Crime Trend Comparison - {location} ({months_ahead}-month forecast):", ""]
    else:
        lines = [f"Crime Trend Comparison - National ({months_ahead}-month forecast):", ""]

    # Determine column widths
    offense_width = max(
        len(format_offense_name(offense)) for offense, _, _, _ in results
    )
    offense_width = max(offense_width, 22)  # Minimum width for header

    # Header row
    if metric == "percent_change":
        header = (
            f"{'':>{offense_width}}  "
            f"{'Current':>12}  "
            f"{f'{months_ahead}-Month Forecast':>18}  "
            f"{'Change':>10}"
        )
    else:
        header = (
            f"{'':>{offense_width}}  "
            f"{'Current':>12}  "
            f"{f'{months_ahead}-Month Forecast':>18}"
        )
    lines.append(header)

    # Track warnings and model info
    warnings = []
    models_info = {}
    training_ends = set()
    errors = []

    for offense, prediction, history, error in results:
        offense_display = format_offense_name(offense)

        if error:
            errors.append(f"{offense_display}: {error}")
            continue

        # Extract current value from history
        # API returns history data with 'actual' field, not 'count'
        if history and "data" in history and len(history["data"]) > 0:
            current_value = history["data"][-1].get("actual", history["data"][-1].get("count", 0))
        else:
            current_value = 0

        # Extract forecast value (last prediction in the series)
        if prediction and "predictions" in prediction and len(prediction["predictions"]) > 0:
            forecast_value = prediction["predictions"][-1].get("predicted", 0)
        else:
            forecast_value = 0

        # Track model information
        if prediction and "metadata" in prediction:
            metadata = prediction["metadata"]
            model_type = metadata.get("model_type", "Unknown")
            models_info[offense] = model_type
            if "training_end" in metadata:
                training_ends.add(metadata["training_end"])

        # Calculate percent change
        pct_change = calculate_percent_change(current_value, forecast_value)

        # Format row
        if metric == "percent_change":
            # Format change with sign
            if pct_change >= 0:
                change_str = f"+{pct_change:.1f}%"
            else:
                change_str = f"{pct_change:.1f}%"

            # Add warning indicator for significant changes (> 10%)
            if abs(pct_change) > 10:
                change_str += " \u26a0\ufe0f"
                warnings.append(
                    f"{offense_display} shows significant projected "
                    f"{'increase' if pct_change > 0 else 'decrease'}."
                )

            row = (
                f"{offense_display:>{offense_width}}  "
                f"{current_value:>12,.0f}  "
                f"{forecast_value:>18,.0f}  "
                f"{change_str:>10}"
            )
        else:
            row = (
                f"{offense_display:>{offense_width}}  "
                f"{current_value:>12,.0f}  "
                f"{forecast_value:>18,.0f}"
            )

        lines.append(row)

    # Add blank line before notes
    lines.append("")

    # Add warnings
    for warning in warnings:
        lines.append(f"\u26a0\ufe0f {warning}")

    if warnings:
        lines.append("")

    # Add errors if any
    for error_msg in errors:
        lines.append(f"Error: {error_msg}")

    if errors:
        lines.append("")

    # Add model/data info footer
    if models_info:
        # Build compact model info
        model_parts = []
        model_to_offenses: dict[str, list[str]] = {}
        for offense, model in models_info.items():
            if model not in model_to_offenses:
                model_to_offenses[model] = []
            # Use short names for compactness
            short_name = offense.replace("-crime", "").replace("-", " ")
            model_to_offenses[model].append(short_name)

        for model, offenses in model_to_offenses.items():
            model_parts.append(f"{model} ({', '.join(offenses)})")

        training_end = (
            list(training_ends)[0] if len(training_ends) == 1 else "varies"
        )

        lines.append(f"Models: {', '.join(model_parts)} | Data through: {training_end}")

    return "\n".join(lines)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ucr_compare(
    offenses: list[str] = Field(
        description=(
            "List of 2-5 offense types to compare. "
            "Valid values: violent-crime, property-crime, homicide, burglary, motor-vehicle-theft"
        ),
    ),
    months_ahead: int = Field(
        default=6,
        ge=1,
        le=12,
        description="Forecast horizon in months (1-12)",
    ),
    metric: Literal["absolute", "percent_change"] = Field(
        default="percent_change",
        description="'absolute' shows raw counts, 'percent_change' shows trends",
    ),
    state: str | None = Field(
        default=None,
        description=(
            "State code for state-level comparison (CA, TX, FL, NY, IL). "
            "If omitted, compares national-level data."
        ),
    ),
) -> str:
    """Compare crime trend forecasts across multiple offense types.

    Use this tool when you need to compare different types of crime or
    identify which categories are increasing/decreasing the most.
    Supports both national-level (default) and state-level comparisons.

    OFFENSES (provide 2-5 from this list):
    - violent-crime
    - property-crime
    - homicide
    - burglary
    - motor-vehicle-theft

    STATES (optional):
    - CA (California), TX (Texas), FL (Florida), NY (New York), IL (Illinois)
    - If omitted, compares national-level data

    PARAMETERS:
    - offenses: List of 2-5 offense types to compare (required)
    - months_ahead: Forecast horizon, 1-12 months (default: 6)
    - metric: "absolute" shows raw counts, "percent_change" shows trends (default: percent_change)
    - state: State code for state-level comparison (optional)

    WHY USE THIS:
    - Single call instead of multiple ucr_forecast calls
    - Side-by-side comparison table
    - Highlights significant changes with warnings

    EXAMPLE OUTPUT:
    ```
    Crime Trend Comparison - California (6-month forecast):

                          Current    6-Month Forecast   Change
    Violent Crime         85,000     84,800            -0.2%
    Property Crime        250,000    245,000           -2.0%
    Motor Vehicle Theft   70,000     83,822            +19.7% warning

    warning Motor vehicle theft shows significant projected increase.

    Models: ARIMA (violent, property), SARIMA (mvt) | Data through: Oct 2024
    ```

    Returns:
        Formatted comparison table with current values, forecasts, and changes

    Raises:
        ToolError: If validation fails or API is unavailable
    """
    # Validate offense count
    if len(offenses) < 2:
        raise ToolError(
            "At least 2 offenses are required for comparison. "
            f"You provided {len(offenses)}. "
            "Valid offenses: violent-crime, property-crime, homicide, burglary, motor-vehicle-theft"
        )

    if len(offenses) > 5:
        raise ToolError(
            "Maximum 5 offenses can be compared at once. "
            f"You provided {len(offenses)}. "
            "Please select up to 5 offenses from: violent-crime, property-crime, homicide, "
            "burglary, motor-vehicle-theft"
        )

    # Validate and normalize state if provided
    normalized_state = None
    if state is not None:
        try:
            normalized_state = normalize_state(state)
        except ValueError:
            valid_states = ", ".join(sorted(VALID_STATES))
            raise ToolError(
                f"Invalid state code: '{state}'. "
                f"Valid options are: {valid_states}. "
                "Use 2-letter state codes (e.g., 'CA' for California)."
            )

    # Normalize and validate each offense
    normalized_offenses = []
    invalid_offenses = []

    for offense in offenses:
        try:
            normalized = normalize_offense(offense)
            normalized_offenses.append(normalized)
        except ValueError:
            invalid_offenses.append(offense)

    if invalid_offenses:
        suggestions = []
        for invalid in invalid_offenses:
            # Try to suggest a correction
            invalid_lower = invalid.lower().strip()
            if "_" in invalid_lower:
                suggestion = invalid_lower.replace("_", "-")
                if suggestion in VALID_OFFENSES:
                    suggestions.append(f'"{invalid}" -> Did you mean "{suggestion}"?')
                    continue
            suggestions.append(f'"{invalid}" is not recognized')

        valid_list = ", ".join(sorted(VALID_OFFENSES))
        raise ToolError(
            f"Invalid offense(s) in list:\n"
            + "\n".join(f"  - {s}" for s in suggestions)
            + f"\n\nValid offenses: {valid_list}\n"
            "Note: Use hyphens, not underscores."
        )

    # Make parallel requests for all offenses
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_offense_data(client, offense, months_ahead, normalized_state)
            for offense in normalized_offenses
        ]
        results = await asyncio.gather(*tasks)

    # Check if all requests failed
    all_failed = all(error is not None for _, _, _, error in results)
    if all_failed:
        raise ToolError(
            "The FBI UCR prediction service is temporarily unavailable.\n\n"
            "This may be due to:\n"
            "- Scheduled maintenance\n"
            "- High demand\n"
            "- Network issues\n\n"
            "Try again in a few minutes. If the problem persists, the service "
            "may be experiencing an outage."
        )

    return format_comparison_output(results, months_ahead, metric, normalized_state)
