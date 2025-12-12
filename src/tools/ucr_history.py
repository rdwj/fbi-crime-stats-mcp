"""Fetch historical crime data from the FBI Crime Data Explorer API for multi-year trend analysis.

SUPPORTED SCOPE:
- Geographic: National level + 5 states (CA, TX, FL, NY, IL)
- Offenses: violent-crime, property-crime, homicide, burglary, motor-vehicle-theft
- Time range: 2015-present
- Data source: FBI Crime Data Explorer API (live data)

DATA NOTES:
- FBI data has approximately 2 month lag (most recent data ~2 months old)
- Data represents reported crimes only, not all crimes committed
- Annual data may be incomplete if requested before year end
"""

import json
import os
from datetime import datetime
from typing import Annotated

import httpx
from fastmcp.exceptions import ToolError
from pydantic import Field

from core.app import mcp

# FBI Crime Data Explorer API Configuration
FBI_API_BASE_URL = "https://api.usa.gov/crime/fbi/cde"
FBI_API_KEY = os.getenv("FBI_API_KEY")
REQUEST_TIMEOUT = 30.0

# Valid offense types
VALID_OFFENSES = frozenset(
    [
        "violent-crime",
        "property-crime",
        "homicide",
        "burglary",
        "motor-vehicle-theft",
    ]
)

# Supported states for state-level data
VALID_STATES = frozenset(["CA", "TX", "FL", "NY", "IL"])

# State name mapping for display
STATE_NAMES = {
    "CA": "California",
    "TX": "Texas",
    "FL": "Florida",
    "NY": "New York",
    "IL": "Illinois",
}

# Offense aliases for fuzzy matching
OFFENSE_ALIASES = {
    "violent_crime": "violent-crime",
    "violentcrime": "violent-crime",
    "violent": "violent-crime",
    "property_crime": "property-crime",
    "propertycrime": "property-crime",
    "property": "property-crime",
    "murder": "homicide",
    "homicides": "homicide",
    "burglaries": "burglary",
    "break-in": "burglary",
    "motor_vehicle_theft": "motor-vehicle-theft",
    "motorvehicletheft": "motor-vehicle-theft",
    "vehicle-theft": "motor-vehicle-theft",
    "car-theft": "motor-vehicle-theft",
    "auto-theft": "motor-vehicle-theft",
    "mvt": "motor-vehicle-theft",
}


def normalize_offense(offense: str) -> str:
    """Normalize offense name using fuzzy matching."""
    cleaned = offense.lower().strip()

    if cleaned in VALID_OFFENSES:
        return cleaned

    if cleaned in OFFENSE_ALIASES:
        return OFFENSE_ALIASES[cleaned]

    valid_list = ", ".join(sorted(VALID_OFFENSES))
    raise ToolError(
        f"Unknown offense type: '{offense}'. "
        f"Valid options are: {valid_list}. "
        f"Tip: Use hyphens instead of underscores (e.g., 'violent-crime' not 'violent_crime')."
    )


def normalize_state(state: str | None) -> str | None:
    """Normalize state code to uppercase."""
    if state is None:
        return None

    cleaned = state.upper().strip()

    if cleaned in VALID_STATES:
        return cleaned

    valid_list = ", ".join(sorted(VALID_STATES))
    raise ToolError(
        f"Unknown state code: '{state}'. "
        f"Valid options are: {valid_list}. "
        f"Use 2-letter state codes (e.g., 'CA' for California)."
    )


def format_number(value: float | int) -> str:
    """Format a number with thousands separators."""
    return f"{int(round(value)):,}"


def parse_api_date(api_date: str) -> str:
    """Convert API date format (MM-YYYY) to YYYY-MM."""
    if "-" in api_date:
        parts = api_date.split("-")
        if len(parts[0]) == 2:  # MM-YYYY format
            return f"{parts[1]}-{parts[0]}"
    return api_date


def calculate_trend(data: list[dict]) -> tuple[str, float]:
    """Calculate trend direction and percent change from first to last data point."""
    if len(data) < 2:
        return "Stable", 0.0

    first_value = data[0].get("actual", 0)
    last_value = data[-1].get("actual", 0)

    if first_value == 0:
        return "Stable", 0.0

    percent_change = ((last_value - first_value) / first_value) * 100

    if percent_change > 5:
        return "Increasing", percent_change
    elif percent_change < -5:
        return "Decreasing", percent_change
    else:
        return "Stable", percent_change


