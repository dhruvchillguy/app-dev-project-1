# Sinchai

I built Sinchai as an irrigation controller for a small farm with three zones (tomato, maize, and cotton). It reads soil moisture, checks the weather forecast from Open-Meteo, calculates how many minutes to water each zone, and skips watering when rain is expected. It keeps a ledger of rain skips to verify whether the predicted rain actually arrived.

Deviation from the brief: there is no mobile app. Alerts appear directly in the terminal interface, `sinchai brief` prints a short plain-text message a farmer can copy or forward by SMS or WhatsApp, and MCP covers the conversational assistant side.

## Screenshot

The user interface runs inside the terminal using Textual. It shows live zone moisture cards, valve states, weather status, and alerts. A visible banner indicates when simulated data is active.

## Quick Start

You need Python 3.11 or newer.

```bash
git clone https://github.com/dhruvkhare/smart-irrigation-system.git
cd smart-irrigation-system
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
sinchai doctor
sinchai run --demo
```

## Commands

- `sinchai run`: Start the terminal interface.
  - `--demo`: Run with scripted demo time and events (starts in AUTO mode).
  - `--auto`: Enable automatic valve opening and closing.
  - `--source sim`: Use simulated sensors (default).
  - `--source serial --port PORT`: Read real JSON lines from serial.
  - `--speed SPEED`: Clock acceleration factor for demo (default 1800).

### Keyboard Controls

- `d`: Switch to **Dashboard** tab (status bar, simulated banner, zone table, weather panel, alerts feed).
- `z`: Switch to **Zones** tab (selected zone details, 120-reading moisture sparkline, engine trace).
- `r`: Switch to **Reports** tab (litres used per zone, 7-day baseline comparison, stress hours).
- `l`: Switch to **Rain-check** tab (weather ledger with HIT/MISS verdicts and moisture low point).
- `s`: Switch to **Settings** tab (interactive inputs for location, calibration, zone overrides, and mode switch).
- `v`: Open or close the selected zone valve (1-second debounce, safety runtime limit).
- `m`: Toggle between MANUAL and AUTO mode.
- `a`: Acknowledge active alerts.
- `t`: Toggle light/dark theme.
- `q`: Quit the application.
  - `--seed SEED`: Random seed for sensor simulation.
  - `--headless`: Run controller loop without launching the TUI.
  - `--ticks N`: Run for N ticks and exit cleanly.
- `sinchai brief`: Print a one-line summary of current zone status.
- `sinchai export --table readings|alerts --out FILE [--force]`: Export records to CSV.
- `sinchai doctor`: Check Python version, database, weather API, MCP import, and terminal size.
- `sinchai mcp`: Start the Model Context Protocol server over stdio.
- `sinchai reset-db`: Delete the database file and start fresh.

## How Decisions Are Made

In the code and configuration, I use everyday names:
- `crop_factor` means crop coefficient (Kc).
- `water_holding_mm` means total available water in the root zone (TAW, mm).
- `evaporation_mm` means reference evapotranspiration (ET0, mm).

The decision engine is pure Python without database, network, or clock calls. It takes readings, crop parameters, zone configuration, weather data, and the current time, and returns an action.

The calculation steps are:
1. Deficit (mm) = `(target_pct - moisture_pct) / 100.0 * water_holding_mm`
2. Crop evapotranspiration ETc (mm) = `evaporation_mm * crop_factor`
3. Net water needed (mm) = `deficit_mm + ETc`
4. Gross water needed (mm) = `net_mm / irrigation_efficiency`
5. Irrigation duration (minutes) = `(gross_mm / flow_mm_hr) * 60`
6. Duration is clamped between `min_duration_minutes` and `max_duration_minutes` for the zone irrigation type.
7. Water volume (litres) = `(flow_mm_hr * (duration_minutes / 60.0)) * area_m2`

### Worked Example from Real Output

