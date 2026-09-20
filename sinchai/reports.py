from sinchai import clock


def water_used(con, zone_id, days=7):
    rows = con.execute(
        """SELECT substr(ts,1,10) as day, SUM(litres) as litres
           FROM valve_events WHERE zone_id=? AND action='close' AND litres IS NOT NULL
           AND ts >= datetime('now', ?)
           GROUP BY day ORDER BY day""",
        (zone_id, f"-{days} days")
    ).fetchall()
    return [{"day": r["day"], "litres": r["litres"] or 0.0} for r in rows]


def baseline_litres(zone, cfg, days=7):
    base_min = cfg["reports"]["baseline_minutes_per_day"]
    litres_per_day = zone["flow_mm_hr"] * (base_min / 60.0) * zone["area_m2"]
    return litres_per_day * days


def stress_hours(con, zone_id, min_pct, days=7):
    row = con.execute(
        """SELECT COUNT(*) FROM readings WHERE zone_id=? AND moisture_pct < ?
           AND ts >= datetime('now', ?)""",
        (zone_id, min_pct, f"-{days} days")
    ).fetchone()
    return (row[0] or 0) * (5.0 / 60.0)


def zone_report(con, zones, cfg, days=7):
    rows = []
    for zone in zones:
        crop = con.execute("SELECT * FROM crops WHERE name=?", (zone["crop"],)).fetchone()
        mn = zone["min_pct"] if zone["min_pct"] is not None else (crop["min_pct"] if crop else 45)
        used = sum(r["litres"] for r in water_used(con, zone["id"], days))
        base = baseline_litres(zone, cfg, days)
        sh = stress_hours(con, zone["id"], mn, days)
        rows.append({
            "zone_id": zone["id"],
            "name": zone["name"],
            "crop": zone["crop"],
            "litres_used": used,
            "baseline_litres": base,
            "stress_hours": sh,
            "days": days,
        })
    return rows
