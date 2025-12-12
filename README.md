# FBI Crime Stats MCP Server

An MCP (Model Context Protocol) server providing tools for accessing FBI crime statistics, generating crime forecasts, and analyzing historical crime trends using data from the FBI Uniform Crime Reporting (UCR) Program.

## Features

- **Crime Forecasting** - Generate predictions for major crime categories using time-series models (ARIMA, SARIMA, Prophet)
- **Historical Data** - Fetch actual crime statistics from 2015 to present via the FBI Crime Data Explorer API
- **Trend Comparison** - Compare forecasts across multiple offense types side-by-side
- **Model Information** - View details about available forecasting models including accuracy metrics
- **Multi-Level Support** - National-level and state-level data for CA, TX, FL, NY, IL

## Supported Data

### Offense Types

| Offense | Description |
|---------|-------------|
| `violent-crime` | All violent crimes (murder, rape, robbery, assault) |
| `property-crime` | All property crimes (burglary, theft, vehicle theft) |
| `homicide` | Murder and non-negligent manslaughter |
| `burglary` | Unlawful entry to commit felony |
| `motor-vehicle-theft` | Theft or attempted theft of motor vehicles |

### Geographic Coverage

- **National**: United States aggregate data
- **States**: California (CA), Texas (TX), Florida (FL), New York (NY), Illinois (IL)

### Time Coverage

- **Historical data**: 2015 to present (via FBI Crime Data Explorer API)
- **Forecasts**: 1-12 months ahead
- **Training data**: January 2020 - October 2024

## Tools

### `ucr_forecast`

Generate crime predictions with confidence intervals.

```
Parameters:
- offense (required): Crime type to forecast
- months_ahead (default: 6): Forecast horizon (1-12 months)
- include_history (default: false): Include recent historical data
- format (default: "summary"): Output format ("summary" or "detailed")
- state (optional): State code for state-level forecast

Example output:
Violent Crime Forecast (National, next 6 months):

Predicted Incidents:
- Jan 2025: ~95,000 (range: 90,000 - 100,000)
- Feb 2025: ~93,500 (range: 88,500 - 98,500)
...

Trend: Decreasing (-2.3%)
Model: ARIMA | Accuracy: 94.2% | Data through: Oct 2024
```

### `ucr_history`

Fetch historical crime data for multi-year trend analysis.

```
Parameters:
- offense (required): Crime type to fetch
- from_year (default: 2020): Start year (2015-present)
- to_year (default: current year): End year
- state (optional): State code for state-level data
- format (default: "summary"): Output format ("summary" or "detailed")

Example output:
Violent Crime Historical Data (United States)
Period: 2020 - 2024

Annual Totals:
- 2020: 1,313,105 incidents
- 2021: 1,326,388 incidents
- 2022: 1,244,986 incidents
...

Overall Trend: Decreasing (-5.2% from start to end)
```

### `ucr_compare`

Compare forecasts across multiple offense types.

```
Parameters:
- offenses (required): List of 2-5 offense types to compare
- months_ahead (default: 6): Forecast horizon (1-12 months)
- metric (default: "percent_change"): "absolute" or "percent_change"
- state (optional): State code for state-level comparison

Example output:
Crime Trend Comparison - National (6-month forecast):

                      Current    6-Month Forecast   Change
Violent Crime         95,000     93,000            -2.1%
Property Crime       250,000    245,000            -2.0%
Motor Vehicle Theft   70,000     83,822            +19.7% warning

warning Motor vehicle theft shows significant projected increase.

Models: ARIMA (violent, property), SARIMA (mvt) | Data through: Oct 2024
```

### `ucr_info`

Get information about available forecasting models.

```
Parameters:
- offense (optional): Specific offense to get details for
- state (optional): State code to filter models

Example output:
FBI UCR Crime Forecasting Models

Available Models:

1. violent-crime
   Description: All violent crimes combined (murder, rape, robbery, assault)
   Model: ARIMA | Accuracy: 94.2% (MAPE: 5.8%)
   Training data through: October 2024

2. motor-vehicle-theft
   Description: Theft or attempted theft of motor vehicles
   Model: SARIMA (seasonal) | Accuracy: 91.5% (MAPE: 8.5%)
   Training data through: October 2024
...
```

## Quick Start

### Local Development

```bash
# Install dependencies
make install

# Run locally (STDIO transport)
make run-local

# Test with cmcp
cmcp ".venv/bin/python -m src.main" tools/list
```

### Deploy to OpenShift

```bash
# Remove example code before deployment
./remove_examples.sh

# Deploy to OpenShift
make deploy PROJECT=my-project
```

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `FBI_API_KEY` | API key for FBI Crime Data Explorer ([register here](https://api.data.gov/signup/)) |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TRANSPORT` | Transport protocol | `stdio` (local) / `http` (OpenShift) |
| `MCP_HTTP_PORT` | HTTP server port | `8080` |
| `MCP_HTTP_PATH` | HTTP endpoint path | `/mcp/` |
| `MCP_HOT_RELOAD` | Enable hot-reload | `0` |

## Data Sources

- **FBI Crime Data Explorer API** - Official FBI API for historical crime statistics ([api.usa.gov/crime/fbi/cde](https://api.usa.gov/crime/fbi/cde))
- **FBI UCR Prediction Service** - Custom forecasting service using trained time-series models

### Data Limitations

- FBI data has approximately 2-month reporting lag
- Data represents reported crimes only, not all crimes committed
- Annual data may be incomplete if requested before year end
- State-level predictions limited to CA, TX, FL, NY, IL

## Project Structure

```
├── src/
│   ├── core/           # Core MCP server setup
│   ├── tools/          # MCP tool implementations
│   │   ├── ucr_forecast.py    # Crime prediction tool
│   │   ├── ucr_history.py     # Historical data tool
│   │   ├── ucr_compare.py     # Comparison tool
│   │   └── ucr_info.py        # Model information tool
│   ├── resources/      # MCP resources (if any)
│   ├── prompts/        # MCP prompts (if any)
│   └── middleware/     # Request/response middleware
├── tests/              # Test suite
├── Containerfile       # Container definition (Red Hat UBI)
├── openshift.yaml      # OpenShift deployment manifests
└── Makefile           # Common tasks
```

## Testing

```bash
# Run unit tests
make test

# Run with coverage
pytest --cov=src --cov-report=html

# Test specific tool
pytest tests/tools/test_ucr_forecast.py -v
```

## Requirements

- Python 3.11+
- OpenShift CLI (`oc`) for deployment
- cmcp for local testing: `pip install cmcp`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