Here is a real calculation from the system for Zone 1:
- Crop: tomato (`crop_factor` = 1.15, `water_holding_mm` = 75.0 mm, minimum moisture = 60%, target moisture = 85%)
- Zone: area = 400 m2, drip irrigation (efficiency = 0.90, max duration = 180 min), flow rate = 8.0 mm/hr
- Moisture reading: 54.0% (6.0 points below minimum 60%)
- Daily reference evaporation: 4.0 mm
- Deficit: `(85 - 54) / 100 * 75.0 = 23.25 mm`
- ETc: `4.0 * 1.15 = 4.6 mm`
- Net water needed: `23.25 + 4.6 = 27.85 mm`
- Gross water needed: `27.85 / 0.90 = 30.94 mm`
- Uncapped duration: `(30.94 / 8.0) * 60 = 232.0 minutes`
- Capped duration: 180 minutes (maximum runtime safety cap for drip)
- Volume delivered: `8.0 * (180 / 60) * 400 = 9,600 litres`

Real output from `engine.decide`:
`{'action': 'IRRIGATE_NOW', 'minutes': 180, 'reason': 'moisture 54% is 6.0 points below minimum 60% (split into cycles)', 'hours_until': 0.0}`

## How the Rain-Check Ledger Works

When soil moisture is below minimum but rain is forecast within the lookahead window (12 hours) with probability at or above 70% and volume at or above 5.0 mm, the engine skips irrigation to conserve water.

The system opens a row in the `skips` ledger recording the forecast amount, probability, deadline, and the litres of water withheld. Once the deadline passes:
- If actual rainfall during the window meets or exceeds the threshold, the verdict is recorded as `HIT`. Water was saved without crop stress.
- If actual rainfall did not arrive, the verdict is recorded as `MISS`. The ledger records how low soil moisture dropped during the waiting period.

Important: "actual rain" in the ledger comes from Open-Meteo hourly weather observations, not an on-farm physical rain gauge.

Real ledger output from a demo run:
`2 skips: 1 hits, 1 misses. 96,000 L not applied. In misses, moisture dropped as low as 37%.`

## Model Context Protocol (MCP)

Sinchai includes an MCP server running over stdio. It allows AI assistants like Claude Desktop to query farm status safely.

### Available Tools

- `list_zones`: List all zones with crop, current moisture, valve state, and data age.
- `get_zone_status(zone_id)`: Get current status, recommendation, and open alerts for one zone.
- `explain_recommendation(zone_id)`: Show calculation steps and thresholds behind a recommendation.
- `get_weather_outlook`: Get current weather, 12-hour forecast, and cache age.
- `water_report(days)`: Water use report per zone with litres used, baseline, and stress hours.
- `rain_check_ledger(limit)`: List recent rain skips with verdicts and summary statistics.
- `request_valve(zone_id, action, minutes)`: Request manual valve operation. Disabled by default (`allow_valve_requests = false`).

### Example Questions

- "Which zones need watering today?"
- "Why was irrigation skipped for zone 1?"
- "How much water did the farm save this week?"

### Client Configuration

To connect Claude Desktop or another MCP client, add this to your client configuration:

```json
{
  "mcpServers": {
    "sinchai": {
      "command": "/Users/dhruvkhare/Desktop/smart-irrigation-system/.venv/bin/python",
      "args": ["-m", "sinchai.mcp_server"],
      "env": {
        "SINCHAI_DB": "/Users/dhruvkhare/Desktop/smart-irrigation-system/data/sinchai.db"
      }
    }
  }
}
```

Always use the full path to your virtual environment's Python executable.

## Hardware Notes

The system supports a capacitive soil moisture sensor v1.2 (3.3 V to 5.5 V supply, analog output).
- A higher raw analog reading means drier soil.
- Connect the analog signal pin to an ESP32 ADC1 pin (such as GPIO34). Do not use ADC2 pins because ADC2 does not work when Wi-Fi is active.
- Insert the sensor into the soil only up to the marked line and keep the electronic components dry.
- Calibration steps:
  1. Record the raw reading in open air: this is `dry_raw`.
  2. Record the raw reading in field soil a few hours after a thorough watering has drained: this is `wet_raw`.
  3. Enter both values in `defaults.toml` or the Settings screen.

