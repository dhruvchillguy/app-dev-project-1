from textual.app import ComposeResult
from textual.widgets import DataTable, Static
from sinchai import clock, db, engine

class DashboardScreen(Static):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref
        self.cols = None

    def compose(self):
        yield Static(id="status-bar")
        cls = "visible" if (self.app_ref.demo or self.app_ref.source == "sim") else ""
        yield Static("[SIMULATED DATA]", id="sim-banner", classes=cls)
        yield DataTable(id="zone-table", cursor_type="row")
        yield Static(id="weather-panel")
        yield Static(id="alerts-feed")

    def on_mount(self):
        t = self.query_one(DataTable)
        self.cols = t.add_columns("Zone", "Crop", "Moisture", "Status Bar", "Recommendation", "Valve", "Next Due")
        for z in [1, 2, 3]:
            t.add_row(f"Zone {z}", "-", "-", "-", "-", "-", "-", key=str(z))

    def refresh_data(self):
        con = self.app_ref.con
        if con is None:
            return
        zones = db.get_zones(con)
        cfg = self.app_ref.cfg
        now_iso = clock.to_iso(clock.now())
        local_min = clock.local_minutes(clock.now(), cfg["location"]["utc_offset_minutes"])
        w = self.app_ref.weather_data
        t = self.query_one(DataTable)

        open_c = 0
        for zone in zones:
            zid = zone["id"]
            crop = db.get_crop(con, zone["crop"])
            readings = db.get_recent_readings(con, zid, 24)
            rec = engine.decide(zone, crop, readings, w, now_iso, local_min, cfg)
            m = readings[0]["moisture_pct"] if readings else None
            mn = zone["min_pct"] if zone["min_pct"] is not None else (crop["min_pct"] if crop else 45)
            label = "LOW" if m is not None and m < mn else ("WET" if m is not None and m > 90 else "OK")
            pct = min(100.0, max(0.0, m)) if m is not None else 0.0
            filled = int(round(pct / 10.0))
            bar_str = f"[{'█' * filled}{'░' * (10 - filled)}] {label}"
            m_str = f"{m:.0f}%" if m is not None else "no data"
            v_open = zone["valve_open"] == 1
            if v_open:
                open_c += 1
                v_str = f"OPEN ({rec.get('minutes', 0)}m left)"
            else:
                v_str = "CLOSED"
            action_str = f"{rec['action']} ({rec['reason'][:35]})"
            hrs_str = f"{rec['hours_until']:.1f}h" if rec.get("hours_until") is not None else "unknown"

            if self.cols:
                vals = [zone["name"], zone["crop"], m_str, bar_str, action_str, v_str, hrs_str]
                for col_key, val in zip(self.cols, vals):
                    t.update_cell(str(zid), col_key, val)

        src = self.app_ref.source.upper()
        w_src = w["source"].upper() if w else "OFFLINE"
        mode = self.app_ref.mode.upper()
        ts_disp = now_iso.replace("T", " ")[:19]
        status = f"{src} | weather {w_src} | mode {mode} | {ts_disp} | {open_c} open"
        self.query_one("#status-bar").update(status)

        if w:
            temp = f"{w.get('temperature_c', 0.0):.1f}°C"
            wind = f"{w.get('wind_kmh', 0.0):.1f} km/h"
            hum = f"{w.get('humidity', 60)}%"
            rain_12h = sum(r for r in w.get("hourly_precip_mm", [])[:12] if r is not None)
            prob_12h = max([p for p in w.get("hourly_precip_prob", [])[:12] if p is not None] or [0])
            evap = sum(e for e in w.get("hourly_evaporation_mm", [])[:12] if e is not None)
            w_text = f"Weather | Temp: {temp} | Humidity: {hum} | Wind: {wind} | Rain next 12h: {rain_12h:.1f}mm ({prob_12h:.0f}%) | Evap: {evap:.1f}mm"
        else:
            w_text = "Weather: OFFLINE"
        self.query_one("#weather-panel").update(w_text)

        alerts = con.execute("SELECT ts, zone_id, severity, message FROM alerts ORDER BY ts DESC LIMIT 8").fetchall()
        if alerts:
            lines = ["Alerts Feed:"]
            for a in alerts:
                lines.append(f"  [{a['ts'][11:19]}] Zone {a['zone_id']} | {a['severity'].upper()} | {a['message']}")
            a_text = "\n".join(lines)
        else:
            a_text = "Alerts Feed: No active alerts"
        self.query_one("#alerts-feed").update(a_text)
