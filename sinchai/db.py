import importlib.resources
import pathlib
import sqlite3

DEFAULT_DB_PATH = "data/sinchai.db"


def open_db(path, query_only=False):
    db_file = pathlib.Path(path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_file), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    if query_only:
        con.execute("PRAGMA query_only=ON")
    else:
        sql = importlib.resources.files("sinchai").joinpath("schema.sql").read_text()
        con.executescript(sql)
        con.commit()
    return con


def _exec(con, sql, params=()):
    con.execute(sql, params)
    con.commit()


def get_zones(con):
    return con.execute("SELECT * FROM zones ORDER BY id").fetchall()


def get_crop(con, name):
    return con.execute("SELECT * FROM crops WHERE name=?", (name,)).fetchone()


def insert_reading(con, zone_id, ts, moisture, raw, source):
    _exec(con, "INSERT INTO readings (zone_id,ts,moisture_pct,raw,source) VALUES (?,?,?,?,?)",
          (zone_id, ts, moisture, raw, source))


def get_recent_readings(con, zone_id, n=12):
    return con.execute(
        "SELECT * FROM readings WHERE zone_id=? ORDER BY ts DESC LIMIT ?",
        (zone_id, n)).fetchall()


def set_valve(con, zone_id, open_, ts, source, minutes=None, litres=None):
    if open_:
        _exec(con, "UPDATE zones SET valve_open=1, valve_opened_at=? WHERE id=?", (ts, zone_id))
    else:
        _exec(con, "UPDATE zones SET valve_open=0, valve_opened_at=NULL, last_closed_at=? WHERE id=?",
              (ts, zone_id))
    action = "open" if open_ else "close"
    _exec(con, "INSERT INTO valve_events (zone_id,ts,action,source,minutes,litres) VALUES (?,?,?,?,?,?)",
          (zone_id, ts, action, source, minutes, litres))


def close_all_valves(con, ts, source="failsafe"):
    rows = con.execute("SELECT id FROM zones WHERE valve_open=1").fetchall()
    for row in rows:
        set_valve(con, row["id"], False, ts, source)
    return len(rows)


def get_weather_cache(con, key):
    return con.execute("SELECT * FROM weather_cache WHERE key=?", (key,)).fetchone()


def upsert_weather_cache(con, key, fetched_at, payload):
    _exec(con, """INSERT INTO weather_cache (key,fetched_at,payload) VALUES (?,?,?)
          ON CONFLICT(key) DO UPDATE SET fetched_at=excluded.fetched_at, payload=excluded.payload""",
          (key, fetched_at, payload))


def upsert_rain_obs(con, hour_ts, mm, source="weather"):
    _exec(con, """INSERT INTO rain_obs (hour_ts,mm,source) VALUES (?,?,?)
          ON CONFLICT(hour_ts) DO UPDATE SET mm=excluded.mm, source=excluded.source""",
          (hour_ts, mm, source))


def insert_alert(con, ts, zone_id, kind, severity, message):
    cur = con.execute(
        "INSERT INTO alerts (ts,zone_id,kind,severity,message) VALUES (?,?,?,?,?)",
        (ts, zone_id, kind, severity, message))
    con.commit()
    return cur.lastrowid


def clear_alert(con, alert_id, ts):
    _exec(con, "UPDATE alerts SET cleared_ts=? WHERE id=?", (ts, alert_id))


def get_open_alerts(con):
    return con.execute(
        "SELECT * FROM alerts WHERE cleared_ts IS NULL ORDER BY ts DESC").fetchall()


def get_controller_row(con):
    return con.execute("SELECT * FROM controller WHERE id=1").fetchone()


def upsert_controller(con, pid, started_at, hb, clock_now, mode, source, demo, speed):
    _exec(con, """INSERT INTO controller (id,pid,started_at,heartbeat_at,clock_now,mode,source,demo,speed)
          VALUES (1,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET pid=excluded.pid, heartbeat_at=excluded.heartbeat_at,
          clock_now=excluded.clock_now, mode=excluded.mode, source=excluded.source,
          demo=excluded.demo, speed=excluded.speed""",
          (pid, started_at, hb, clock_now, mode, source, 1 if demo else 0, speed))


def clear_controller(con):
    _exec(con, "DELETE FROM controller WHERE id=1")
