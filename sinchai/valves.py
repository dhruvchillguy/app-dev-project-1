import logging
from sinchai import clock, db

log = logging.getLogger(__name__)

_opened_at = {}


def open_valve(con, zone, source, minutes, cfg):
    zid = zone["id"]
    ts = clock.to_iso(clock.now())
    flow = zone["flow_mm_hr"]
    area = zone["area_m2"]
    litres = flow * (minutes / 60.0) * area
    db.set_valve(con, zid, True, ts, source, minutes, litres)
    _opened_at[zid] = clock.from_iso(ts)
    log.info("valve open zone=%d source=%s minutes=%.0f litres=%.0f", zid, source, minutes, litres)


def close_valve(con, zone, source):
    zid = zone["id"]
    ts = clock.to_iso(clock.now())
    opened = _opened_at.pop(zid, None)
    litres = None
    if opened is not None:
        elapsed_hr = (clock.from_iso(ts) - opened).total_seconds() / 3600.0
        litres = zone["flow_mm_hr"] * elapsed_hr * zone["area_m2"]
    db.set_valve(con, zid, False, ts, source, None, litres)
    log.info("valve close zone=%d source=%s litres=%s", zid, source, litres)


def check_max_runtime(con, zones, cfg):
    max_min = cfg["engine"]["max_run_minutes"]
    now_dt = clock.now()
    for zone in zones:
        if not zone["valve_open"] or zone["valve_opened_at"] is None:
            continue
        opened_dt = clock.from_iso(zone["valve_opened_at"])
        elapsed_min = (now_dt - opened_dt).total_seconds() / 60.0
        if elapsed_min >= max_min:
            close_valve(con, zone, "failsafe")
            log.warning("max runtime reached zone=%d", zone["id"])


def handle_auto(con, zone, rec, cooldowns, cfg):
    zid = zone["id"]
    now_dt = clock.now()
    if zone["valve_open"]:
        if rec["action"] not in ("IRRIGATE_NOW",):
            close_valve(con, zone, "auto")
        return
    if rec["action"] != "IRRIGATE_NOW":
        return
    last_close = zone["last_closed_at"]
    if last_close:
        elapsed_min = (now_dt - clock.from_iso(last_close)).total_seconds() / 60.0
        if elapsed_min < cfg["engine"]["cooldown_minutes"]:
            return
    if zid in cooldowns:
        return
    open_valve(con, zone, "auto", rec["minutes"], cfg)
    cooldowns.add(zid)
