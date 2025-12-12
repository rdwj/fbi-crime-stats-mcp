# FBI Crime Data Explorer API Reference

## Overview

This document describes the working endpoints and parameters for the FBI Crime Data Explorer (CDE) API, based on empirical testing conducted on 2025-11-30.

**Base URL:** `https://api.usa.gov/crime/fbi/cde`

**Authentication:** API key required via query parameter `api_key`
- Get your key at: https://api.data.gov/signup/

**Date Format:** `MM-YYYY` (NOT YYYY-MM)
- Example: `from=01-2014&to=12-2024`

---

## Working Endpoints (31 Verified)

### 1. Agency Data
Get information about law enforcement agencies.

| Endpoint | Description |
|----------|-------------|
| `/agency/byStateAbbr/{state}` | Get all agencies in a state |

**Parameters:**
- `{state}` - Two-letter state abbreviation (e.g., "CA", "NY", "TX")

**Response Structure:**
```json
{
  "COUNTY_NAME": [
    {
      "ori": "AL0430200",
      "counties": "LEE",
      "is_nibrs": true,
      "latitude": 32.604064,
      "longitude": -85.353048,
      "state_abbr": "AL",
      "state_name": "Alabama",
      "agency_name": "Opelika Police Department",
      "agency_type_name": "City",
      "nibrs_start_date": "2021-01-01"
    }
  ]
}
```

---

### 2. Summarized Crime Data
Aggregated crime statistics (rates and counts).

| Endpoint | Description |
|----------|-------------|
| `/summarized/national/{offense}` | National crime data |
| `/summarized/state/{state}/{offense}` | State-level crime data |
| `/summarized/agency/{ori}/{offense}` | Agency-level crime data |

**Required Query Parameters:**
- `from` - Start date (MM-YYYY)
- `to` - End date (MM-YYYY)

**Valid Offense Codes:**
| Code | Description |
|------|-------------|
| `violent-crime` | All violent crimes combined |
| `homicide` | Murder and non-negligent manslaughter |
| `robbery` | Robbery |
| `aggravated-assault` | Aggravated assault |
| `property-crime` | All property crimes combined |
| `burglary` | Burglary |
| `larceny` | Larceny-theft |
| `motor-vehicle-theft` | Motor vehicle theft |
| `arson` | Arson |

**Note:** `rape-legacy` and `rape-revised` are NOT valid for this endpoint.

**Response Structure:**
```json
{
  "offenses": {
    "rates": {
      "United States": {
        "01-2014": 26.55,
        "02-2014": 22.45
      },
      "United States Clearances": {
        "01-2014": 12.59
      }
    },
    "actuals": {
      "United States": {
        "01-2014": 84563
      }
    }
  },
  "tooltips": {},
  "populations": {
    "United States": {
      "2014": 318857056
    }
  },
  "cde_properties": {}
}
```

**Data Available:** Monthly data from 2014-present

---

### 3. NIBRS Data (National Incident-Based Reporting System)
Detailed incident-level data with demographics.

| Endpoint | Description |
|----------|-------------|
| `/nibrs/national/{offense}` | National NIBRS data |
| `/nibrs/state/{state}/{offense}` | State-level NIBRS data |
| `/nibrs/agency/{ori}/{offense}` | Agency-level NIBRS data |

**Required Query Parameters:**
- `from` - Start date (MM-YYYY)
- `to` - End date (MM-YYYY)

**Valid Offense Codes:**
| Code | Description |
|------|-------------|
| `aggravated-assault` | Aggravated assault |
| `burglary` | Burglary |
| `homicide` | Homicide |
| `larceny` | Larceny-theft |
| `motor-vehicle-theft` | Motor vehicle theft |
| `robbery` | Robbery |
| `rape` | Rape (Note: valid here, unlike summarized) |

**Response Structure:**
```json
{
  "victim": {
    "age": {"0-9": null, "10-19": null, ...},
    "sex": {"Male": null, "Female": null, ...},
    "race": {"Asian": null, "White": null, ...},
    "location": {"Residence/Home": null, ...},
    "ethnicity": {"Hispanic or Latino": null, ...},
    "relationship": {"Spouse": null, "Friend": null, ...}
  },
  "offense": {
    "weapon": {...},
    "linkedOffense": {...}
  },
  "offender": {
    "age": {...},
    "sex": {...},
    "race": {...}
  },
  "cde_properties": {}
}
```

