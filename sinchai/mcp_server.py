import json
import os

from mcp.server.mcpserver import MCPServer

from sinchai import clock, config, db, engine, ledger, reports

mcp = MCPServer("sinchai")
_cfg = None
_db_path = None


def _con():
    return db.open_db(_db_path, query_only=True)


def _ctrl(con):
    row = db.get_controller_row(con)
    if row is None:
        return False, clock.to_iso(clock.now()), True
    age = (clock.now() - clock.from_iso(row["heartbeat_at"])).total_seconds()
    return age < 15, row["clock_now"], row["source"] == "sim" or row["demo"] == 1


def _base(con):
    running, clock_now, simulated = _ctrl(con)
    age_min = None
    if clock_now:
        age_min = round((clock.from_iso(clock.to_iso(clock.now())) - clock.from_iso(clock_now)).total_seconds() / 60.0, 1)
    return {"as_of": clock_now, "data_age_minutes": age_min, "controller_running": running, "simulated": simulated}


@mcp.tool(description="List all zones with crop, moisture, valve state and data age.")
def list_zones():
    con = _con()
    result = _base(con)
    result["zones"] = []
    for zone in db.get_zones(con):
        r = db.get_recent_readings(con, zone["id"], 1)
        m = r[0]["moisture_pct"] if r else None
        age = round((clock.from_iso(clock.to_iso(clock.now())) - clock.from_iso(r[0]["ts"])).total_seconds() / 60.0, 1) if r else None
        result["zones"].append({"id": zone["id"], "name": zone["name"], "crop": zone["crop"],
                                 "moisture_pct": m, "reading_age_minutes": age, "valve_open": bool(zone["valve_open"])})
    con.close()
    return result


@mcp.tool(description="Get status and recommendation for one zone. zone_id must match a real zone.")
def get_zone_status(zone_id: int):
    con = _con()
    zone = next((z for z in db.get_zones(con) if z["id"] == zone_id), None)
    if zone is None:
        con.close()
        return {"error": f"zone {zone_id} not found"}
    crop = db.get_crop(con, zone["crop"])
    readings = db.get_recent_readings(con, zone_id, 24)
    now_iso = clock.to_iso(clock.now())
    rec = engine.decide(zone, crop, readings, None, now_iso,
                        clock.local_minutes(clock.now(), _cfg["location"]["utc_offset_minutes"]), _cfg)
    open_alerts = [{"kind": a["kind"], "message": a["message"]}
                   for a in db.get_open_alerts(con) if a["zone_id"] == zone_id]
    result = _base(con)
    result.update({"zone": zone["name"], "crop": zone["crop"],
                   "moisture_pct": readings[0]["moisture_pct"] if readings else None,
                   "action": rec["action"], "minutes": rec["minutes"],
                   "reason": rec["reason"], "alerts": open_alerts})
    con.close()
    return result


@mcp.tool(description="Show the reasoning steps for the zone recommendation. zone_id must match a real zone.")
def explain_recommendation(zone_id: int):
    con = _con()
    zone = next((z for z in db.get_zones(con) if z["id"] == zone_id), None)
    if zone is None:
        con.close()
        return {"error": f"zone {zone_id} not found"}
    crop = db.get_crop(con, zone["crop"])
    readings = db.get_recent_readings(con, zone_id, 24)
    now_iso = clock.to_iso(clock.now())
    rec = engine.decide(zone, crop, readings, None, now_iso,
                        clock.local_minutes(clock.now(), _cfg["location"]["utc_offset_minutes"]), _cfg)
    result = _base(con)
    result.update({"action": rec["action"], "reason": rec["reason"], "trace": rec["trace"]})
    con.close()
    return result


