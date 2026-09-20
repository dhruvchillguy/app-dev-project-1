import json
import os
import pytest
from sinchai import weather, clock, db

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "open_meteo_live.json")


def test_parse_live_fixture():
    with open(FIXTURE) as f:
        payload = f.read()
    w = weather._parse(payload)
    assert w["temperature_c"] is not None
    assert isinstance(w["hourly_times"], list)
    assert len(w["hourly_times"]) > 0
    assert w["source"] == "live"


def test_missing_hourly_tolerated():
    payload = json.dumps({"current": {"temperature_2m": 25.0, "wind_speed_10m": 5.0, "precipitation": 0.0}})
    w = weather._parse(payload)
    assert w["temperature_c"] == 25.0
    assert w["hourly_precip_mm"] == []


def test_malformed_json():
    with pytest.raises(Exception):
        weather._parse("not json")


def test_get_weather_uses_cache(tmp_path):
    import tomllib, importlib.resources
    cfg_bytes = importlib.resources.files("sinchai").joinpath("defaults.toml").read_bytes()
    cfg = tomllib.loads(cfg_bytes.decode())
    cfg["weather"]["refresh_minutes"] = 60
    con = db.open_db(str(tmp_path / "test.db"))
    with open(FIXTURE) as f:
        payload = f.read()
    key = f"{round(cfg['location']['latitude'],2)},{round(cfg['location']['longitude'],2)}"
    db.upsert_weather_cache(con, key, clock.to_iso(clock.now()), payload)
    w = weather.get_weather(con, cfg)
    assert w is not None
    assert w["source"] in ("live", "cached")
