import asyncio, tempfile, os
import pytest
from textual.widgets import DataTable, Sparkline
from sinchai import config, db
from sinchai.app import SinchaiApp

@pytest.mark.asyncio
async def test_dashboard_populated_after_5_ticks():
    tmp_db = tempfile.mktemp(suffix=".db")
    cfg = config.get_config(tmp_db)
    app = SinchaiApp(db_path=tmp_db, cfg=cfg, demo=True, speed=1800.0, seed=42, source="sim", mode="auto")
    async with app.run_test(size=(100, 30)) as pilot:
        for _ in range(5):
            await pilot.pause(0.2)
        assert app.title == "Sinchai"
        assert "SIM" in app.sub_title
        
        dash = app.query_one("DashboardScreen")
        status_bar = dash.query_one("#status-bar")
        sim_banner = dash.query_one("#sim-banner")
        table = dash.query_one(DataTable)
        weather_panel = dash.query_one("#weather-panel")
        alerts_feed = dash.query_one("#alerts-feed")
        
        assert status_bar.content != ""
        assert "SIM" in status_bar.content
        assert "weather" in status_bar.content.lower()
        assert "mode AUTO" in status_bar.content
        assert "SIMULATED" in sim_banner.content
        assert table.row_count == 3
        cell_val = str(table.get_cell("1", dash.cols[3]))
        assert "LOW" in cell_val or "OK" in cell_val or "WET" in cell_val
        assert "Weather" in weather_panel.content
        assert "Alerts Feed" in alerts_feed.content
    if os.path.exists(tmp_db):
        os.remove(tmp_db)

@pytest.mark.asyncio
async def test_controls_and_zones_tab():
    tmp_db = tempfile.mktemp(suffix=".db")
    cfg = config.get_config(tmp_db)
    app = SinchaiApp(db_path=tmp_db, cfg=cfg, demo=True, speed=1800.0, seed=42, source="sim", mode="manual")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.2)
        assert app.mode == "manual"
        await pilot.press("m")
        assert app.mode == "auto"
        await pilot.press("m")
        assert app.mode == "manual"
        
        z = db.get_zones(app.con)[0]
        assert z["valve_open"] == 0
        await pilot.press("v")
        z = db.get_zones(app.con)[0]
        assert z["valve_open"] == 1
        
        await pilot.press("z")
        await pilot.pause(0.2)
        zone_screen = app.query_one("ZoneScreen")
        sparklines = zone_screen.query(Sparkline)
        assert len(sparklines) >= 1
    if os.path.exists(tmp_db):
        os.remove(tmp_db)

@pytest.mark.asyncio
async def test_settings_screen():
    tmp_db = tempfile.mktemp(suffix=".db")
    cfg = config.get_config(tmp_db)
    app = SinchaiApp(db_path=tmp_db, cfg=cfg, demo=True, speed=1800.0, seed=42, source="sim", mode="auto")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("s")
        await pilot.pause(0.2)
        settings = app.query_one("SettingsScreen")
        
        lat_input = settings.query_one("#input-lat")
        lat_input.value = "999"
        await pilot.pause(0.1)
        settings.save_settings()
        err_lat = settings.query_one("#err-lat")
        assert "between -90 and 90" in str(err_lat.content)
        
        lat_input.value = "25.5"
        await pilot.pause(0.1)
        settings.save_settings()
        assert str(err_lat.content) == ""
        val = app.con.execute("SELECT value FROM settings WHERE key='location.latitude'").fetchone()[0]
        assert val == "25.5"
        
        min1 = settings.query_one("#input-min-1")
        tgt1 = settings.query_one("#input-tgt-1")
        min1.value = "80"
        tgt1.value = "60"
        await pilot.pause(0.1)
        settings.save_settings()
        err_z1 = settings.query_one("#err-zone-1")
        assert "less than target" in str(err_z1.content)
        
        tgt1.value = "90"
        await pilot.pause(0.1)
        settings.save_settings()
        assert str(err_z1.content) == ""
        z1 = db.get_zones(app.con)[0]
        assert z1["min_pct"] == 80.0
        assert z1["target_pct"] == 90.0
    if os.path.exists(tmp_db):
        os.remove(tmp_db)