@mcp.tool(description="Get current weather status and cache age.")
def get_weather_outlook():
    con = _con()
    key = f"{round(_cfg['location']['latitude'],2)},{round(_cfg['location']['longitude'],2)}"
    cached = db.get_weather_cache(con, key)
    result = _base(con)
    if cached is None:
        result["status"] = "OFFLINE"
        con.close()
        return result
    age_h = (clock.from_iso(clock.to_iso(clock.now())) - clock.from_iso(cached["fetched_at"])).total_seconds() / 3600.0
    data = json.loads(cached["payload"])
    cur = data.get("current", {})
    result.update({"status": "LIVE" if age_h < 0.5 else "CACHED", "cache_age_hours": round(age_h, 1),
                   "temperature_c": cur.get("temperature_2m"), "wind_kmh": cur.get("wind_speed_10m"),
                   "precip_current_mm": cur.get("precipitation")})
    con.close()
    return result


@mcp.tool(description="Water use report per zone. days must be between 1 and 30.")
def water_report(days: int = 7):
    if not 1 <= days <= 30:
        return {"error": "days must be between 1 and 30"}
    con = _con()
    result = _base(con)
    result["assumption"] = "Baseline assumes 30 min irrigation per day per zone at zone flow rate."
    result["zones"] = reports.zone_report(con, db.get_zones(con), _cfg, days)
    con.close()
    return result


@mcp.tool(description="Rain skip ledger with verdicts. limit must be between 1 and 50.")
def rain_check_ledger(limit: int = 10):
    if not 1 <= limit <= 50:
        return {"error": "limit must be between 1 and 50"}
    con = _con()
    rows = con.execute("SELECT * FROM skips ORDER BY decided_at DESC LIMIT ?", (limit,)).fetchall()
    result = _base(con)
    result["summary"] = ledger.ledger_summary(con)
    result["skips"] = [dict(r) for r in rows]
    con.close()
    return result


@mcp.tool(description="Request a valve action. action is open or close, minutes between 1 and max_request_minutes. Requires allow_valve_requests=true.")
def request_valve(zone_id: int, action: str, minutes: int = 30):
    if not _cfg["mcp"]["allow_valve_requests"]:
        return {"error": "valve requests disabled (allow_valve_requests=false in config)"}
    if action not in ("open", "close"):
        return {"error": "action must be open or close"}
    max_min = _cfg["mcp"]["max_request_minutes"]
    if not 1 <= minutes <= max_min:
        return {"error": f"minutes must be between 1 and {max_min}"}
    wcon = db.open_db(_db_path, query_only=False)
    zone = next((z for z in db.get_zones(wcon) if z["id"] == zone_id), None)
    if zone is None:
        wcon.close()
        return {"error": f"zone {zone_id} not found"}
    ts = clock.to_iso(clock.now())
    cur = wcon.execute("INSERT INTO valve_requests (zone_id,action,minutes,requested_at) VALUES (?,?,?,?)",
                       (zone_id, action, minutes, ts))
    wcon.commit()
    req_id = cur.lastrowid
    wcon.close()
    con = _con()
    running, _, _ = _ctrl(con)
    con.close()
    return {"request_id": req_id, "status": "pending", "controller_running": running}


@mcp.resource("sinchai://crops")
def crops_resource():
    con = _con()
    rows = con.execute("SELECT * FROM crops").fetchall()
    con.close()
    return json.dumps([dict(r) for r in rows])


@mcp.resource("sinchai://zones/{zone_id}")
def zone_resource(zone_id: int):
    con = _con()
    zone = next((z for z in db.get_zones(con) if z["id"] == zone_id), None)
    con.close()
    return json.dumps(dict(zone) if zone else {"error": f"zone {zone_id} not found"})


@mcp.resource("sinchai://alerts/recent")
def alerts_resource():
    con = _con()
    rows = db.get_open_alerts(con)
    con.close()
    return json.dumps([dict(r) for r in rows])


@mcp.prompt()
def daily_farm_briefing():
    return """Call list_zones, get_weather_outlook, and get_zone_status for each zone.
Write a short plain-language brief for a farmer: what needs watering, what can wait, and why.
State the data age. If data is simulated, say so. Do not invent numbers."""


def main():
    global _cfg, _db_path
    _db_path = os.environ.get("SINCHAI_DB", "data/sinchai.db")
    _cfg = config.get_config(_db_path)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
