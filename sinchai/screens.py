from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll
from sinchai import db, ledger, reports
from sinchai.dashboard import DashboardScreen
from sinchai.zone_view import ZoneScreen
from sinchai.settings_view import SettingsScreen

class ReportsScreen(Static):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

    def compose(self):
        yield VerticalScroll(id="report-content")

    def refresh_data(self):
        con = self.app_ref.con
        if con is None: return
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
        if con is None: return
        content = self.query_one("#ledger-content")
        content.remove_children()
        content.mount(Static("Actual rain comes from a weather model, not a rain gauge."))
        content.mount(Static(ledger.ledger_summary(con)))
        query = "SELECT s.*, z.crop FROM skips s JOIN zones z ON s.zone_id = z.id ORDER BY s.decided_at DESC LIMIT 20"
        for r in con.execute(query).fetchall():
            act = f"{r['actual_mm']:.1f}mm" if r["actual_mm"] is not None else "pending"
            low = f"{r['min_moisture']:.1f}%" if r["min_moisture"] is not None else "n/a"
            content.mount(Static(f"{r['decided_at'][:16]} | Zone {r['zone_id']} ({r['crop']}) | Forecast: {r['forecast_mm']:.1f}mm | Actual: {act} | Verdict: {r['verdict'] or 'PENDING'} | Lowest: {low}"))
