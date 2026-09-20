import datetime
import threading
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, TabbedContent, TabPane
from sinchai import clock, config, db, farm, demo as demo_mod
from sinchai.screens import DashboardScreen, ZoneScreen, ReportsScreen, RainCheckScreen, SettingsScreen
from sinchai.sensors import SimulatedSensor


class SinchaiApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("d", "switch_tab('dashboard')", "Dashboard"),
        ("z", "switch_tab('zones')", "Zones"),
        ("r", "switch_tab('reports')", "Reports"),
        ("l", "switch_tab('raincheck')", "Rain-check"),
        ("s", "switch_tab('settings')", "Settings"),
        ("t", "toggle_theme", "Theme"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, db_path, cfg, demo, speed, seed, source, mode):
        super().__init__()
        self.db_path = db_path
        self.cfg = cfg
        self.demo = demo
        self.speed = speed
        self.seed = seed
        self.source = source
        self.mode = mode
        self.con = None
        self.sensor = None
        self.scenario = None
        self.weather_data = None
        self._tick_thread = None
        self._running = False

    def compose(self):
        yield Header()
        with TabbedContent(id="tabs"):
            with TabPane("Dashboard", id="dashboard"):
                yield DashboardScreen(app_ref=self)
            with TabPane("Zones", id="zones"):
                yield ZoneScreen(app_ref=self)
            with TabPane("Reports", id="reports"):
                yield ReportsScreen(app_ref=self)
            with TabPane("Rain-check", id="raincheck"):
                yield RainCheckScreen(app_ref=self)
            with TabPane("Settings", id="settings"):
                yield SettingsScreen(app_ref=self)
        yield Footer()

    def on_mount(self):
        self.con = db.open_db(self.db_path)
        farm._seed_data(self.con, self.cfg)
        farm._check_second_controller(self.con)
        farm._recover_valves(self.con)
        zones = db.get_zones(self.con)
        self.title = "Sinchai"
        self.sub_title = f"{self.source.upper()} | {self.mode.upper()}"
        self.sensor = SimulatedSensor(zones, self.cfg, self.seed)
        if self.demo:
            self.scenario = demo_mod.setup_demo(self.speed)
            for zid, m in self.scenario.get("zone_initial_moisture", {}).items():
                self.sensor.moisture[int(zid)] = float(m)
        self._running = True
        self._tick_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._tick_thread.start()
        self.set_interval(1.0, self._refresh_ui)

    def _run_loop(self):
        import time, os as _os
        from sinchai import weather
        started_at = clock.to_iso(clock.now())
        while self._running:
            hb = clock.to_iso(clock.now())
            db.upsert_controller(self.con, _os.getpid(), started_at, hb, hb, self.mode, self.source, self.demo, self.speed)
            zones = db.get_zones(self.con)
            if not self.demo:
                self.weather_data = weather.get_weather(self.con, self.cfg)
            elif self.scenario:
                wkm, r_mm = demo_mod.get_demo_weather_at(self.scenario, clock.now())
                if r_mm > 0:
                    db.upsert_rain_obs(self.con, hb[:13] + ":00:00Z", r_mm)
                f_mm, f_prob = demo_mod.get_demo_forecast_at(self.scenario, clock.now())
                times = [clock.to_iso(clock.now() + datetime.timedelta(hours=i)) for i in range(1, 13)]
                self.weather_data = {"wind_kmh": wkm, "temperature_c": 30.0, "current_precip_mm": r_mm,
                                     "hourly_times": times, "hourly_precip_mm": [f_mm / 12.0] * 12, "hourly_precip_prob": [f_prob] * 12,
                                     "hourly_evaporation_mm": [0.3] * 12, "hourly_wind_kmh": [wkm] * 12, "hourly_temp_c": [30.0] * 12,
                                     "source": "scripted", "fetched_at": hb}
            farm.tick(self.con, zones, self.sensor, self.weather_data, self.mode, self.demo, self.scenario, self.cfg)
            time.sleep(0.1 if self.demo else self.cfg["sensor"]["poll_seconds"])

    def _refresh_ui(self):
        for screen_id in ("dashboard", "zones", "reports", "raincheck"):
            pane = self.query_one(f"#{screen_id}")
            for child in pane.children:
                if hasattr(child, "refresh_data"):
                    child.refresh_data()

    def action_switch_tab(self, tab_id):
        self.query_one("#tabs").active = tab_id

    def action_toggle_theme(self):
        self.dark = not self.dark

    def on_unmount(self):
        self._running = False
        if self.con:
            db.close_all_valves(self.con, clock.to_iso(clock.now()), "failsafe")
            db.clear_controller(self.con)
