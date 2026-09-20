from textual.app import ComposeResult
from textual.widgets import Sparkline, Static
from textual.containers import VerticalScroll
from sinchai import clock, db, engine

class ZoneScreen(Static):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

    def compose(self):
        yield VerticalScroll(id="zone-detail")

    def refresh_data(self):
        con = self.app_ref.con
        if con is None:
            return
        detail = self.query_one("#zone-detail")
        detail.remove_children()
        cfg = self.app_ref.cfg
        now_iso = clock.to_iso(clock.now())
        local_min = clock.local_minutes(clock.now(), cfg["location"]["utc_offset_minutes"])
        zid = getattr(self.app_ref, "selected_zone_id", 1)
        zone = next((z for z in db.get_zones(con) if z["id"] == zid), None)
        if zone is None:
            return
        crop = db.get_crop(con, zone["crop"])
        readings = db.get_recent_readings(con, zid, 120)
        rec = engine.decide(zone, crop, readings, self.app_ref.weather_data, now_iso, local_min, cfg)
        hist = [r["moisture_pct"] for r in reversed(readings)]
        v_str = f"OPEN (since {zone['valve_opened_at'][11:19]})" if zone["valve_open"] else "CLOSED"
        mn = zone["min_pct"] if zone["min_pct"] is not None else (crop["min_pct"] if crop else 45)
        tgt = zone["target_pct"] if zone["target_pct"] is not None else (crop["target_pct"] if crop else 85)
        crit = cfg["crops"].get(zone["crop"], {}).get("critical_pct", 40)
        
        info1 = f"{zone['name']} ({zone['crop']}) | Area: {zone['area_m2']} m2 | Flow: {zone['flow_mm_hr']} mm/hr ({zone['irrigation']})"
        info2 = f"Thresholds: Min {mn}% | Target {tgt}% | Critical {crit}% | Valve: {v_str}"
        info3 = f"Recommendation: {rec['action']} | {rec['reason']}"
        detail.mount(Static(f"{info1}\n{info2}\n{info3}"))
        if hist:
            detail.mount(Static(f"Moisture History (last {len(hist)} readings):"))
            detail.mount(Sparkline(hist, summary_function=max))
        detail.mount(Static("Decision Trace:"))
        for step in rec.get("trace", []):
            detail.mount(Static(f"  - {step}"))
