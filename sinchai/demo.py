import datetime
import importlib.resources
import tomllib
from sinchai import clock


def load_scenario():
    pkg = importlib.resources.files("sinchai")
    return tomllib.loads((pkg / "demo_scenario.toml").read_bytes().decode())


def setup_demo(speed):
    scenario = load_scenario()
    start_str = scenario.get("start_time", "2026-09-20T05:00:00Z")
    start_dt = clock.from_iso(start_str)
    clock.configure_demo(start_dt, speed)
    return scenario


def get_demo_weather_at(scenario, now_dt):
    events = scenario.get("weather_events", [])
    wind = scenario.get("base_wind_kmh", 10.0)
    rain_mm = 0.0
    for ev in events:
        ev_dt = clock.from_iso(ev["at"])
        if ev_dt <= now_dt:
            if ev.get("type") == "wind":
                wind = ev.get("wind_kmh", wind)
            if ev.get("type") == "rain":
                if 0 <= (now_dt - ev_dt).total_seconds() < 3600:
                    rain_mm = ev.get("mm", 0.0)
    return wind, rain_mm


def get_demo_forecast_at(scenario, now_dt):
    events = scenario.get("forecast_events", [])
    for ev in sorted(events, key=lambda e: e["at"], reverse=True):
        ev_dt = clock.from_iso(ev["at"])
        if ev_dt <= now_dt:
            return ev.get("precip_mm", 0.0), ev.get("precip_prob", 0)
    return 0.0, 0


def get_dropout_zones(scenario, now_dt):
    dropouts = scenario.get("dropout_events", [])
    active = set()
    for ev in dropouts:
        start = clock.from_iso(ev["start"])
        end = clock.from_iso(ev["end"])
        if start <= now_dt <= end:
            active.add(ev["zone_id"])
    return active
