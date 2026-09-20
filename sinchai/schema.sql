PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS crops (
    name              TEXT PRIMARY KEY,
    crop_factor       REAL NOT NULL,
    water_holding_mm  REAL NOT NULL CHECK (water_holding_mm > 0),
    min_pct           REAL NOT NULL CHECK (min_pct >= 0 AND min_pct < 100),
    target_pct        REAL NOT NULL CHECK (target_pct > 0 AND target_pct <= 100),
    note              TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS zones (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    crop            TEXT NOT NULL REFERENCES crops(name),
    area_m2         REAL NOT NULL CHECK (area_m2 > 0),
    irrigation      TEXT NOT NULL CHECK (irrigation IN ('drip', 'sprinkler', 'flood')),
    flow_mm_hr      REAL NOT NULL CHECK (flow_mm_hr > 0),
    min_pct         REAL,
    target_pct      REAL,
    valve_open      INTEGER NOT NULL DEFAULT 0 CHECK (valve_open IN (0, 1)),
    valve_opened_at TEXT,
    last_closed_at  TEXT
);

CREATE TABLE IF NOT EXISTS readings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id      INTEGER NOT NULL REFERENCES zones(id),
    ts           TEXT NOT NULL,
    moisture_pct REAL NOT NULL CHECK (moisture_pct >= 0 AND moisture_pct <= 110),
    raw          INTEGER,
    source       TEXT NOT NULL DEFAULT 'sim'
);
CREATE INDEX IF NOT EXISTS idx_readings_zone_ts ON readings (zone_id, ts);

CREATE TABLE IF NOT EXISTS valve_events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL REFERENCES zones(id),
    ts      TEXT NOT NULL,
    action  TEXT NOT NULL CHECK (action IN ('open', 'close')),
    source  TEXT NOT NULL CHECK (source IN ('manual', 'auto', 'mcp', 'failsafe')),
    minutes REAL,
    litres  REAL
);

CREATE TABLE IF NOT EXISTS weather_cache (
    key        TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    payload    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rain_obs (
    hour_ts TEXT PRIMARY KEY,
    mm      REAL NOT NULL,
    source  TEXT NOT NULL DEFAULT 'weather'
);

CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    zone_id      INTEGER REFERENCES zones(id),
    kind         TEXT NOT NULL,
    severity     TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    message      TEXT NOT NULL,
    cleared_ts   TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skips (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id         INTEGER NOT NULL REFERENCES zones(id),
    decided_at      TEXT NOT NULL,
    forecast_mm     REAL NOT NULL,
    forecast_prob   REAL NOT NULL,
    deadline_at     TEXT NOT NULL,
    resolved_at     TEXT,
    actual_mm       REAL,
    verdict         TEXT CHECK (verdict IN ('HIT', 'MISS', NULL)),
    min_moisture    REAL,
    litres_withheld REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS valve_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id      INTEGER NOT NULL REFERENCES zones(id),
    action       TEXT NOT NULL CHECK (action IN ('open', 'close')),
    minutes      INTEGER,
    requested_at TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'applied', 'rejected', 'expired')),
    reason       TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS controller (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    pid          INTEGER NOT NULL,
    started_at   TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    clock_now    TEXT NOT NULL,
    mode         TEXT NOT NULL CHECK (mode IN ('manual', 'auto')),
    source       TEXT NOT NULL,
    demo         INTEGER NOT NULL CHECK (demo IN (0, 1)),
    speed        REAL NOT NULL DEFAULT 1.0
);

PRAGMA user_version = 1;
