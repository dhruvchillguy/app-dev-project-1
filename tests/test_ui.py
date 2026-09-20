import asyncio, tempfile, os
import pytest
from textual.widgets import DataTable
from sinchai import config
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
        
        # Verify status bar
        assert status_bar.content != ""
        assert "SIM" in status_bar.content
        assert "weather" in status_bar.content.lower()
        assert "mode AUTO" in status_bar.content
        
        # Verify banner
        assert "SIMULATED" in sim_banner.content
        
        # Verify table has 3 rows with zone data
        assert table.row_count == 3
        cell_val = str(table.get_cell("1", dash.cols[3]))
        assert "LOW" in cell_val or "OK" in cell_val or "WET" in cell_val
        
        # Verify weather panel
        assert "Weather" in weather_panel.content
        assert "Temp:" in weather_panel.content
        assert "Wind:" in weather_panel.content
        
        # Verify alerts feed
        assert "Alerts Feed" in alerts_feed.content
    if os.path.exists(tmp_db):
        os.remove(tmp_db)
