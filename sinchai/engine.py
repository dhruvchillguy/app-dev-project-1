from sinchai import clock


def _thresholds(zone, crop):
    mn = zone["min_pct"] if zone["min_pct"] is not None else crop["min_pct"]
    tg = zone["target_pct"] if zone["target_pct"] is not None else crop["target_pct"]
    return mn, tg


def _rain_expected(weather, now_iso, cfg):
    if weather is None:
        return False, 0.0, 0.0
    total, max_prob, count = 0.0, 0.0, 0
    for i, t in enumerate(weather["hourly_times"]):
        if t < now_iso:
            continue
        if count >= cfg["engine"]["rain_lookahead_hours"]:
            break
        total += weather["hourly_precip_mm"][i] or 0.0
        max_prob = max(max_prob, weather["hourly_precip_prob"][i] or 0.0)
        count += 1
    by_vol = total >= cfg["engine"]["rain_skip_mm"]
    by_prob = max_prob >= cfg["engine"]["rain_skip_prob"] and total >= cfg["engine"]["rain_skip_prob_min_mm"]
    return (by_vol or by_prob), total, max_prob


def _slope_hours(readings, mn, moisture):
    if len(readings) < 4:
        return None
    pts = [r["moisture_pct"] for r in reversed(readings[-12:])]
    n = len(pts)
    sx, sy = sum(range(n)), sum(pts)
    sxy = sum(i * pts[i] for i in range(n))
    sxx = sum(i * i for i in range(n))
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    if slope >= 0:
        return None
    return (moisture - mn) / abs(slope) * 5.0 / 60.0


def _et0_hours(weather, crop, moisture, mn):
    if weather is None:
        return None
    vals = [v for v in weather["hourly_evaporation_mm"] if v is not None]
    if not vals:
        return None
    rate = sum(vals) / len(vals) * crop["crop_factor"] / crop["water_holding_mm"] * 100.0
    return (moisture - mn) / rate if rate > 0 else None


def _duration(moisture, tg, wh_mm, flow, eff, max_min):
    mins = (tg - moisture) / 100.0 * wh_mm / (flow * eff) * 60.0
    if mins <= 0:
        return 0.0, False
    return (max_min, True) if mins > max_min else (mins, False)


def _next_window(local_min, windows):
    parsed = [(int(w[:2]) * 60 + int(w[3:5]), int(w[6:8]) * 60 + int(w[9:11])) for w in windows]
    for s, e in parsed:
        if s <= local_min <= e:
            return True, None
    nxt = next((s for s, e in sorted(parsed) if s > local_min), min(p[0] for p in parsed))
    return False, f"{nxt // 60:02d}:{nxt % 60:02d}"


def decide(zone, crop, readings, weather, now_iso, local_min, cfg):
    if crop is None:
        raise ValueError(f"Zone {zone['id']}: unknown crop")
    mn, tg = _thresholds(zone, crop)
    if mn >= tg:
        raise ValueError(f"Zone {zone['id']}: min_pct must be less than target_pct")
    crit = mn - cfg["engine"]["critical_margin_pts"]
    trace = [f"min={mn}% target={tg}% critical={crit:.1f}%"]
    eff = cfg["efficiency"][zone["irrigation"]]

    if not readings:
        return {"action": "NO_DATA", "minutes": None, "reason": "no sensor data", "hours_until": None, "trace": trace}
    age = (clock.from_iso(now_iso) - clock.from_iso(readings[0]["ts"])).total_seconds() / 60.0
    if age > cfg["engine"]["sensor_offline_minutes"]:
        return {"action": "NO_DATA", "minutes": None, "reason": f"sensor offline ({age:.0f} min since last reading)", "hours_until": None, "trace": trace}

    moisture = readings[0]["moisture_pct"]
    trace.append(f"moisture={moisture:.1f}%")
    wlog_n = cfg["engine"]["waterlog_hours"] * 60 / 5
    if sum(1 for r in readings if r["moisture_pct"] >= cfg["engine"]["waterlog_pct"]) >= wlog_n:
        return {"action": "STOP", "minutes": None, "reason": "waterlogged, check drainage", "hours_until": None, "trace": trace}

    if moisture >= mn:
        hrs = _slope_hours(readings, mn, moisture) or _et0_hours(weather, crop, moisture, mn)
        return {"action": "OK", "minutes": None, "reason": f"moisture {moisture:.0f}% at or above minimum {mn:.0f}%", "hours_until": hrs, "trace": trace}

    mins, capped = _duration(moisture, tg, crop["water_holding_mm"], zone["flow_mm_hr"], eff, cfg["engine"]["max_run_minutes"])
    cap = " (split into cycles)" if capped else ""
    rain_ex, rain_mm, rain_prob = _rain_expected(weather, now_iso, cfg)
    is_crit = moisture < crit
    override = ""

    if rain_ex and not is_crit:
        return {"action": "SKIP_RAIN", "minutes": mins, "reason": f"rain forecast {rain_mm:.1f}mm {rain_prob:.0f}%{cap}", "hours_until": 0.0, "trace": trace}
    if rain_ex and is_crit:
        override = " (critical, irrigating despite rain forecast)"

    if zone["irrigation"] == "sprinkler" and weather is not None and weather["wind_kmh"] > cfg["engine"]["wind_limit_kmh"]:
        if not is_crit:
            return {"action": "WAIT_WIND", "minutes": mins, "reason": f"wind {weather['wind_kmh']:.1f} km/h too high for sprinkler{cap}", "hours_until": None, "trace": trace}
        override = override or " (critical, irrigating despite wind)"

    in_win, next_win = _next_window(local_min, cfg["engine"]["windows"])
    if not in_win and not is_crit:
        return {"action": "IRRIGATE_LATER", "minutes": mins, "reason": f"outside window, next at {next_win}{cap}", "hours_until": None, "trace": trace}
    if not in_win and is_crit:
        override = override or " (critical, irrigating outside window)"

    reason = f"moisture {moisture:.0f}% is {mn - moisture:.1f} points below minimum {mn:.0f}%{override}{cap}"
    return {"action": "IRRIGATE_NOW", "minutes": mins, "reason": reason, "hours_until": 0.0, "trace": trace}
