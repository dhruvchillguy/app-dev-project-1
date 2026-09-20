import json, os
from mcp.server.mcpserver import MCPServer
from sinchai import clock, config, db, engine, ledger, reports

mcp = MCPServer("sinchai")
_cfg, _db_path = None, None
def _con(): return db.open_db(_db_path, query_only=True)
def _base(con):
    row = db.get_controller_row(con)
    if row is None: return {"as_of": clock.to_iso(clock.now()), "data_age_minutes": None, "controller_running": False, "simulated": True}
    running = (clock.now() - clock.from_iso(row["heartbeat_at"])).total_seconds() < 15
    age = round((clock.now() - clock.from_iso(row["clock_now"])).total_seconds() / 60.0, 1) if row["clock_now"] else None
    return {"as_of": row["clock_now"], "data_age_minutes": age, "controller_running": running, "simulated": row["source"] == "sim" or row["demo"] == 1}
def _zone_rec(con, zone_id):
    zone = next((z for z in db.get_zones(con) if z["id"] == zone_id), None)
    if zone is None: return None, None, None
    readings = db.get_recent_readings(con, zone_id, 24)
    rec = engine.decide(zone, db.get_crop(con, zone["crop"]), readings, None, clock.to_iso(clock.now()), clock.local_minutes(clock.now(), _cfg["location"]["utc_offset_minutes"]), _cfg)
    return zone, rec, readings
def _query_json(sql, params=()):
    con = _con()
    res = json.dumps([dict(r) for r in con.execute(sql, params).fetchall()])
    con.close()
    return res

@mcp.tool(description="List all zones with crop, moisture, valve state and data age.")
def list_zones():
    con = _con()
    res, now_dt = _base(con), clock.now()
    res["zones"] = []
    for z in db.get_zones(con):
        r = db.get_recent_readings(con, z["id"], 1)
        m = r[0]["moisture_pct"] if r else None
        age = round((now_dt - clock.from_iso(r[0]["ts"])).total_seconds() / 60.0, 1) if r else None
        res["zones"].append({"id": z["id"], "name": z["name"], "crop": z["crop"], "moisture_pct": m, "reading_age_minutes": age, "valve_open": bool(z["valve_open"])})
    con.close()
    return res

@mcp.tool(description="Get status and recommendation for one zone. zone_id must match a real zone.")
def get_zone_status(zone_id: int):
    con = _con()
    zone, rec, readings = _zone_rec(con, zone_id)
    if zone is None:
        con.close()
        return {"error": f"zone {zone_id} not found"}
    alerts = [{"kind": a["kind"], "message": a["message"]} for a in db.get_open_alerts(con) if a["zone_id"] == zone_id]
    m = readings[0]["moisture_pct"] if readings else None
    base = _base(con)
    con.close()
    return dict(base, zone=zone["name"], crop=zone["crop"], moisture_pct=m, action=rec["action"], minutes=rec["minutes"], reason=rec["reason"], alerts=alerts)

@mcp.tool(description="Show the reasoning steps for the zone recommendation. zone_id must match a real zone.")
def explain_recommendation(zone_id: int):
    con = _con()
    zone, rec, _ = _zone_rec(con, zone_id)
    base = _base(con)
    con.close()
    if zone is None: return {"error": f"zone {zone_id} not found"}
    return dict(base, action=rec["action"], reason=rec["reason"], trace=rec["trace"])

@mcp.tool(description="Get current weather status and cache age.")
def get_weather_outlook():
    con = _con()
    res, cached = _base(con), db.get_weather_cache(con, f"{round(_cfg['location']['latitude'],2)},{round(_cfg['location']['longitude'],2)}")
    con.close()
    if cached is None: return dict(res, status="OFFLINE")
    age_h = (clock.now() - clock.from_iso(cached["fetched_at"])).total_seconds() / 3600.0
    cur = json.loads(cached["payload"]).get("current", {})
    return dict(res, status="LIVE" if age_h < 0.5 else "CACHED", cache_age_hours=round(age_h, 1), temperature_c=cur.get("temperature_2m"), wind_kmh=cur.get("wind_speed_10m"), precip_current_mm=cur.get("precipitation"))

@mcp.tool(description="Water use report per zone. days must be between 1 and 30.")
def water_report(days: int = 7):
    if not 1 <= days <= 30: return {"error": "days must be between 1 and 30"}
    con = _con()
    z = reports.zone_report(con, db.get_zones(con), _cfg, days)
    res = dict(_base(con), assumption="Baseline assumes 30 min irrigation per day per zone at zone flow rate.", zones=z)
    con.close()
    return res

@mcp.tool(description="Rain skip ledger with verdicts. limit must be between 1 and 50.")
def rain_check_ledger(limit: int = 10):
    if not 1 <= limit <= 50: return {"error": "limit must be between 1 and 50"}
    con = _con()
    skips = [dict(r) for r in con.execute("SELECT * FROM skips ORDER BY decided_at DESC LIMIT ?", (limit,)).fetchall()]
    res = dict(_base(con), summary=ledger.ledger_summary(con), skips=skips)
    con.close()
    return res

@mcp.tool(description="Request a valve action. action is open or close, minutes between 1 and max_request_minutes.")
def request_valve(zone_id: int, action: str, minutes: int = 30):
    if not _cfg["mcp"]["allow_valve_requests"]: return {"error": "valve requests disabled (allow_valve_requests=false in config)"}
    if action not in ("open", "close") or not 1 <= minutes <= _cfg["mcp"]["max_request_minutes"]: return {"error": "invalid action or minutes"}
    wcon = db.open_db(_db_path, query_only=False)
    if not wcon.execute("SELECT 1 FROM zones WHERE id = ?", (zone_id,)).fetchone():
        wcon.close()
        return {"error": f"zone {zone_id} not found"}
    cur = wcon.execute("INSERT INTO valve_requests (zone_id,action,minutes,requested_at) VALUES (?,?,?,?)", (zone_id, action, minutes, clock.to_iso(clock.now())))
    wcon.commit()
    wcon.close()
    con = _con()
    run = _base(con)["controller_running"]
    con.close()
    return {"request_id": cur.lastrowid, "status": "pending", "controller_running": run}
@mcp.resource("sinchai://crops")
def crops_resource(): return _query_json("SELECT * FROM crops")
@mcp.resource("sinchai://zones/{zone_id}")
def zone_resource(zone_id: int):
    z = _query_json("SELECT * FROM zones WHERE id = ?", (zone_id,))
    return z[1:-1] if len(z) > 2 else json.dumps({"error": f"zone {zone_id} not found"})
@mcp.resource("sinchai://alerts/recent")
def alerts_resource(): return _query_json("SELECT * FROM alerts WHERE cleared_at IS NULL")
@mcp.prompt()
def daily_farm_briefing(): return "Call list_zones, get_weather_outlook, and get_zone_status for each zone. Write a short plain brief for a farmer. State data age and if simulated."
def main():
    global _cfg, _db_path
    _db_path = os.environ.get("SINCHAI_DB", "data/sinchai.db")
    _cfg = config.get_config(_db_path)
    mcp.run(transport="stdio")

if __name__ == "__main__": main()
