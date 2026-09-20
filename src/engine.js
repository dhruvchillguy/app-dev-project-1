import { fromIso } from "./clock.js";

function getThresholds(zone, crop) {
  const mn = zone.min_pct !== null && zone.min_pct !== undefined ? zone.min_pct : crop.min_pct;
  const tg = zone.target_pct !== null && zone.target_pct !== undefined ? zone.target_pct : crop.target_pct;
  return [mn, tg];
}

function rainExpected(weather, nowIso, cfg) {
  if (!weather || !weather.hourly_times) return [false, 0.0, 0.0];
  let total = 0.0, maxProb = 0.0, count = 0;
  for (let i = 0; i < weather.hourly_times.length; i++) {
    if (weather.hourly_times[i] < nowIso) continue;
    if (count >= cfg.engine.rain_lookahead_hours) break;
    total += weather.hourly_precip_mm[i] || 0.0;
    maxProb = Math.max(maxProb, weather.hourly_precip_prob[i] || 0.0);
    count++;
  }
  const byVol = total >= cfg.engine.rain_skip_mm;
  const byProb = maxProb >= cfg.engine.rain_skip_prob && total >= cfg.engine.rain_skip_prob_min_mm;
  return [byVol || byProb, total, maxProb];
}

function slopeHours(readings, mn, moisture) {
  if (readings.length < 4) return null;
  const pts = readings.slice(0, 12).map(r => r.moisture_pct).reverse();
  const n = pts.length;
  let sx = 0, sy = 0, sxy = 0, sxx = 0;
  for (let i = 0; i < n; i++) {
    sx += i; sy += pts[i]; sxy += i * pts[i]; sxx += i * i;
  }
  const denom = n * sxx - sx * sx;
  if (denom === 0) return null;
  const slope = (n * sxy - sx * sy) / denom;
  if (slope >= 0) return null;
  return (moisture - mn) / Math.abs(slope) * (5.0 / 60.0);
}

function et0Hours(weather, crop, moisture, mn) {
  if (!weather || !weather.hourly_evaporation_mm) return null;
  const vals = weather.hourly_evaporation_mm.filter(v => v !== null && v !== undefined);
  if (vals.length === 0) return null;
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  const rate = mean * crop.crop_factor / crop.water_holding_mm * 100.0;
  return rate > 0 ? (moisture - mn) / rate : null;
}

export function duration(moisture, tg, whMm, flow, eff, maxMin) {
  const mins = (tg - moisture) / 100.0 * whMm / (flow * eff) * 60.0;
  if (mins <= 0) return [0.0, false];
  return mins > maxMin ? [maxMin, true] : [mins, false];
}

function nextWindow(localMin, windows) {
  const parsed = windows.map(w => {
    const s = parseInt(w.slice(0, 2), 10) * 60 + parseInt(w.slice(3, 5), 10);
    const e = parseInt(w.slice(6, 8), 10) * 60 + parseInt(w.slice(9, 11), 10);
    return [s, e];
  });
  for (const [s, e] of parsed) {
    if (s <= localMin && localMin <= e) return [true, null];
  }
  const starts = parsed.map(p => p[0]).sort((a, b) => a - b);
  const nxt = starts.find(s => s > localMin) ?? starts[0];
  const hh = String(Math.floor(nxt / 60)).padStart(2, "0");
  const mm = String(nxt % 60).padStart(2, "0");
  return [false, `${hh}:${mm}`];
}

export function decide(zone, crop, readings, weather, nowIso, localMin, cfg) {
  if (!crop) throw new Error(`Zone ${zone.id}: unknown crop`);
  const [mn, tg] = getThresholds(zone, crop);
  if (mn >= tg) throw new Error(`Zone ${zone.id}: min_pct must be less than target_pct`);
  const crit = mn - cfg.engine.critical_margin_pts;
  const trace = [`min=${mn}% target=${tg}% critical=${crit.toFixed(1)}%`];
  const eff = cfg.efficiency[zone.irrigation];
  if (!readings || readings.length === 0) {
    return { action: "NO_DATA", minutes: null, reason: "no sensor data", hours_until: null, trace };
  }
  const age = (fromIso(nowIso) - fromIso(readings[0].ts)) / 60000.0;
  if (age > cfg.engine.sensor_offline_minutes) {
    return { action: "NO_DATA", minutes: null, reason: `sensor offline (${age.toFixed(0)} min since last reading)`, hours_until: null, trace };
  }
  const moisture = readings[0].moisture_pct;
  trace.push(`moisture=${moisture.toFixed(1)}%`);
  const wlogN = cfg.engine.waterlog_hours * 60 / 5;
  const wlogCount = readings.filter(r => r.moisture_pct >= cfg.engine.waterlog_pct).length;
  if (wlogCount >= wlogN) {
    return { action: "STOP", minutes: null, reason: "waterlogged, check drainage", hours_until: null, trace };
  }
  if (moisture >= mn) {
    const hrs = slopeHours(readings, mn, moisture) ?? et0Hours(weather, crop, moisture, mn);
    return { action: "OK", minutes: null, reason: `moisture ${Math.round(moisture)}% at or above minimum ${Math.round(mn)}%`, hours_until: hrs, trace };
  }
  const [mins, capped] = duration(moisture, tg, crop.water_holding_mm, zone.flow_mm_hr, eff, cfg.engine.max_run_minutes);
  const cap = capped ? " (split into cycles)" : "";
  const [rainEx, rainMm, rainProb] = rainExpected(weather, nowIso, cfg);
  const isCrit = moisture < crit;
  let override = "";
  if (rainEx && !isCrit) {
    return { action: "SKIP_RAIN", minutes: mins, reason: `rain forecast ${rainMm.toFixed(1)}mm ${Math.round(rainProb)}%${cap}`, hours_until: 0.0, trace, forecast_mm: rainMm, forecast_prob: rainProb };
  }
  if (rainEx && isCrit) override = " (critical, irrigating despite rain forecast)";
  if (zone.irrigation === "sprinkler" && weather && weather.wind_kmh > cfg.engine.wind_limit_kmh) {
    if (!isCrit) return { action: "WAIT_WIND", minutes: mins, reason: `wind ${weather.wind_kmh.toFixed(1)} km/h too high for sprinkler${cap}`, hours_until: null, trace };
    override = override || " (critical, irrigating despite wind)";
  }
  const [inWin, nextWin] = nextWindow(localMin, cfg.engine.windows);
  if (!inWin && !isCrit) {
    return { action: "IRRIGATE_LATER", minutes: mins, reason: `outside window, next at ${nextWin}${cap}`, hours_until: null, trace };
  }
  if (!inWin && isCrit) override = override || " (critical, irrigating outside window)";
  const reason = `moisture ${Math.round(moisture)}% is ${(mn - moisture).toFixed(1)} points below minimum ${Math.round(mn)}%${override}${cap}`;
  return { action: "IRRIGATE_NOW", minutes: mins, reason, hours_until: 0.0, trace };
}