The firmware sketch in `firmware/soil_node.ino` is untested on real hardware.

## Project Structure

```
smart-irrigation-system/
├── defaults.toml           # Baseline farm configuration
├── pyproject.toml          # Package metadata and dependencies
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Development dependencies
├── firmware/
│   └── soil_node.ino       # ESP32 sensor reader sketch (untested on hardware)
├── docs/
│   └── DESIGN.md           # Architecture and design decisions
├── sinchai/
│   ├── __init__.py
│   ├── __main__.py
│   ├── alerts.py           # Alert generation and lifecycle
│   ├── app.py              # Textual terminal application
│   ├── app.tcss            # Terminal styles
│   ├── cli.py              # Command-line interface and dispatch
│   ├── clock.py            # Real time and accelerated demo time
│   ├── config.py           # TOML configuration loader
│   ├── dashboard.py        # Dashboard screen component
│   ├── db.py               # SQLite database access and queries
│   ├── demo.py             # Scripted demo scenario runner
│   ├── demo_scenario.toml  # Demo weather and sensor events
│   ├── engine.py           # Pure decision engine
│   ├── farm.py             # Controller loop and tick handler
│   ├── ledger.py           # Rain-check skip ledger
│   ├── mcp_server.py       # Model Context Protocol server
│   ├── message.py          # Plain-text farmer brief formatter
│   ├── reports.py          # Water consumption and stress reports
│   ├── schema.sql          # SQLite schema
│   ├── screens.py          # Textual screen components
│   ├── sensors.py          # Simulated and serial sensor readers
│   ├── settings_view.py    # Settings screen with validation
│   ├── valves.py           # Valve safety and state management
│   ├── weather.py          # Open-Meteo client and cache
│   ├── widgets.py          # UI widgets
│   └── zone_view.py        # Zone detail and sparkline view
└── tests/
    ├── test_calibration.py # Sensor calibration math
    ├── test_db.py          # Database integrity and WAL mode
    ├── test_engine.py      # Decision engine boundary tests
    ├── test_ledger.py      # Rain-check ledger HIT/MISS logic
    ├── test_mcp.py         # MCP stdio server tests
    ├── test_reports.py     # Water volume and stress calculations
    ├── test_sensors.py     # Simulated and serial sensor tests
    └── test_weather.py     # Weather parsing and cache tests
```

## Configuration Layers

Configuration is loaded in two layers:
1. `sinchai/defaults.toml`: Default values for crops, zones, efficiency, weather, and safety limits.
2. `settings` table in SQLite: User-specific overrides applied at runtime.

## Testing

Run the test suite with pytest:

```bash
pytest -q
```

All 49 tests pass, verifying the decision engine, sensor calibration, database constraints, valve safety rules, rain-check ledger, reports, weather client, and MCP server.

## Limitations

- Sensor data is simulated unless a serial adapter is connected.
- Crop values in `defaults.toml` are approximate teaching values and must be verified against local UASD or KVK advisories.
- Soil moisture percentage is an approximation of plant-available water (0 = air-dry calibration, 100 = field capacity), not volumetric water content.
- "Actual rain" in the rain-check ledger comes from Open-Meteo weather models, not an on-farm rain gauge.
- Valves are simulated; no physical relay driver is implemented.
- The firmware sketch and serial communication path are untested on real hardware.
- There is no mobile application.
- The system is designed for a single farm and a single user.
- Measured tick execution time is approximately 7.15 ms of compute time per tick.

## Data Attribution

Weather data provided by Open-Meteo (open-meteo.com), licensed for non-commercial use. Weather requests are cached and polled at most once every 30 minutes.

## AI Assistance

Built with help from an AI coding assistant; the chat history is linked in my submission.
