import pytest
from sinchai.reports import baseline_litres
from sinchai.engine import _duration


def test_litres_formula():
    # 20mm on 500m2 = 10,000 L
    mm = 20.0
    area = 500.0
    litres = mm / 1000.0 * 1000.0 * area
    assert abs(litres - 10000.0) < 0.01


def test_baseline_litres():
    zone = {"flow_mm_hr": 8.0, "area_m2": 400, "id": 1, "name": "Z1", "crop": "tomato",
            "irrigation": "drip", "min_pct": None, "target_pct": None}
    import tomllib, importlib.resources
    cfg = tomllib.loads(importlib.resources.files("sinchai").joinpath("defaults.toml").read_bytes().decode())
    base = baseline_litres(zone, cfg, 1)
    expected = 8.0 * (30.0 / 60.0) * 400.0
    assert abs(base - expected) < 0.01


def test_duration_tomato_drip():
    # tomato drip: moisture=60, target=85, wh=75mm, flow=8mm/hr, eff=0.9
    mins, capped = _duration(60, 85, 75, 8, 0.9, 180)
    # deficit = (85-60)/100*75 = 18.75mm; mins = 18.75/(8*0.9)*60 = 156.25
    assert abs(mins - 156.25) < 0.1
    assert not capped


def test_duration_cap():
    mins, capped = _duration(0, 100, 500, 8, 0.9, 180)
    assert mins == 180
    assert capped


def test_baseline_7day():
    zone = {"flow_mm_hr": 10.0, "area_m2": 400, "id": 2, "name": "Z2", "crop": "maize",
            "irrigation": "sprinkler", "min_pct": None, "target_pct": None}
    import tomllib, importlib.resources
    cfg = tomllib.loads(importlib.resources.files("sinchai").joinpath("defaults.toml").read_bytes().decode())
    base = baseline_litres(zone, cfg, 7)
    # 30 min/day * 7 days = 210 min = 3.5 hrs; 10 mm/hr * 3.5 * 400 = 14000 L
    assert abs(base - 14000.0) < 0.01
