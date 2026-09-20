import pytest
from sinchai import clock
from sinchai.engine import decide, _duration, _next_window


CROP = {"name": "tomato", "crop_factor": 1.15, "water_holding_mm": 75, "min_pct": 60, "target_pct": 85, "note": "approx"}
ZONE_DRIP = {"id": 1, "name": "Z1", "crop": "tomato", "area_m2": 400, "irrigation": "drip", "flow_mm_hr": 8, "min_pct": None, "target_pct": None, "valve_open": 0, "valve_opened_at": None, "last_closed_at": None}
ZONE_SPR = {"id": 2, "name": "Z2", "crop": "maize", "area_m2": 1200, "irrigation": "sprinkler", "flow_mm_hr": 10, "min_pct": None, "target_pct": None, "valve_open": 0, "valve_opened_at": None, "last_closed_at": None}

CFG = {
    "engine": {"sensor_offline_minutes": 15, "rain_lookahead_hours": 12, "rain_skip_mm": 5.0,
               "rain_skip_prob": 70, "rain_skip_prob_min_mm": 2.0, "wind_limit_kmh": 25,
               "critical_margin_pts": 15, "max_run_minutes": 180, "waterlog_pct": 100,
               "waterlog_hours": 3, "windows": ["05:00-09:00", "17:00-20:00"]},
    "efficiency": {"drip": 0.9, "sprinkler": 0.75, "flood": 0.6},
    "location": {"utc_offset_minutes": 330},
}

def make_readings(n, moisture, now_iso):
    return [{"moisture_pct": moisture, "ts": now_iso} for _ in range(n)]


def test_no_data_empty_readings():
    now = "2026-09-20T06:00:00Z"
    rec = decide(ZONE_DRIP, CROP, [], None, now, 330, CFG)
    assert rec["action"] == "NO_DATA"


def test_stale_reading_offline():
    now = "2026-09-20T08:00:00Z"
    old = "2026-09-20T07:44:00Z"
    readings = [{"moisture_pct": 65, "ts": old}]
    rec = decide(ZONE_DRIP, CROP, readings, None, now, 330, CFG)
    assert rec["action"] == "NO_DATA"


def test_fresh_reading_ok():
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 70.0, now)
    rec = decide(ZONE_DRIP, CROP, readings, None, now, 330, CFG)
    assert rec["action"] == "OK"


def test_rain_skip_by_volume():
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 58.0, now)
    times = [f"2026-09-20T{6+i:02d}:00:00Z" for i in range(13)]
    weather = {"hourly_times": times, "hourly_precip_mm": [0]*3 + [5.0]*10, "hourly_precip_prob": [50]*13,
               "hourly_evaporation_mm": [0.3]*13, "wind_kmh": 5.0, "temperature_c": 28}
    rec = decide(ZONE_DRIP, CROP, readings, weather, now, 330, CFG)
    assert rec["action"] == "SKIP_RAIN"


def test_rain_just_below_volume_no_skip():
    # total=4.9mm < 5mm skip_mm, prob=60% < 70% so no skip by volume or probability
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 58.0, now)
    times = [f"2026-09-20T{6+i:02d}:00:00Z" for i in range(13)]
    weather = {"hourly_times": times, "hourly_precip_mm": [4.9] + [0]*12, "hourly_precip_prob": [60]*13,
               "hourly_evaporation_mm": [0.3]*13, "wind_kmh": 5.0, "temperature_c": 28}
    rec = decide(ZONE_DRIP, CROP, readings, weather, now, 330, CFG)
    assert rec["action"] == "IRRIGATE_NOW"


def test_rain_skip_by_probability():
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 58.0, now)
    times = [f"2026-09-20T{6+i:02d}:00:00Z" for i in range(13)]
    weather = {"hourly_times": times, "hourly_precip_mm": [2.0]*12 + [0], "hourly_precip_prob": [70]*12 + [0],
               "hourly_evaporation_mm": [0.3]*13, "wind_kmh": 5.0, "temperature_c": 28}
    rec = decide(ZONE_DRIP, CROP, readings, weather, now, 330, CFG)
    assert rec["action"] == "SKIP_RAIN"


