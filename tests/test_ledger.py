import pytest
from sinchai import db, clock, ledger


def test_ledger_hit(tmp_path):
    import tomllib, importlib.resources
    cfg = tomllib.loads(importlib.resources.files("sinchai").joinpath("defaults.toml").read_bytes().decode())
    con = db.open_db(str(tmp_path / "test.db"))
    from sinchai.farm import _seed_data
    _seed_data(con, cfg)
    ts = clock.to_iso(clock.now())
    import datetime
    past = clock.to_iso(clock.from_iso(ts) - datetime.timedelta(hours=13))
    deadline = clock.to_iso(clock.from_iso(past) + datetime.timedelta(hours=12))
    con.execute("INSERT INTO skips (zone_id,decided_at,forecast_mm,forecast_prob,deadline_at,litres_withheld) VALUES (?,?,?,?,?,?)",
                (1, past, 8.0, 80.0, deadline, 1000.0))
    con.commit()
    db.upsert_rain_obs(con, past, 5.0)
    ledger.resolve_due_skips(con, db.get_zones(con), cfg)
    row = con.execute("SELECT verdict FROM skips WHERE zone_id=1").fetchone()
    assert row["verdict"] == "HIT"


def test_ledger_miss(tmp_path):
    import tomllib, importlib.resources, datetime
    cfg = tomllib.loads(importlib.resources.files("sinchai").joinpath("defaults.toml").read_bytes().decode())
    con = db.open_db(str(tmp_path / "test.db"))
    from sinchai.farm import _seed_data
    _seed_data(con, cfg)
    ts = clock.to_iso(clock.now())
    past = clock.to_iso(clock.from_iso(ts) - datetime.timedelta(hours=13))
    deadline = clock.to_iso(clock.from_iso(past) + datetime.timedelta(hours=12))
    con.execute("INSERT INTO skips (zone_id,decided_at,forecast_mm,forecast_prob,deadline_at,litres_withheld) VALUES (?,?,?,?,?,?)",
                (1, past, 8.0, 80.0, deadline, 1000.0))
    con.commit()
    db.upsert_rain_obs(con, past, 0.5)
    ledger.resolve_due_skips(con, db.get_zones(con), cfg)
    row = con.execute("SELECT verdict FROM skips WHERE zone_id=1").fetchone()
    assert row["verdict"] == "MISS"
