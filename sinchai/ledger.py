import datetime
import logging
from sinchai import clock, db

log = logging.getLogger(__name__)


def maybe_open_skip(con, zone, rec, cfg):
    if rec["action"] != "SKIP_RAIN":
        return
    existing = con.execute(
        "SELECT id FROM skips WHERE zone_id=? AND resolved_at IS NULL", (zone["id"],)
    ).fetchone()
    if existing:
        return
    ts = clock.to_iso(clock.now())
    lookahead = cfg["engine"]["rain_lookahead_hours"]
    deadline = clock.to_iso(clock.from_iso(ts) + datetime.timedelta(hours=lookahead))
    hours = (rec["minutes"] or 0) / 60.0
    litres = hours * zone["flow_mm_hr"] * zone["area_m2"]
    con.execute(
        "INSERT INTO skips (zone_id,decided_at,forecast_mm,forecast_prob,deadline_at,litres_withheld) VALUES (?,?,?,?,?,?)",
        (zone["id"], ts, 0.0, 0.0, deadline, litres),
    )
    con.commit()
    log.info("skip opened zone=%d deadline=%s", zone["id"], deadline)


def resolve_due_skips(con, zones, cfg):
    now_iso = clock.to_iso(clock.now())
    due = con.execute(
        "SELECT * FROM skips WHERE resolved_at IS NULL AND deadline_at <= ?", (now_iso,)
    ).fetchall()
    for skip in due:
        actual_mm = con.execute(
            "SELECT SUM(mm) FROM rain_obs WHERE hour_ts >= ? AND hour_ts <= ?",
            (skip["decided_at"], skip["deadline_at"])
        ).fetchone()[0] or 0.0
        threshold = max(cfg["ledger"]["hit_min_mm"], cfg["ledger"]["hit_fraction"] * (skip["forecast_mm"] or 0))
        verdict = "HIT" if actual_mm >= threshold else "MISS"
        min_m = con.execute(
            "SELECT MIN(moisture_pct) FROM readings WHERE zone_id=? AND ts >= ? AND ts <= ?",
            (skip["zone_id"], skip["decided_at"], skip["deadline_at"])
        ).fetchone()[0]
        con.execute(
            "UPDATE skips SET resolved_at=?, actual_mm=?, verdict=?, min_moisture=? WHERE id=?",
            (now_iso, actual_mm, verdict, min_m, skip["id"])
        )
        con.commit()
        log.info("skip resolved zone=%d verdict=%s actual_mm=%.1f", skip["zone_id"], verdict, actual_mm)


def ledger_summary(con):
    rows = con.execute("SELECT verdict, litres_withheld, min_moisture FROM skips WHERE resolved_at IS NOT NULL").fetchall()
    if not rows:
        return "No rain skips recorded yet."
    hits = sum(1 for r in rows if r["verdict"] == "HIT")
    misses = sum(1 for r in rows if r["verdict"] == "MISS")
    total_l = sum(r["litres_withheld"] or 0 for r in rows)
    miss_rows = [r for r in rows if r["verdict"] == "MISS"]
    parts = [f"{len(rows)} skips: {hits} hits, {misses} misses. {total_l:,.0f} L not applied."]
    if miss_rows:
        low = min(r["min_moisture"] or 999 for r in miss_rows)
        parts.append(f"In misses, moisture dropped as low as {low:.0f}%.")
    return " ".join(parts)