---

### 4. Hate Crime Data
Hate crime statistics with bias breakdowns.

| Endpoint | Description |
|----------|-------------|
| `/hate-crime/national` | National hate crime data |
| `/hate-crime/national/{bias}` | National data by bias type |
| `/hate-crime/state/{state}` | State-level hate crime data |
| `/hate-crime/state/{state}/{bias}` | State data by bias type |
| `/hate-crime/agency/{ori}` | Agency-level hate crime data |

**Required Query Parameters:**
- `from` - Start date (MM-YYYY)
- `to` - End date (MM-YYYY)

**Valid Bias Codes:**
- `anti-black`
- `anti-white`
- `anti-jewish`
- `anti-asian`
- `anti-hispanic`
- (and potentially others)

**Response Structure:**
```json
{
  "bias_section": {
    "victim_type": {
      "Individual": 100030,
      "Business": 7700,
      ...
    },
    "offense_type": {
      "Intimidation": 37167,
      "Simple Assault": 25884,
      "Aggravated Assault": 14218,
      "Destruction/Damage/Vandalism of Property": 28182,
      ...
    },
    "location_type": {...}
  },
  "incident_section": {...},
  "last_refresh_date": "2024-XX-XX"
}
```

---

## Endpoints NOT Working / Requiring Different Parameters

### Arrest Endpoints
The arrest endpoints (`/arrest/national/{offense}`, etc.) return:
```
"An invalid offense was requested. Please see our API page for valid offense IDs"
```

The standard offense codes used elsewhere do NOT work here. Valid codes unknown.

### NIBRS Estimation Endpoints
- `/nibrs-estimation/lookup/{lookup}` - Returns "lookup not found"
- `/nibrs-estimation/region/{region}/{offense}` - Region names unclear

### Supplemental/Expanded Property Endpoints
Returns: `"Type is missing or not valid"` - needs additional parameter

### Law Enforcement Employee Endpoints (WORKING with year format)
| Endpoint | Description |
|----------|-------------|
| `/pe` | National police employee data |
| `/pe/{state}` | State-level police employee data |

**Note:** Uses YEAR format (`from=2014&to=2024`), NOT MM-YYYY

**Response Structure:**
```json
{
  "rates": {...},
  "actuals": {...},
  "tooltips": {...},
  "populations": {...},
  "cde_properties": {}
}
```

### Participation Endpoints
- `/participation/national/{collection}/count` - Returns 404

---

## Example API Calls

### Get National Violent Crime (10 years)
```bash
curl "https://api.usa.gov/crime/fbi/cde/summarized/national/violent-crime?from=01-2014&to=12-2024&api_key=YOUR_KEY"
```

### Get California Agencies
```bash
curl "https://api.usa.gov/crime/fbi/cde/agency/byStateAbbr/CA?api_key=YOUR_KEY"
```

### Get NIBRS Homicide Data
```bash
curl "https://api.usa.gov/crime/fbi/cde/nibrs/national/homicide?from=01-2020&to=12-2024&api_key=YOUR_KEY"
```

### Get Hate Crime by State
```bash
curl "https://api.usa.gov/crime/fbi/cde/hate-crime/state/NY?from=01-2020&to=12-2024&api_key=YOUR_KEY"
```

---

## Data Availability Summary

| Category | Geographic Levels | Time Range | Data Type |
|----------|------------------|------------|-----------|
| Summarized Crime | National, State, Agency | 2014-present | Monthly rates/counts |
| NIBRS | National, State, Agency | 2014-present | Demographics/details |
| Hate Crime | National, State, Agency | 2014-present | Counts by bias/offense |
| Agency Info | State | Current | Metadata |

---

## For This Project

Based on testing, the following endpoints are most useful for trend analysis:

1. **`/summarized/national/{offense}`** - Primary source for national crime trends
2. **`/summarized/state/{state}/{offense}`** - State-level comparisons
3. **`/hate-crime/national`** - Hate crime trend analysis
4. **`/nibrs/national/{offense}`** - Demographic breakdowns (when data available)

**Valid offense codes for summarized data:**
- `violent-crime`, `property-crime` (aggregates)
- `homicide`, `robbery`, `aggravated-assault` (violent)
- `burglary`, `larceny`, `motor-vehicle-theft`, `arson` (property)

---

*Last Updated: 2025-11-30*
*Based on empirical API testing*
