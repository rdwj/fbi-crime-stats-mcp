# FBI UCR MCP Tools Plan

## Design Philosophy

This document defines the MCP tools for the FBI UCR Crime Prediction service, following [Anthropic's best practices for writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents).

### Core Principles

1. **Consolidate Functionality**: Single tools handle complete workflows rather than exposing individual API endpoints. An agent should rarely need multiple tool calls to answer a question.

2. **Human-Readable Output by Default**: Prioritize semantic, interpretable responses over raw JSON. Agents can request detailed format when needed.

3. **Rich Tool Descriptions**: Descriptions explain what the tool does as you would to a new team member, including valid inputs, edge cases, and example outputs.

4. **Actionable Error Messages**: Errors explain what went wrong and suggest how to fix it, not just return codes.

5. **Response Format Control**: Tools support format options allowing agents to control token usage (concise vs. detailed).

6. **Namespace Prefix**: All tools use `ucr_` prefix to prevent collision with other MCP servers.

---

## Backend API Reference

The MCP server calls the deployed FBI UCR inference API:

**Base URL:** `https://fbi-ucr-fbi-ucr.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Service health check |
| `/api/v1/models` | GET | List all available models |
| `/api/v1/predict/{offense}` | POST | Generate predictions |
| `/api/v1/history/{offense}` | GET | Get historical data |

**Available Offenses:**
- `violent-crime` - All violent crimes combined
- `property-crime` - All property crimes combined
- `homicide` - Murder and non-negligent manslaughter
- `burglary` - Unlawful entry to commit felony
- `motor-vehicle-theft` - Theft of motor vehicles

---

## Tool Definitions

### Tool 1: `ucr_forecast`

**Purpose:** Primary prediction tool - generates crime forecasts with confidence intervals.

```python
@mcp.tool()
def ucr_forecast(
    offense: str,
    months_ahead: int = 6,
    include_history: bool = False,
    format: Literal["summary", "detailed"] = "summary"
) -> str:
    """
    Generate crime predictions using FBI UCR data and time-series models.

    Use this tool to forecast future crime incidents for specific offense types.
    The forecasts include confidence intervals showing prediction uncertainty.

    OFFENSES (use exact names with hyphens):
    - violent-crime: Aggregated violent crimes (murder, rape, robbery, assault)
    - property-crime: Aggregated property crimes (burglary, theft, vehicle theft)
    - homicide: Murder and non-negligent manslaughter only
    - burglary: Unlawful entry to commit a felony
    - motor-vehicle-theft: Theft or attempted theft of motor vehicles

    PARAMETERS:
    - offense: Crime type to forecast (required, use exact names above)
    - months_ahead: How many months to forecast, 1-12 (default: 6)
    - include_history: Include recent historical data for context (default: False)
    - format: "summary" for prose, "detailed" for full JSON (default: "summary")

    TIPS:
    - For trend analysis, use include_history=True to see past vs. predicted
    - Use format="summary" (default) for concise output, "detailed" for raw data
    - Confidence intervals widen for predictions further in the future
    - All predictions are national-level (state-level coming in future release)

    ACCURACY: Models have 91-95% accuracy (MAPE 5-9%) on validation data.

    EXAMPLE OUTPUT (summary):
    ```
    Violent Crime Forecast (National, next 6 months):

    Predicted Incidents:
    - Jan 2025: ~84,925 (range: 76,032 - 93,819)
    - Feb 2025: ~84,876 (range: 72,253 - 97,500)
    - Mar 2025: ~84,844 (range: 69,340 - 100,349)
    - Apr 2025: ~84,824 (range: 66,880 - 102,767)
    - May 2025: ~84,810 (range: 64,714 - 104,906)
    - Jun 2025: ~84,801 (range: 62,757 - 106,845)

    Trend: Stable (slight decrease of 0.1%)
    Model: ARIMA | Accuracy: 91% | Data through: Dec 2024
    ```
    """
```

**Output Format (summary):**
```
{Offense} Forecast (National, next {N} months):

Predicted Incidents:
- {Month Year}: ~{predicted} (range: {lower} - {upper})
...

Trend: {Increasing|Decreasing|Stable} ({percent_change}%)
Model: {model_type} | Accuracy: {100-mape}% | Data through: {training_end}
```

**Output Format (detailed):**
Returns full JSON response from API including all metadata.

---

### Tool 2: `ucr_compare`

**Purpose:** Compare trends across multiple offense types in a single call.

```python
@mcp.tool()
def ucr_compare(
    offenses: list[str],
    months_ahead: int = 6,
    metric: Literal["absolute", "percent_change"] = "percent_change"
) -> str:
    """
    Compare crime trend forecasts across multiple offense types.

    Use this tool when you need to compare different types of crime or
    identify which categories are increasing/decreasing the most.

    OFFENSES (provide 2-5 from this list):
    - violent-crime
    - property-crime
    - homicide
    - burglary
    - motor-vehicle-theft

    PARAMETERS:
    - offenses: List of 2-5 offense types to compare (required)
    - months_ahead: Forecast horizon, 1-12 months (default: 6)
    - metric: "absolute" shows raw counts, "percent_change" shows trends (default: percent_change)

    WHY USE THIS:
    - Single call instead of multiple ucr_forecast calls
    - Side-by-side comparison table
    - Highlights significant changes with warnings

    EXAMPLE OUTPUT:
    ```
    Crime Trend Comparison (6-month forecast):

                          Current    6-Month Forecast   Change
    Violent Crime         85,000     84,800            -0.2%
    Property Crime        250,000    245,000           -2.0%
    Motor Vehicle Theft   70,000     83,822            +19.7% ⚠️

    ⚠️ Motor vehicle theft shows significant projected increase.

    Models: ARIMA (violent, property), SARIMA (mvt) | Data through: Dec 2024
    ```
    """
```

---

### Tool 3: `ucr_info`

**Purpose:** Discovery tool - what models are available and their capabilities.

```python
@mcp.tool()
def ucr_info(
    offense: str | None = None
) -> str:
    """
    Get information about available crime forecasting models.

    Use this tool to:
    - Discover what offense types can be forecast
    - Learn about model accuracy and methodology
    - Check when models were last trained

    PARAMETERS:
    - offense: Specific offense to get details for (optional)
              If omitted, lists all available models

    EXAMPLE OUTPUT (no offense specified):
    ```
    FBI UCR Crime Forecasting Models

    Available Models:

    1. violent-crime
       Description: All violent crimes combined (murder, rape, robbery, assault)
       Model: ARIMA | Accuracy: 91% (MAPE: 9.0%)
       Training data through: December 2024

    2. property-crime
       Description: All property crimes combined
       Model: ARIMA | Accuracy: 92.1% (MAPE: 7.9%)
       Training data through: December 2024

    3. homicide
       Description: Murder and non-negligent manslaughter
       Model: Prophet | Accuracy: 91.8% (MAPE: 8.2%)
       Training data through: December 2024

    4. burglary
       Description: Unlawful entry to commit felony
       Model: ARIMA | Accuracy: 92.3% (MAPE: 7.7%)
       Training data through: December 2024

    5. motor-vehicle-theft
       Description: Theft of motor vehicles
       Model: SARIMA (seasonal) | Accuracy: 94.6% (MAPE: 5.4%)
       Training data through: December 2024

    Data source: FBI Uniform Crime Reporting (UCR) Program
    Geographic scope: National level
    Forecast horizon: Up to 12 months
    ```

    EXAMPLE OUTPUT (offense="motor-vehicle-theft"):
    ```
    Motor Vehicle Theft Forecasting Model

    Description: Theft or attempted theft of motor vehicles

    Model Details:
    - Algorithm: SARIMA (Seasonal ARIMA)
    - Parameters: order=(1,1,1), seasonal_order=(1,1,1,12)
    - Accuracy: 94.6% (MAPE: 5.4%)
    - Training data: Through December 2024

    Why SARIMA: This offense shows strong seasonal patterns
    (higher in summer, lower in winter), which SARIMA captures
    better than standard ARIMA.

    Use ucr_forecast(offense="motor-vehicle-theft") to generate predictions.
    ```
    """
```

---

## Error Handling

All tools return actionable error messages:

**Unknown Offense:**
```
Unknown offense "violent_crime". Did you mean "violent-crime"?

Valid offenses: violent-crime, property-crime, homicide, burglary, motor-vehicle-theft

Note: Use hyphens, not underscores.
```

**Invalid Parameter:**
```
months_ahead must be between 1 and 12. You provided: 24

For longer forecasts, consider making multiple calls or note that
accuracy decreases significantly beyond 12 months.
```

**Service Unavailable:**
```
The FBI UCR prediction service is temporarily unavailable.

This may be due to:
- Scheduled maintenance
- High demand
- Network issues

Try again in a few minutes. If the problem persists, the service
may be experiencing an outage.
```

---

## Implementation Notes

### API Client

The MCP server wraps the FastAPI inference service:

```python
import httpx

API_BASE = "https://fbi-ucr-fbi-ucr.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com"

async def get_prediction(offense: str, months: int) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/api/v1/predict/{offense}",
            json={"months": months},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
```

### Response Formatting

Summary format converts API JSON to human-readable prose:

```python
def format_forecast_summary(api_response: dict) -> str:
    offense = api_response["offense"].replace("-", " ").title()
    predictions = api_response["predictions"]
    metadata = api_response["metadata"]

    lines = [f"{offense} Forecast (National, next {len(predictions)} months):", ""]
    lines.append("Predicted Incidents:")

    for p in predictions:
        date = datetime.strptime(p["date"], "%Y-%m")
        month_str = date.strftime("%b %Y")
        lines.append(
            f"- {month_str}: ~{p['predicted']:,.0f} "
            f"(range: {p['lower']:,.0f} - {p['upper']:,.0f})"
        )

    # Calculate trend
    first = predictions[0]["predicted"]
    last = predictions[-1]["predicted"]
    change = (last - first) / first * 100
    trend = "Increasing" if change > 1 else "Decreasing" if change < -1 else "Stable"

    lines.append("")
    lines.append(f"Trend: {trend} ({change:+.1f}%)")
    lines.append(
        f"Model: {metadata['model_type']} | "
        f"Accuracy: {100 - metadata['mape']:.0f}% | "
        f"Data through: {metadata['training_end']}"
    )

    return "\n".join(lines)
```

### Fuzzy Matching for Offense Names

Handle common input variations:

```python
OFFENSE_ALIASES = {
    "violent": "violent-crime",
    "violent crime": "violent-crime",
    "violent_crime": "violent-crime",
    "property": "property-crime",
    "property crime": "property-crime",
    "property_crime": "property-crime",
    "murder": "homicide",
    "mvt": "motor-vehicle-theft",
    "vehicle theft": "motor-vehicle-theft",
    "car theft": "motor-vehicle-theft",
}

def normalize_offense(input: str) -> str:
    normalized = input.lower().strip()
    if normalized in VALID_OFFENSES:
        return normalized
    if normalized in OFFENSE_ALIASES:
        return OFFENSE_ALIASES[normalized]
    raise ValueError(f"Unknown offense: {input}")
```

---

## Future Enhancements

### Phase 2: State-Level Predictions
- Add `state` parameter to `ucr_forecast`
- New `ucr_compare_states` tool for geographic comparison
- Fairness metrics across states

### Phase 3: Explainability
- `ucr_explain` tool for SHAP/LIME explanations
- Factor contribution breakdown
- "Why is X predicted to increase?" queries

### Phase 4: Historical Analysis
- Enhanced `ucr_history` tool
- Trend detection and anomaly highlighting
- Year-over-year comparisons

---

## Testing Checklist

- [ ] `ucr_forecast` returns valid predictions for all 5 offenses
- [ ] `ucr_forecast` with `format="detailed"` returns full JSON
- [ ] `ucr_forecast` with `include_history=True` includes historical data
- [ ] `ucr_compare` handles 2-5 offenses correctly
- [ ] `ucr_info` lists all models when no offense specified
- [ ] `ucr_info` returns details for specific offense
- [ ] Error messages are actionable and suggest corrections
- [ ] Fuzzy matching handles common aliases
- [ ] Service unavailable errors are handled gracefully
- [ ] Response times are under 5 seconds

---

**Document Version:** 1.0
**Created:** 2025-12-01
**Based On:** Anthropic's "Writing Tools for Agents" best practices
**Backend API:** FBI UCR Inference Service (OpenShift)
