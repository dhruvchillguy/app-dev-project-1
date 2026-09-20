import json
import logging
import time

import httpx

from sinchai import clock, db

log = logging.getLogger(__name__)
_next_fetch = 0.0


def _cache_key(cfg):
    lat = round(cfg["location"]["latitude"], 2)
    lon = round(cfg["location"]["longitude"], 2)
    return f"{lat},{lon}"


def _parse(payload_str):
    data = json.loads(payload_str)
    h = data.get("hourly", {})
    cur = data.get("current", {})
    times = h.get("time", [])
    return {
        "fetched_at": clock.to_iso(clock.now()),
        "temperature_c": cur.get("temperature_2m", 0.0),
        "wind_kmh": cur.get("wind_speed_10m", 0.0),
        "current_precip_mm": cur.get("precipitation", 0.0),
        "hourly_times": times,
        "hourly_precip_mm": h.get("precipitation", [None] * len(times)),
        "hourly_precip_prob": h.get("precipitation_probability", [0] * len(times)),
        "hourly_evaporation_mm": h.get("et0_fao_evapotranspiration", [None] * len(times)),
        "hourly_wind_kmh": h.get("wind_speed_10m", [None] * len(times)),
        "hourly_temp_c": h.get("temperature_2m", [None] * len(times)),
        "source": "live",
    }


def _fetch_live(cfg):
    lat = cfg["location"]["latitude"]
    lon = cfg["location"]["longitude"]
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
        "hourly": "precipitation_probability,precipitation,et0_fao_evapotranspiration,wind_speed_10m,temperature_2m",
        "forecast_days": 2, "past_days": 1, "timezone": "auto",
    }
    resp = httpx.get(url, params=params, timeout=cfg["weather"]["timeout_seconds"])
    resp.raise_for_status()
    return resp.text


def store_rain_obs(con, weather):
    for i, ts in enumerate(weather["hourly_times"]):
        mm = weather["hourly_precip_mm"][i]
        if mm is not None:
            db.upsert_rain_obs(con, ts, mm)


def get_weather(con, cfg, force=False):
    global _next_fetch
    key = _cache_key(cfg)
    cached = db.get_weather_cache(con, key)
    max_age_h = cfg["engine"]["weather_max_age_hours"]
    now_iso = clock.to_iso(clock.now())

    if cached and not force:
        age_h = (clock.from_iso(now_iso) - clock.from_iso(cached["fetched_at"])).total_seconds() / 3600.0
        if age_h < cfg["weather"]["refresh_minutes"] / 60.0:
            w = _parse(cached["payload"])
            w["source"] = "cached"
            return w
        if age_h < max_age_h:
            pass
        else:
            w = _parse(cached["payload"])
            w["source"] = "cached_stale"
            log.warning("weather cache older than %s h, using stale", max_age_h)

    real_now = time.time()
    if real_now < _next_fetch and not force:
        if cached:
            w = _parse(cached["payload"])
            w["source"] = "cached"
            return w
        return None

    try:
        payload = _fetch_live(cfg)
        db.upsert_weather_cache(con, key, now_iso, payload)
        w = _parse(payload)
        store_rain_obs(con, w)
        _next_fetch = real_now + cfg["weather"]["refresh_minutes"] * 60
        log.info("weather fetched ok")
        return w
    except Exception as e:
        log.warning("weather fetch failed: %s", e)
        backoff = min(cfg["weather"]["backoff_max_minutes"] * 60, (_next_fetch - real_now) * 2 + 60)
        _next_fetch = real_now + backoff
        if cached:
            w = _parse(cached["payload"])
            w["source"] = "cached"
            return w
        return None


def scripted_weather(scenario):
    h = scenario.get("weather_hourly", {})
    times = h.get("times", [])
    return {
        "fetched_at": clock.to_iso(clock.now()),
        "temperature_c": scenario.get("temperature_c", 30.0),
        "wind_kmh": scenario.get("wind_kmh", 10.0),
        "current_precip_mm": 0.0,
        "hourly_times": times,
        "hourly_precip_mm": h.get("precip_mm", [0.0] * len(times)),
        "hourly_precip_prob": h.get("precip_prob", [0] * len(times)),
        "hourly_evaporation_mm": h.get("evaporation_mm", [0.3] * len(times)),
        "hourly_wind_kmh": h.get("wind_kmh", [10.0] * len(times)),
        "hourly_temp_c": h.get("temp_c", [30.0] * len(times)),
        "source": "scripted",
    }
