from textual.app import ComposeResult
from textual.widgets import Static, Sparkline
from textual.containers import VerticalScroll
from sinchai import clock, db, engine, ledger, reports

class DashboardScreen(Static):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

    def compose(self):
        yield Static(id="status-bar")
        yield Static("[SIMULATED DATA]", id="sim-banner", classes="visible" if (self.app_ref.demo or self.app_ref.source == "sim") else "")
        yield VerticalScroll(id="zone-cards")

    def refresh_data(self):
        con = self.app_ref.con
        if con is None:
            return
        zones = db.get_zones(con)
        cfg = self.app_ref.cfg
        now_iso = clock.to_iso(clock.now())
        local_min = clock.local_minutes(clock.now(), cfg["location"]["utc_offset_minutes"])
        w = self.app_ref.weather_data
        cards = self.query_one("#zone-cards")
        cards.remove_children()
        for zone in zones:
            crop = db.get_crop(con, zone["crop"])
            readings = db.get_recent_readings(con, zone["id"], 24)
            rec = engine.decide(zone, crop, readings, w, now_iso, local_min, cfg)
            m = readings[0]["moisture_pct"] if readings else None
            mn = zone["min_pct"] if zone["min_pct"] is not None else (crop["min_pct"] if crop else 45)
            label = "LOW" if m is not None and m < mn else ("WET" if m is not None and m > 90 else "OK")
            v_str = "OPEN" if zone["valve_open"] else "closed"
            m_str = f"{m:.0f}%" if m is not None else "no data"
            line1 = f"{zone['name']} | {zone['crop']} | moisture {m_str} ({label}) | valve {v_str}"
            cards.mount(Static(f"{line1}\n  {rec['action']}: {rec['reason']}", classes="zone-card"))
        open_c = sum(1 for z in zones if z["valve_open"])
        w_src = w["source"].upper() if w else "OFFLINE"
        status = f"SIM | weather {w_src} | mode {self.app_ref.mode.upper()} | {open_c} open | {now_iso[:19]}"
        self.query_one("#status-bar").update(status)

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
        for zone in db.get_zones(con):
            crop = db.get_crop(con, zone["crop"])
            readings = db.get_recent_readings(con, zone["id"], 120)
            rec = engine.decide(zone, crop, readings, self.app_ref.weather_data, now_iso, local_min, cfg)
            hist = [r["moisture_pct"] for r in reversed(readings)]
            hrs = f"{rec['hours_until']:.1f}h" if rec.get("hours_until") is not None else "unknown"
            v_str = "OPEN" if zone["valve_open"] else "closed"
            text = f"{zone['name']} ({zone['crop']}) | area {zone['area_m2']} m2 | {zone['irrigation']}\n  Action: {rec['action']} | {rec['reason']}\n  Time until min: {hrs} | Valve: {v_str}"
            detail.mount(Static(text))
            if hist:
                detail.mount(Sparkline(hist, summary_function=max))

class ReportsScreen(Static):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

    def compose(self):
        yield VerticalScroll(id="report-content")

    def refresh_data(self):
        con = self.app_ref.con
        if con is None:
            return
        content = self.query_one("#report-content")
        content.remove_children()
        content.mount(Static("Baseline: 30 min irrigation per day per zone at zone flow rate (assumed, not measured)."))
        for r in reports.zone_report(con, db.get_zones(con), self.app_ref.cfg, 7):
            content.mount(Static(f"{r['name']} ({r['crop']}): {r['litres_used']:,.0f} L used / {r['baseline_litres']:,.0f} L baseline | stress: {r['stress_hours']:.1f} h below min"))

class RainCheckScreen(Static):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

    def compose(self):
        yield VerticalScroll(id="ledger-content")

    def refresh_data(self):
        con = self.app_ref.con
        if con is None:
            return
        content = self.query_one("#ledger-content")
        content.remove_children()
        content.mount(Static("Actual rain comes from a weather model, not a rain gauge."))
        content.mount(Static(ledger.ledger_summary(con)))
        for r in con.execute("SELECT * FROM skips ORDER BY decided_at DESC LIMIT 20").fetchall():
            act = f"{r['actual_mm']:.1f}mm" if r["actual_mm"] is not None else "pending"
            content.mount(Static(f"{r['decided_at'][:10]} zone {r['zone_id']} | forecast {r['forecast_mm']:.1f}mm | actual {act} | {r['verdict'] or 'pending'}"))

class SettingsScreen(Static):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

    def compose(self):
        yield Static(f"Settings\nMode: {self.app_ref.mode}\nSource: {self.app_ref.source}\nDemo: {self.app_ref.demo}\nDB: {self.app_ref.db_path}")
