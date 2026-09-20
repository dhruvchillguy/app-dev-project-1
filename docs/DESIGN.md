# Sinchai - Design Document

## Assumptions

- A-1: MCP means Model Context Protocol. The MCP server can be removed without breaking the controller.
- A-2: Python is the allowed course language.
- A-3: No hardware available. Serial support tested only through pyserial loop:// and fake data.
- A-4: Moisture percent means percent of plant-available water (0 = air-dry calibration point, 100 = field-capacity). Approximation only.
- A-5: Local time uses a fixed UTC offset of +330 min (India Standard Time). UTC timestamps stored everywhere. No zoneinfo (requires tzdata on Windows).
- A-6: Crop values are approximate teaching values, not validated agronomy.
- A-7: Push credentials for origin already work.
- A-8: mcp 2.x (installed: 2.2.0) renamed FastMCP to MCPServer. Chose MCPServer from mcp.server.mcpserver per the installed API. Code comment notes this.

## Name Mapping (code names to common names)

In Python code and config we use everyday names. Map to agronomic terms:
- crop_factor = crop coefficient (Kc)
- water_holding_mm = total available water in root zone (TAW, mm)
- evaporation_mm = reference evapotranspiration (ET0, mm)

The README explains this mapping once.

## Architecture

Two processes at most: the controller (TUI or headless) writes to SQLite; the MCP server reads (query_only). The single write path the MCP server has is inserting a row into valve_requests (only when allow_valve_requests=true), using a short-lived separate connection.

```
SimulatedSensor / SerialSensor
        |
   farm.py tick()
        |
   engine.decide()  <-- pure, no IO
        |
   alerts, ledger, valves
        |
     SQLite (WAL, one writer)
        |
   Textual UI  /  MCP server (read-only)
```

One notion of now: clock.now() everywhere. Nothing calls datetime.now() directly.

## ADRs

### 1: Python + Textual instead of Electron or web app
Decision: Use Python + Textual.
Context: Course requires terminal application. One developer, no Node.js build pipeline needed.
Alternatives: Electron (heavy, needs Node, cross-platform is harder), curses (low-level, hard to test), web app (needs browser).
Trade-off: Textual is newer and evolves fast, but is testable headless and pure Python.
Consequence: No mobile app. Stated in README Limitations.

### 2: SQLite instead of Postgres or flat files
Decision: SQLite with WAL mode, foreign keys, one writer.
Context: Single machine, single user, ~315,000 readings/year fits comfortably.
Alternatives: JSON files (no foreign keys, corruption risk), Postgres (overkill, needs a server process).
Trade-off: SQLite has a single-writer constraint; the design enforces this via the controller heartbeat.
Consequence: Beyond ~20 zones or multiple writers the design needs revisiting.

### 3: Open-Meteo instead of key-based weather APIs
Decision: Open-Meteo free tier.
Context: Zero cost, no API key, has ET0 and rain probability, non-commercial terms acceptable for a student project.
Alternatives: WeatherAPI (key required), OpenWeatherMap (key required, limited free tier).
Trade-off: Rate-limited, non-commercial terms, data needs attribution.
Consequence: Poll no more than every 30 minutes. Attribution line in README.

### 4: Pure decision engine separate from the UI
Decision: engine.py imports no UI, DB, network, or clock.
Context: Engine logic is the core that needs testing. Mixing it with I/O makes testing hard.
Alternatives: Logic inside widgets (untestable), logic in farm.py (harder to unit test).
Consequence: Easy to write boundary tests with hand-checked numbers.

### 5: Simulated sensors and valves first, serial behind the same base class
Decision: SensorReader base class with SimulatedSensor and SerialSensor.
Context: No hardware available. Must still show a credible data path.
Consequence: Serial path is untested on real hardware. Stated in README.

### 6: MCP over stdio, read-only by default, single-writer controller
Decision: MCP server uses stdio transport. Valve requests are off by default.
Context: No network listener needed. Standard MCP client support.
Trade-off: Client must spawn the process. Fine for one user.
Consequence: MCP tools return an error result on failure; they never crash the client.

### 7: Moisture as percent of available water with per-crop water_holding_mm
Decision: Express moisture as percent of plant-available water (0 = dry calibration point, 100 = field capacity).
Context: Simpler to understand than volumetric water content. Calibration requires only two raw readings.
Trade-off: Not volumetric water content. Approximation only.
Consequence: Stated clearly in README and on-screen.

## Security Review

- SQL injection: all queries parameterised. Tested with hostile strings in MCP text arguments.
- Command injection: no shell calls anywhere.
- Path traversal: export --out validated to not overwrite without --force.
- Serial input: size cap 256 bytes, JSON schema check, raw 0-4095, zone must exist.
- MCP inputs: zone_id must be int, minutes bounded, action must be open or close.
- Prompt injection: MCP responses contain only numbers and system-generated strings.
- Secrets: none. No API keys, no .env.
- Network: outbound HTTPS to Open-Meteo only. No listening sockets.
- Logging: nothing sensitive in logs.
- stdout: MCP server never prints to stdout.

## How This Could Grow

Current design is right for 1 farm, ~20 zones, 1 user.

Single machine (now) -> several fields (add a farms table, zone FKs) -> real hardware nodes (ESP32 over MQTT or HTTP to a small gateway, engine is unchanged) -> many users (SQLite to Postgres, real authentication, TLS, remote valve control needs proper auth).

The design stops being appropriate beyond roughly 20 zones, multiple concurrent writers, multiple users, or any remote valve control.

## Open-Meteo Terms

Non-commercial use, attribution required. Poll limit: no more than once per 10 minutes per IP in practice; we poll every 30 minutes. Attribution: "Weather data provided by Open-Meteo (open-meteo.com), licensed for non-commercial use."

## Dependencies (direct, verified versions)

- textual 8.2.8
- mcp 2.2.0
- httpx 0.28.1
- pyserial 3.5
- pytest 9.1.1
- pytest-asyncio 1.4.0