def test_critical_overrides_rain_skip():
    now = "2026-09-20T06:00:00Z"
    critical_moisture = 60 - 15 - 1  # below critical
    readings = make_readings(4, critical_moisture, now)
    times = [f"2026-09-20T{6+i:02d}:00:00Z" for i in range(13)]
    weather = {"hourly_times": times, "hourly_precip_mm": [10.0]*12 + [0], "hourly_precip_prob": [90]*12 + [0],
               "hourly_evaporation_mm": [0.3]*13, "wind_kmh": 5.0, "temperature_c": 28}
    rec = decide(ZONE_DRIP, CROP, readings, weather, now, 330, CFG)
    assert rec["action"] == "IRRIGATE_NOW"
    assert "critical" in rec["reason"]


def test_wind_blocks_sprinkler():
    CROP2 = {"name": "maize", "crop_factor": 1.2, "water_holding_mm": 120, "min_pct": 45, "target_pct": 85, "note": "approx"}
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 44.0, now)  # below maize min=45
    weather = {"hourly_times": [], "hourly_precip_mm": [], "hourly_precip_prob": [],
               "hourly_evaporation_mm": [], "wind_kmh": 25.1, "temperature_c": 28}
    rec = decide(ZONE_SPR, CROP2, readings, weather, now, 330, CFG)
    assert rec["action"] == "WAIT_WIND"


def test_wind_ok_at_limit():
    CROP2 = {"name": "maize", "crop_factor": 1.2, "water_holding_mm": 120, "min_pct": 45, "target_pct": 85, "note": "approx"}
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 44.0, now)  # below maize min=45
    weather = {"hourly_times": [], "hourly_precip_mm": [], "hourly_precip_prob": [],
               "hourly_evaporation_mm": [], "wind_kmh": 25.0, "temperature_c": 28}
    rec = decide(ZONE_SPR, CROP2, readings, weather, now, 330, CFG)
    assert rec["action"] in ("IRRIGATE_NOW", "IRRIGATE_LATER")


def test_irrigate_later_outside_window():
    now = "2026-09-20T10:00:00Z"
    readings = make_readings(4, 58.0, now)
    local_min = 15 * 60 + 30  # 15:30 local IST, outside both windows
    rec = decide(ZONE_DRIP, CROP, readings, None, now, local_min, CFG)
    assert rec["action"] == "IRRIGATE_LATER"


def test_duration_hand_checked():
    mins, capped = _duration(60, 85, 75, 8, 0.9, 180)
    # deficit_mm = (85-60)/100*75 = 18.75mm, mins = 18.75/(8*0.9)*60 = 156.25
    assert abs(mins - 156.25) < 0.01
    assert not capped


def test_duration_capped():
    mins, capped = _duration(0, 100, 500, 8, 0.9, 180)
    assert mins == 180
    assert capped


def test_at_minimum_is_ok():
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 60.0, now)
    rec = decide(ZONE_DRIP, CROP, readings, None, now, 330, CFG)
    assert rec["action"] == "OK"


def test_just_below_minimum_irrigates():
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 59.9, now)
    rec = decide(ZONE_DRIP, CROP, readings, None, now, 330, CFG)
    assert rec["action"] in ("IRRIGATE_NOW", "SKIP_RAIN", "WAIT_WIND", "IRRIGATE_LATER")
    assert rec["action"] != "OK"


def test_window_parsing():
    in_win, _ = _next_window(360, ["05:00-09:00", "17:00-20:00"])  # 360=6:00
    assert in_win
    in_win2, nxt = _next_window(700, ["05:00-09:00", "17:00-20:00"])  # 700=11:40
    assert not in_win2
    assert nxt == "17:00"


def test_no_weather_skips_rain_check():
    now = "2026-09-20T06:00:00Z"
    readings = make_readings(4, 58.0, now)
    rec = decide(ZONE_DRIP, CROP, readings, None, now, 330, CFG)
    assert rec["action"] == "IRRIGATE_NOW"