def calculate_yearly_totals(data: list[dict]) -> dict[int, int]:
    """Calculate yearly totals from monthly data."""
    yearly: dict[int, int] = {}
    for point in data:
        date = point.get("date", "")
        if date and "-" in date:
            year = int(date.split("-")[0])
            yearly[year] = yearly.get(year, 0) + point.get("actual", 0)
    return yearly


def format_summary(
    offense: str,
    location: str,
    data: list[dict],
    from_year: int,
    to_year: int,
) -> str:
    """Format historical data as a human-readable summary."""
    lines = []

    # Header
    offense_display = offense.replace("-", " ").title()
    location_display = (
        STATE_NAMES.get(location, "United States")
        if location != "national"
        else "United States"
    )
    lines.append(f"{offense_display} Historical Data ({location_display})")
    lines.append(f"Period: {from_year} - {to_year}")
    lines.append("")

    if not data:
        lines.append("No data available for the requested period.")
        return "\n".join(lines)

    # Calculate yearly totals
    yearly_totals = calculate_yearly_totals(data)

    lines.append("Annual Totals:")
    for year in sorted(yearly_totals.keys()):
        total = yearly_totals[year]
        lines.append(f"- {year}: {format_number(total)} incidents")

    lines.append("")

    # Trend analysis
    trend, percent_change = calculate_trend(data)
    lines.append(f"Overall Trend: {trend} ({percent_change:+.1f}% from start to end)")

    # Data notes
    lines.append("")
    lines.append(
        "Note: Data from FBI Crime Data Explorer. Approximately 2-month reporting lag."
    )
    lines.append(f"Total months of data: {len(data)}")

    return "\n".join(lines)


def format_detailed(
    offense: str,
    location: str,
    data: list[dict],
    from_year: int,
    to_year: int,
) -> str:
    """Format historical data as detailed JSON output."""
    trend, percent_change = calculate_trend(data)
    yearly_totals = calculate_yearly_totals(data)

    result = {
        "offense": offense,
        "location": location,
        "from_year": from_year,
        "to_year": to_year,
        "total_months": len(data),
        "yearly_totals": yearly_totals,
        "monthly_data": data,
        "trend": {
            "direction": trend,
            "percent_change": round(percent_change, 2),
        },
        "data_source": "FBI Crime Data Explorer API",
        "notes": "Data has approximately 2-month reporting lag",
    }

    return json.dumps(result, indent=2)


