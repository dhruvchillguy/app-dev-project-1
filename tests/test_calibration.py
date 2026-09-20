import pytest
from sinchai.sensors import SimulatedSensor, SerialSensor


def make_reader(dry=3000, wet=1300):
    cfg = {"sensor": {"dry_raw": dry, "wet_raw": wet, "raw_fault_low": 50, "raw_fault_high": 4045},
           "efficiency": {"drip": 0.9, "sprinkler": 0.75, "flood": 0.6},
           "crops": {}, "zones": []}
    class R(SerialSensor):
        def __init__(self):
            self.cfg = cfg
            self._latest = {}
            self._rejects = 0
    return R()


def test_midpoint():
    r = make_reader(3000, 1300)
    pct = r._convert(2150)
    assert abs(pct - 50.0) < 0.01


def test_dry_end():
    r = make_reader(3000, 1300)
    assert abs(r._convert(3000) - 0.0) < 0.01


def test_wet_end():
    r = make_reader(3000, 1300)
    assert abs(r._convert(1300) - 100.0) < 0.01


def test_beyond_wet_clamped():
    r = make_reader(3000, 1300)
    pct = r._convert(1200)
    assert pct > 100.0 and pct <= 110.0


def test_fault_low():
    r = make_reader(3000, 1300)
    with pytest.raises(ValueError, match="fault range"):
        r._convert(50)


def test_fault_high():
    r = make_reader(3000, 1300)
    with pytest.raises(ValueError, match="fault range"):
        r._convert(4045)


def test_bad_calibration():
    r = make_reader(3000, 3000)
    with pytest.raises(ValueError, match="calibration invalid"):
        r._convert(2000)
