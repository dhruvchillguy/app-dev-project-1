import pytest
from sinchai.sensors import SimulatedSensor


def make_zones():
    return [
        {"id": 1, "name": "Z1", "crop": "tomato", "area_m2": 400, "irrigation": "drip", "flow_mm_hr": 8, "min_pct": None, "target_pct": None, "valve_open": 0, "valve_opened_at": None, "last_closed_at": None},
        {"id": 2, "name": "Z2", "crop": "maize", "area_m2": 1200, "irrigation": "sprinkler", "flow_mm_hr": 10, "min_pct": None, "target_pct": None, "valve_open": 0, "valve_opened_at": None, "last_closed_at": None},
    ]


def make_cfg():
    import tomllib, importlib.resources
    return tomllib.loads(importlib.resources.files("sinchai").joinpath("defaults.toml").read_bytes().decode())


def test_deterministic_seed():
    cfg = make_cfg()
    zones = make_zones()
    crop = {"crop_factor": 1.15, "water_holding_mm": 75}
    s1 = SimulatedSensor(zones, cfg, seed=42)
    s2 = SimulatedSensor(zones, cfg, seed=42)
    m1 = s1.tick(zones[0], crop, 1/12, False)
    m2 = s2.tick(zones[0], crop, 1/12, False)
    assert m1 == m2


def test_moisture_stays_in_range():
    cfg = make_cfg()
    zones = make_zones()
    crop = {"crop_factor": 1.15, "water_holding_mm": 75}
    s = SimulatedSensor(zones, cfg, seed=1)
    for _ in range(100):
        m = s.tick(zones[0], crop, 1/12, False)
        assert 0 <= m <= 110


def test_valve_raises_moisture():
    cfg = make_cfg()
    zones = make_zones()
    crop = {"crop_factor": 1.15, "water_holding_mm": 75}
    s = SimulatedSensor(zones, cfg, seed=7)
    s.moisture[1] = 50.0
    m_before = s.moisture[1]
    s.tick(zones[0], crop, 1/6, True)
    assert s.moisture[1] > m_before


def test_serial_parse_valid():
    from sinchai.sensors import SerialSensor
    cfg = {"sensor": {"dry_raw": 3000, "wet_raw": 1300, "raw_fault_low": 50, "raw_fault_high": 4045},
           "efficiency": {}, "crops": {}, "zones": []}
    class R(SerialSensor):
        def __init__(self):
            self.cfg = cfg
            self._latest = {}
            self._rejects = 0
    r = R()
    zid, raw, pct = r._parse_line('{"zone":1,"raw":2150}')
    assert zid == 1 and raw == 2150 and abs(pct - 50.0) < 0.01


def test_serial_rejects_garbage():
    from sinchai.sensors import SerialSensor
    cfg = {"sensor": {"dry_raw": 3000, "wet_raw": 1300, "raw_fault_low": 50, "raw_fault_high": 4045},
           "efficiency": {}, "crops": {}, "zones": []}
    class R(SerialSensor):
        def __init__(self):
            self.cfg = cfg
            self._latest = {}
            self._rejects = 0
    r = R()
    result = r.read.__func__(r) if False else None
    with pytest.raises(Exception):
        r._parse_line("not json at all")
