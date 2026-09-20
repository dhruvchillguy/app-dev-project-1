import pytest
import sqlite3
from sinchai import db, clock


def test_foreign_keys_enforced(tmp_path):
    con = db.open_db(str(tmp_path / "test.db"))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO readings (zone_id,ts,moisture_pct,source) VALUES (999,'2026-01-01T00:00:00Z',50,'sim')")
        con.commit()


def test_wal_mode(tmp_path):
    con = db.open_db(str(tmp_path / "test.db"))
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_query_only_rejects_insert(tmp_path):
    p = str(tmp_path / "test.db")
    db.open_db(p)
    qcon = db.open_db(p, query_only=True)
    with pytest.raises(Exception):
        qcon.execute("INSERT INTO settings (key,value) VALUES ('x','y')")
        qcon.commit()


def test_insert_and_retrieve_reading(tmp_path):
    con = db.open_db(str(tmp_path / "test.db"))
    import tomllib, importlib.resources
    cfg = tomllib.loads(importlib.resources.files("sinchai").joinpath("defaults.toml").read_bytes().decode())
    from sinchai.farm import _seed_data
    _seed_data(con, cfg)
    ts = clock.to_iso(clock.now())
    db.insert_reading(con, 1, ts, 72.5, None, "sim")
    rows = db.get_recent_readings(con, 1, 5)
    assert len(rows) == 1
    assert abs(rows[0]["moisture_pct"] - 72.5) < 0.01
