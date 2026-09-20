from sinchai import db, clock


def farm_brief(con, zones, cfg):
    lines = []
    for zone in zones:
        readings = db.get_recent_readings(con, zone["id"], 1)
        m = readings[0]["moisture_pct"] if readings else None
        crop = con.execute("SELECT * FROM crops WHERE name=?", (zone["crop"],)).fetchone()
        mn = zone["min_pct"] if zone["min_pct"] is not None else (crop["min_pct"] if crop else 45)
        if m is None:
            lines.append(f"{zone['name']}: no reading.")
        elif m < mn:
            lines.append(f"{zone['name']} ({zone['crop']}): moisture {m:.0f}%, needs water.")
        else:
            lines.append(f"{zone['name']} ({zone['crop']}): moisture {m:.0f}%, ok.")
    text = " | ".join(lines)
    if len(text) > 320:
        text = text[:317] + "..."
    return text
