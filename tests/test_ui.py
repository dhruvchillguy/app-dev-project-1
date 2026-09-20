import asyncio, tempfile, os
import pytest
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
        dash = app.query_one("DashboardScreen")
        status_bar = dash.query_one("#status-bar")
        sim_banner = dash.query_one("#sim-banner")
        cards = dash.query_one("#zone-cards")
        
        # Verify status bar is non-empty
        assert status_bar.content != "", "Status bar must not be empty"
        assert "SIM" in status_bar.content
        assert "weather" in status_bar.content.lower()
        
        # Verify banner contains SIMULATED
        assert "SIMULATED" in sim_banner.content
        
        # Verify 3 zone rows exist with non-empty moisture and status text
        assert len(cards.children) == 3, f"Expected 3 zone cards, got {len(cards.children)}"
        for card in cards.children:
            text = card.content
            assert text != "", "Zone card text must not be empty"
            assert "moisture" in text.lower()
            assert ("LOW" in text or "OK" in text or "WET" in text)
    if os.path.exists(tmp_db):
        os.remove(tmp_db)
