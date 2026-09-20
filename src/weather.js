import { now, toIso, fromIso } from "./clock.js";

export function parseWeather(data, fetchedAt = null) {
  const h = data.hourly || {};
  const cur = data.current || {};
  const times = h.time || [];
  return {
    temperature_c: cur.temperature_2m ?? 0.0,
    wind_kmh: cur.wind_speed_10m ?? 0.0,
    current_precip_mm: cur.precipitation ?? 0.0,
    hourly_times: times,
    hourly_precip_mm: h.precipitation ?? new Array(times.length).fill(null),
    hourly_precip_prob: h.precipitation_probability ?? new Array(times.length).fill(0),
    hourly_evaporation_mm: h.et0_fao_evapotranspiration ?? new Array(times.length).fill(null),
    hourly_wind_kmh: h.wind_speed_10m ?? new Array(times.length).fill(null),
    hourly_temp_c: h.temperature_2m ?? new Array(times.length).fill(null),
    source: "open-meteo",
    fetched_at: fetchedAt || toIso(now())
  };
}

export async function fetchLiveWeather(cfg) {
  const loc = cfg.location;
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${loc.latitude}&longitude=${loc.longitude}&current=temperature_2m,wind_speed_10m,precipitation&hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m,et0_fao_evapotranspiration&forecast_days=2&timezone=auto`;
  const timeoutMs = (cfg.weather?.timeout_seconds || 10) * 1000;
  const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function getWeather(db, cfg) {
  const nowDt = now();
  const cached = db.prepare("SELECT * FROM weather_cache WHERE key = 'forecast'").get();
  if (cached) {
    const ageMin = (nowDt - fromIso(cached.fetched_at)) / 60000.0;
    if (ageMin < cfg.weather.refresh_minutes) {
      return parseWeather(JSON.parse(cached.payload), cached.fetched_at);
    }
  }
  try {
    const data = await fetchLiveWeather(cfg);
    const ts = toIso(nowDt);
    db.prepare(`INSERT INTO weather_cache (key, fetched_at, payload) VALUES ('forecast', ?, ?)
      ON CONFLICT(key) DO UPDATE SET fetched_at = excluded.fetched_at, payload = excluded.payload`).run(ts, JSON.stringify(data));
    return parseWeather(data, ts);
  } catch {
    if (cached) {
      const ageHours = (nowDt - fromIso(cached.fetched_at)) / 3600000.0;
      if (ageHours <= cfg.engine.weather_max_age_hours) {
        return parseWeather(JSON.parse(cached.payload), cached.fetched_at);
      }
    }
    return null;
  }
}
