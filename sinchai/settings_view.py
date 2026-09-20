from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, Static, Switch
from sinchai import config, db


class SettingsScreen(Static):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

    def compose(self):
        cfg = self.app_ref.cfg
        with VerticalScroll():
            yield Label("System Settings")
            with Horizontal():
                yield Label("Mode (OFF=Manual, ON=Auto): ")
                yield Switch(value=self.app_ref.mode == "auto", id="mode-switch")
            yield Label("Location")
            with Horizontal():
                yield Label("Latitude: ")
                yield Input(value=str(cfg["location"]["latitude"]), id="input-lat")
                yield Label("", id="err-lat", classes="error-msg")
            with Horizontal():
                yield Label("Longitude: ")
                yield Input(value=str(cfg["location"]["longitude"]), id="input-lon")
                yield Label("", id="err-lon", classes="error-msg")
            yield Label("Sensor Raw Calibration")
            with Horizontal():
                yield Label("Dry Raw: ")
                yield Input(value=str(cfg["sensor"]["dry_raw"]), id="input-dry")
                yield Label("Wet Raw: ")
                yield Input(value=str(cfg["sensor"]["wet_raw"]), id="input-wet")
                yield Label("", id="err-sensor", classes="error-msg")
            yield Label("Zone Threshold Overrides")
            for zid in (1, 2, 3):
                with Horizontal():
                    yield Label(f"Zone {zid} Min%: ")
                    yield Input(value="", id=f"input-min-{zid}")
                    yield Label(f" Target%: ")
                    yield Input(value="", id=f"input-tgt-{zid}")
                    yield Label("", id=f"err-zone-{zid}", classes="error-msg")
            yield Button("Save Settings", id="btn-save")

    def refresh_data(self):
        sw = self.query_one("#mode-switch", Switch)
        if sw.value != (self.app_ref.mode == "auto"):
            sw.value = (self.app_ref.mode == "auto")

    def on_switch_changed(self, event):
        if event.switch.id == "mode-switch":
            self.app_ref.mode = "auto" if event.value else "manual"
            self.app_ref.sub_title = f"{self.app_ref.source.upper()} | {self.app_ref.mode.upper()}"
            if self.app_ref.con:
                self.app_ref.con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('mode', ?)", (self.app_ref.mode,))
                self.app_ref.con.commit()

    def on_button_pressed(self, event):
        if event.button.id == "btn-save": self.save_settings()

    def on_input_submitted(self, event): self.save_settings()

    def on_input_changed(self, event): self.save_settings()

    def save_settings(self):
        con = self.app_ref.con
        if not con: return
        valid = True
        try:
            lat = float(self.query_one("#input-lat").value)
            if not (-90.0 <= lat <= 90.0): raise ValueError("Latitude must be between -90 and 90")
            self.query_one("#err-lat").update("")
        except Exception as e:
            self.query_one("#err-lat").update(str(e))
            valid = False
        try:
            lon = float(self.query_one("#input-lon").value)
            if not (-180.0 <= lon <= 180.0): raise ValueError("Longitude must be between -180 and 180")
            self.query_one("#err-lon").update("")
        except Exception as e:
            self.query_one("#err-lon").update(str(e))
            valid = False
        try:
            dry = int(self.query_one("#input-dry").value)
            wet = int(self.query_one("#input-wet").value)
            if dry == wet: raise ValueError("dry_raw cannot equal wet_raw")
            self.query_one("#err-sensor").update("")
        except Exception as e:
            self.query_one("#err-sensor").update(str(e))
            valid = False
        for zid in (1, 2, 3):
            mn_s = self.query_one(f"#input-min-{zid}").value.strip()
            tg_s = self.query_one(f"#input-tgt-{zid}").value.strip()
            if mn_s or tg_s:
                try:
                    mn = float(mn_s) if mn_s else None
                    tg = float(tg_s) if tg_s else None
                    if mn is not None and tg is not None and mn >= tg:
                        raise ValueError(f"Zone {zid}: min must be less than target")
                    self.query_one(f"#err-zone-{zid}").update("")
                except Exception as e:
                    self.query_one(f"#err-zone-{zid}").update(str(e))
                    valid = False
        if not valid: return
        for k, v in (("location.latitude", lat), ("location.longitude", lon), ("sensor.dry_raw", dry), ("sensor.wet_raw", wet)):
            con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
        for zid in (1, 2, 3):
            mn_s = self.query_one(f"#input-min-{zid}").value.strip()
            tg_s = self.query_one(f"#input-tgt-{zid}").value.strip()
            if mn_s:
                con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"zone.{zid}.min_pct", mn_s))
                con.execute("UPDATE zones SET min_pct=? WHERE id=?", (float(mn_s), zid))
            if tg_s:
                con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"zone.{zid}.target_pct", tg_s))
                con.execute("UPDATE zones SET target_pct=? WHERE id=?", (float(tg_s), zid))
        con.commit()
        self.app_ref.cfg = config.get_config(self.app_ref.db_path)
