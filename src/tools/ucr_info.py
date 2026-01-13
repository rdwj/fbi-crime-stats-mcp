"""Get information about available FBI UCR crime forecasting models.

Lists all models or returns details for a specific offense including accuracy and methodology.

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

from typing import Annotated
import httpx
from fastmcp.exceptions import ToolError
from pydantic import Field
from core.app import mcp


# Base URL for the FBI UCR API
BASE_URL = "https://fbi-ucr-fbi-ucr.apps.cluster-tw52m.tw52m.sandbox448.opentlc.com"

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

# Static offense descriptions
OFFENSE_DESCRIPTIONS = {
    "violent-crime": "All violent crimes combined (murder, rape, robbery, assault)",
    "property-crime": "All property crimes combined (burglary, theft, vehicle theft)",
    "homicide": "Murder and non-negligent manslaughter",
    "burglary": "Unlawful entry to commit felony",
    "motor-vehicle-theft": "Theft or attempted theft of motor vehicles",
}

# Extended descriptions for detailed view
OFFENSE_DETAILS = {
    "violent-crime": {
        "full_description": "All violent crimes combined including murder, rape, robbery, and aggravated assault",
        "why_model": "Violent crime aggregates multiple offense types, making it suitable for standard ARIMA modeling.",
    },
    "property-crime": {
        "full_description": "All property crimes combined including burglary, larceny-theft, and motor vehicle theft",
        "why_model": "Property crime data is well-suited for ARIMA models due to consistent reporting patterns.",
    },
    "homicide": {
        "full_description": "Murder and non-negligent manslaughter",
        "why_model": "Homicide data benefits from Prophet's ability to handle irregular patterns and holidays.",
    },
    "burglary": {
        "full_description": "Unlawful entry of a structure to commit a felony or theft",
        "why_model": "Burglary shows stable trends suitable for ARIMA time-series modeling.",
    },
    "motor-vehicle-theft": {
        "full_description": "Theft or attempted theft of motor vehicles",
        "why_model": "This offense shows strong seasonal patterns (higher in summer, lower in winter), which SARIMA captures better than standard ARIMA.",
    },
}


def _format_month(date_str: str) -> str:
    """Convert date string (e.g., '2024-12') to readable format (e.g., 'December 2024')."""
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    try:
        parts = date_str.split("-")
        if len(parts) >= 2:
            year = parts[0]
            month_num = int(parts[1])
            if 1 <= month_num <= 12:
                return f"{month_names[month_num - 1]} {year}"
    except (ValueError, IndexError):
        pass
    return date_str


def _format_model_type(model_info: dict) -> str:
    """Format model type with seasonal indicator if applicable."""
    model_type = model_info.get("model_type", "Unknown")
    params = model_info.get("parameters", {})

    # Check for seasonal parameters
    if params.get("seasonal_order"):
        return f"{model_type} (seasonal)"
    return model_type


def _format_all_models(models: list[dict], state: str | None = None) -> str:
    """Format output for listing all models."""
    if state:
        location = STATE_NAMES.get(state, state)
        lines = [
            f"FBI UCR Crime Forecasting Models - {location}",
            "",
            "Available Models:",
            "",
        ]
    else:
        lines = [
            "FBI UCR Crime Forecasting Models",
            "",
            "Available Models:",
            "",
        ]

    # Filter models by location if state specified
    filtered_models = models
    if state:
        filtered_models = [m for m in models if m.get("location") == state]
    else:
        # Show national models when no state specified
        filtered_models = [m for m in models if m.get("location") == "national"]

    for idx, model in enumerate(filtered_models, 1):
        offense = model.get("offense", "unknown")
        description = OFFENSE_DESCRIPTIONS.get(offense, model.get("description", "No description available"))
        model_type = _format_model_type(model)
        mape = model.get("mape", 0)
        accuracy = 100 - mape
        training_end = _format_month(model.get("training_end", "Unknown"))

        lines.append(f"{idx}. {offense}")
        lines.append(f"   Description: {description}")
        lines.append(f"   Model: {model_type} | Accuracy: {accuracy:.1f}% (MAPE: {mape:.1f}%)")
        lines.append(f"   Training data through: {training_end}")
        lines.append("")

    lines.append("Data source: FBI Uniform Crime Reporting (UCR) Program")
    if state:
        lines.append(f"Geographic scope: {location}")
    else:
        lines.append("Geographic scope: National level")
        lines.append("State-level support: CA, TX, FL, NY, IL")
    lines.append("Forecast horizon: Up to 12 months")

    return "\n".join(lines)


def _format_model_details(model: dict) -> str:
    """Format detailed output for a specific offense."""
    offense = model.get("offense", "unknown")
    offense_title = offense.replace("-", " ").title()

    details = OFFENSE_DETAILS.get(offense, {})
    description = details.get("full_description", OFFENSE_DESCRIPTIONS.get(offense, "No description available"))
    why_model = details.get("why_model", "")

    model_type = model.get("model_type", "Unknown")
    params = model.get("parameters", {})
    mape = model.get("mape", 0)
    accuracy = 100 - mape
    training_end = _format_month(model.get("training_end", "Unknown"))

    # Format parameters
    params_lines = []
    if params.get("order"):
        params_lines.append(f"- Parameters: order={params['order']}")
        if params.get("seasonal_order"):
            params_lines[-1] += f", seasonal_order={params['seasonal_order']}"

    lines = [
        f"{offense_title} Forecasting Model",
        "",
        f"Description: {description}",
        "",
        "Model Details:",
        f"- Algorithm: {model_type}",
    ]

    lines.extend(params_lines)
    lines.append(f"- Accuracy: {accuracy:.1f}% (MAPE: {mape:.1f}%)")
    lines.append(f"- Training data: Through {training_end}")

    if why_model:
        lines.append("")
        lines.append(f"Why {model_type}: {why_model}")

    lines.append("")
    lines.append(f'Use ucr_forecast(offense="{offense}") to generate predictions.')

    return "\n".join(lines)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ucr_info(
    offense: str | None = Field(
        default=None,
        description="Specific offense to get details for. Valid values: violent-crime, property-crime, homicide, burglary, motor-vehicle-theft. If omitted, lists all available models."
    ),
    state: str | None = Field(
        default=None,
        description=(
            "State code to filter models (CA, TX, FL, NY, IL). "
            "If omitted, shows national-level models."
        ),
    ),
) -> str:
    """Get information about available FBI UCR crime forecasting models.

    Lists all models or returns details for a specific offense including accuracy
    and methodology. Supports both national and state-level models.

    GEOGRAPHIC COVERAGE:
    - National (default): United States aggregate data
    - States: CA (California), TX (Texas), FL (Florida), NY (New York), IL (Illinois)

    Args:
        offense: Specific offense to get details for. If omitted, lists all available models.
        state: State code to filter models (optional). If omitted, shows national models.

    Returns:
        Information about available models or details for a specific offense.

    Raises:
        ToolError: If the API request fails or offense is not found.
    """
    # Validate state if provided
    normalized_state = None
    if state is not None:
        state_upper = state.upper().strip()
        if state_upper not in VALID_STATES:
            valid_list = ", ".join(sorted(VALID_STATES))
            raise ToolError(
                f"Invalid state code: '{state}'. "
                f"Valid options are: {valid_list}. "
                "Use 2-letter state codes (e.g., 'CA' for California)."
            )
        normalized_state = state_upper

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Build query params
            params = {}
            if normalized_state:
                params["state"] = normalized_state

            response = await client.get(f"{BASE_URL}/api/v1/models", params=params)

            if response.status_code != 200:
                raise ToolError(f"Failed to fetch model information: HTTP {response.status_code}")

            data = response.json()
            models = data.get("models", [])

            if not models:
                if normalized_state:
                    raise ToolError(f"No models available for state: {normalized_state}")
                raise ToolError("No models available from the API")

            # If no offense specified, list all models
            if offense is None:
                return _format_all_models(models, normalized_state)

            # Find the specific model
            offense_lower = offense.lower().strip()
            for model in models:
                if model.get("offense", "").lower() == offense_lower:
                    return _format_model_details(model)

            # Offense not found - provide helpful error
            available = [m.get("offense") for m in models if m.get("offense")]
            unique_offenses = sorted(set(available))
            raise ToolError(
                f"Offense '{offense}' not found. Available offenses: {', '.join(unique_offenses)}"
            )

    except httpx.TimeoutException:
        raise ToolError("Request timed out while fetching model information")
    except httpx.RequestError as e:
        raise ToolError(f"Network error while fetching model information: {str(e)}")
    except ToolError:
        raise  # Re-raise ToolError as-is
    except Exception as e:
        raise ToolError(f"Unexpected error: {str(e)}")
