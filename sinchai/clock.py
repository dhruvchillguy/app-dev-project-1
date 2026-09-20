import datetime

_demo_start_real = None
_demo_start_sim = None
_speed = 1.0


def configure_demo(start_sim, speed):
    global _demo_start_real, _demo_start_sim, _speed
    _demo_start_real = _wall()
    _demo_start_sim = start_sim
    _speed = speed


def reset():
    global _demo_start_real, _demo_start_sim, _speed
    _demo_start_real = None
    _demo_start_sim = None
    _speed = 1.0


def _wall():
    return datetime.datetime.now(datetime.timezone.utc)


def now():
    if _demo_start_real is None:
        return _wall()
    elapsed = (_wall() - _demo_start_real).total_seconds() * _speed
    return _demo_start_sim + datetime.timedelta(seconds=elapsed)


def to_iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(s):
    s = s.rstrip("Z")
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def local_minutes(dt, utc_offset_minutes):
    local = dt + datetime.timedelta(minutes=utc_offset_minutes)
    return local.hour * 60 + local.minute