async def fetch_national_history(
    offense: str,
    from_year: int,
    to_year: int,
) -> list[dict]:
    """Fetch national-level historical data from FBI API."""
    from_date = f"01-{from_year}"
    to_date = f"12-{to_year}"

    url = f"{FBI_API_BASE_URL}/summarized/national/{offense}"
    params = {
        "from": from_date,
        "to": to_date,
        "API_KEY": FBI_API_KEY,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    # Parse response
    records = []
    # FBI API returns keys with " Offenses" suffix (e.g., "United States Offenses")
    if data and "offenses" in data:
        actuals = (
            data.get("offenses", {})
            .get("actuals", {})
            .get("United States Offenses", {})
        )
        rates = (
            data.get("offenses", {}).get("rates", {}).get("United States Offenses", {})
        )

        for date_str, actual in actuals.items():
            date_normalized = parse_api_date(date_str)
            rate = rates.get(date_str)
            records.append(
                {
                    "date": date_normalized,
                    "actual": int(actual) if actual is not None else 0,
                    "rate": float(rate) if rate is not None else None,
                }
            )

    # Sort by date
    records.sort(key=lambda x: str(x["date"]))
    return records


async def fetch_state_history(
    state: str,
    offense: str,
    from_year: int,
    to_year: int,
) -> list[dict]:
    """Fetch state-level historical data from FBI API."""
    from_date = f"01-{from_year}"
    to_date = f"12-{to_year}"

    url = f"{FBI_API_BASE_URL}/summarized/state/{state}/{offense}"
    params = {
        "from": from_date,
        "to": to_date,
        "API_KEY": FBI_API_KEY,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    # Parse response
    records = []
    state_name = STATE_NAMES.get(state, state)
    # FBI API returns keys with " Offenses" suffix (e.g., "Texas Offenses")
    offenses_key = f"{state_name} Offenses"
    if data and "offenses" in data:
        actuals = data.get("offenses", {}).get("actuals", {}).get(offenses_key, {})
        rates = data.get("offenses", {}).get("rates", {}).get(offenses_key, {})

        for date_str, actual in actuals.items():
            date_normalized = parse_api_date(date_str)
            rate = rates.get(date_str)
            records.append(
                {
                    "date": date_normalized,
                    "actual": int(actual) if actual is not None else 0,
                    "rate": float(rate) if rate is not None else None,
                }
            )

    # Sort by date
    records.sort(key=lambda x: str(x["date"]))
    return records


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ucr_history(
    offense: Annotated[
        str,
        Field(
            description="Crime type to fetch history for. Must be one of: violent-crime, property-crime, homicide, burglary, motor-vehicle-theft"
        ),
    ],
    from_year: Annotated[
        int,
        Field(
            default=2020,
            ge=2015,
            le=2030,
            description="Start year for historical data (2015-present, default: 2020)",
        ),
    ] = 2020,
    to_year: Annotated[
        int | None,
        Field(
            default=None,
            description="End year for historical data (default: current year)",
        ),
    ] = None,
    state: Annotated[
        str | None,
        Field(
            default=None,
            description="State code for state-level data (CA, TX, FL, NY, IL). If omitted, returns national-level data.",
        ),
    ] = None,
    format: Annotated[
        str,
        Field(
            default="summary",
            description="Output format: 'summary' for prose, 'detailed' for full JSON",
        ),
    ] = "summary",
) -> str:
    """Fetch historical crime data from the FBI Crime Data Explorer API for multi-year trend analysis.

    Use this tool to retrieve actual historical crime statistics, NOT predictions or forecasts.
    Supports multi-year queries from 2015 to present for both national and state-level data.

    Args:
        offense: Crime type to fetch history for
        from_year: Start year for historical data (2015-present, default: 2020)
        to_year: End year for historical data (default: current year)
        state: State code for state-level data (CA, TX, FL, NY, IL). If omitted, returns national data.
        format: Output format: 'summary' for prose, 'detailed' for full JSON

    Returns:
        Historical crime data in the requested format

    Raises:
        ToolError: If validation fails or FBI API is unavailable
    """
    # Validate and normalize offense
    normalized_offense = normalize_offense(offense)

    # Validate and normalize state
    normalized_state = normalize_state(state)

    # Default to current year if not specified
    if to_year is None:
        to_year = datetime.now().year

    # Validate year range
    if from_year < 2015:
        raise ToolError(
            f"from_year must be 2015 or later (got {from_year}). "
            "FBI Crime Data Explorer API provides data from 2015 onward."
        )

    if from_year > to_year:
        raise ToolError(
            f"from_year ({from_year}) must be less than or equal to to_year ({to_year})."
        )

    # Validate format
    format_lower = format.lower().strip()
    if format_lower not in ("summary", "detailed"):
        raise ToolError(
            f"Invalid format '{format}'. Use 'summary' for prose output or "
            "'detailed' for full JSON data."
        )

    # Fetch data from FBI API
    try:
        if normalized_state:
            data = await fetch_state_history(
                state=normalized_state,
                offense=normalized_offense,
                from_year=from_year,
                to_year=to_year,
            )
            location = normalized_state
        else:
            data = await fetch_national_history(
                offense=normalized_offense,
                from_year=from_year,
                to_year=to_year,
            )
            location = "national"

    except httpx.TimeoutException:
        raise ToolError(
            "The FBI Crime Data Explorer API is not responding. Please try again later."
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ToolError(
                f"No data found for '{normalized_offense}' "
                f"in the specified date range ({from_year}-{to_year})."
            )
        elif e.response.status_code >= 500:
            raise ToolError(
                "The FBI Crime Data Explorer API is experiencing issues. "
                "Please try again later."
            )
        else:
            raise ToolError(
                f"FBI API request failed: {e.response.status_code} - {e.response.text}"
            )
    except httpx.RequestError as e:
        raise ToolError(
            f"Could not connect to the FBI Crime Data Explorer API: {str(e)}. "
            "Please check your network connection."
        )

    # Format output
    if format_lower == "summary":
        return format_summary(
            offense=normalized_offense,
            location=location,
            data=data,
            from_year=from_year,
            to_year=to_year,
        )
    else:
        return format_detailed(
            offense=normalized_offense,
            location=location,
            data=data,
            from_year=from_year,
            to_year=to_year,
        )
