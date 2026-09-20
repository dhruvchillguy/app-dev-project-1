import logging
from sinchai import clock, db

log = logging.getLogger(__name__)

SEVERITY = {
    "LOW_MOISTURE": "warning",
    "WATERLOGGING": "critical",
    "SENSOR_OFFLINE": "critical",
    "SENSOR_FAULT": "warning",
    "RAIN_INCOMING": "info",
    "HEAT": "warning",
    "WEATHER_OFFLINE": "info",
}

_last_raised = {}
COOLDOWN_SECONDS = 300


def raise_alert(con, kind, message, zone_id=None):
    key = (zone_id, kind)
    ts = clock.to_iso(clock.now())
    now_dt = clock.from_iso(ts)
    last = _last_raised.get(key)
    if last is not None:
        age = (now_dt - clock.from_iso(last)).total_seconds()
        if age < COOLDOWN_SECONDS:
            return None
    severity = SEVERITY.get(kind, "info")
    alert_id = db.insert_alert(con, ts, zone_id, kind, severity, message)
    _last_raised[key] = ts
    log.info("alert %s zone=%s: %s", kind, zone_id, message)
    return alert_id


def clear_kind(con, kind, zone_id=None):
    ts = clock.to_iso(clock.now())
    rows = con.execute(
        "SELECT id FROM alerts WHERE kind=? AND zone_id IS ? AND cleared_ts IS NULL",
        (kind, zone_id)).fetchall()
    for row in rows:
        db.clear_alert(con, row["id"], ts)
    if rows:
        _last_raised.pop((zone_id, kind), None)
    return len(rows)


def check_alerts(con, zone, readings, weather, rec, cfg):
    zid = zone["id"]
    if not readings:
        raise_alert(con, "SENSOR_OFFLINE", f"{zone['name']}: no sensor data", zid)
    elif rec["action"] == "NO_DATA" and "offline" in rec["reason"]:
        raise_alert(con, "SENSOR_OFFLINE", f"{zone['name']}: {rec['reason']}", zid)
    else:
        clear_kind(con, "SENSOR_OFFLINE", zid)

    if readings:
        m = readings[0]["moisture_pct"]
        crop = con.execute("SELECT * FROM crops WHERE name=?", (zone["crop"],)).fetchone()
        mn = zone["min_pct"] if zone["min_pct"] is not None else (crop["min_pct"] if crop else 45)
        if m < mn:
            raise_alert(con, "LOW_MOISTURE", f"{zone['name']}: moisture {m:.0f}% below minimum {mn:.0f}%", zid)
        else:
            clear_kind(con, "LOW_MOISTURE", zid)
        if rec["action"] == "STOP":
            raise_alert(con, "WATERLOGGING", f"{zone['name']}: waterlogged", zid)
        else:
            clear_kind(con, "WATERLOGGING", zid)

    if weather is None:
        raise_alert(con, "WEATHER_OFFLINE", "weather data unavailable")
    else:
        clear_kind(con, "WEATHER_OFFLINE")
        if weather.get("temperature_c", 0) >= cfg["engine"]["heat_alert_c"]:
            raise_alert(con, "HEAT", f"temperature {weather['temperature_c']:.0f} C", zid)
        else:
            clear_kind(con, "HEAT", zid)
        if rec["action"] == "SKIP_RAIN":
            raise_alert(con, "RAIN_INCOMING", f"{zone['name']}: rain expected, skipping irrigation", zid)
        else:
            clear_kind(con, "RAIN_INCOMING", zid)
