import datetime
import logging
import os
import time

from sinchai import alerts, clock, db, demo as demo_mod, engine, ledger, valves, weather

log = logging.getLogger(__name__)
_auto_cooldowns = set()


def _seed_data(con, cfg):
    for name, crop in cfg.get("crops", {}).items():
        con.execute(
            "INSERT OR IGNORE INTO crops (name,crop_factor,water_holding_mm,min_pct,target_pct,note) VALUES (?,?,?,?,?,?)",
            (name, crop["crop_factor"], crop["water_holding_mm"], crop["min_pct"], crop["target_pct"], crop.get("note", "approx")),
        )
    for zone in cfg.get("zones", []):
        con.execute(
            "INSERT OR IGNORE INTO zones (id,name,crop,area_m2,irrigation,flow_mm_hr) VALUES (?,?,?,?,?,?)",
            (zone["id"], zone["name"], zone["crop"], zone["area_m2"], zone["irrigation"], zone["flow_mm_hr"]),
        )
    con.commit()


def _check_second_controller(con):
    row = db.get_controller_row(con)
    if row and (clock.now() - clock.from_iso(row["heartbeat_at"])).total_seconds() < 10:
        raise RuntimeError("Another controller is already running")


def _recover_valves(con):
    if db.get_controller_row(con):
        closed = db.close_all_valves(con, clock.to_iso(clock.now()), "failsafe")
        if closed:
            log.warning("unclean shutdown: closed %d valves on recovery", closed)


def _apply_pending_requests(con, zones, cfg):
    pending = con.execute("SELECT * FROM valve_requests WHERE status='pending'").fetchall()
    for req in pending:
        zone = next((z for z in zones if z["id"] == req["zone_id"]), None)
        status = "rejected" if zone is None else "applied"
        if zone and req["action"] == "open":
            valves.open_valve(con, zone, "mcp", req["minutes"] or 30, cfg)
        elif zone:
            valves.close_valve(con, zone, "mcp")
        con.execute("UPDATE valve_requests SET status=? WHERE id=?", (status, req["id"]))
    con.commit()


def tick(con, zones, sensor, w, mode, demo, scenario, cfg):
    now_dt = clock.now()
    now_iso = clock.to_iso(now_dt)
    local_min = clock.local_minutes(now_dt, cfg["location"]["utc_offset_minutes"])
    dropout_zones = demo_mod.get_dropout_zones(scenario, now_dt) if demo and scenario else set()

    for zone in zones:
        zid = zone["id"]
        crop = db.get_crop(con, zone["crop"])
        if zid not in dropout_zones:
            valve_open = zone["valve_open"] == 1
            rain_mm = demo_mod.get_demo_weather_at(scenario, now_dt)[1] if demo and scenario else 0.0
            m = sensor.tick(zone, crop, 5.0 / 60.0, valve_open, rain_mm, w)
            db.insert_reading(con, zid, now_iso, m, None, "sim")
        readings = db.get_recent_readings(con, zid, 48)
        zone = next((z for z in db.get_zones(con) if z["id"] == zid), zone)
        rec = engine.decide(zone, crop, readings, w, now_iso, local_min, cfg)
        alerts.check_alerts(con, zone, readings, w, rec, cfg)
        ledger.maybe_open_skip(con, zone, rec, cfg)
        if mode == "auto":
            valves.check_max_runtime(con, [zone], cfg)
            valves.handle_auto(con, zone, rec, _auto_cooldowns, cfg)

    ledger.resolve_due_skips(con, zones, cfg)
    _apply_pending_requests(con, zones, cfg)
    return now_iso


def run_headless(db_path, cfg, mode, demo, speed, seed, source, ticks_limit):
    from sinchai.sensors import SimulatedSensor
    con = db.open_db(db_path)
    _seed_data(con, cfg)
    _check_second_controller(con)
    _recover_valves(con)
    scenario = demo_mod.setup_demo(speed) if demo else None
    zones = db.get_zones(con)
    sensor = SimulatedSensor(zones, cfg, seed)
    if scenario and "zone_initial_moisture" in scenario:
        for zid, m in scenario["zone_initial_moisture"].items():
            sensor.moisture[int(zid)] = float(m)
    started_at = clock.to_iso(clock.now())
    tick_count = 0
    w = None
    try:
        while ticks_limit is None or tick_count < ticks_limit:
            hb = clock.to_iso(clock.now())
            db.upsert_controller(con, os.getpid(), started_at, hb, hb, mode, source, demo, speed)
            zones = db.get_zones(con)
            if not demo:
                w = weather.get_weather(con, cfg)
            elif scenario:
                wkm, r_mm = demo_mod.get_demo_weather_at(scenario, clock.now())
                if r_mm > 0:
                    db.upsert_rain_obs(con, hb[:13] + ":00:00Z", r_mm)
                f_mm, f_prob = demo_mod.get_demo_forecast_at(scenario, clock.now())
                times = [clock.to_iso(clock.now() + datetime.timedelta(hours=i)) for i in range(1, 13)]
                w = {"wind_kmh": wkm, "temperature_c": 30.0, "current_precip_mm": r_mm,
                     "hourly_times": times, "hourly_precip_mm": [f_mm / 12.0] * 12, "hourly_precip_prob": [f_prob] * 12,
                     "hourly_evaporation_mm": [0.3] * 12, "hourly_wind_kmh": [wkm] * 12, "hourly_temp_c": [30.0] * 12,
                     "source": "scripted", "fetched_at": hb}
            tick(con, zones, sensor, w, mode, demo, scenario, cfg)
            tick_count += 1
            time.sleep(0.05 if demo else cfg["sensor"]["poll_seconds"])
    finally:
        db.close_all_valves(con, clock.to_iso(clock.now()), "failsafe")
        db.clear_controller(con)
        log.info("controller stopped after %d ticks", tick_count)
    return tick_count
