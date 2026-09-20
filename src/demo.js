import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { configureDemo, fromIso, toIso } from "./clock.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export function loadScenario() {
  const p = path.join(__dirname, "demo-scenario.json");
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

export function setupDemo(speed) {
  const scenario = loadScenario();
  const startStr = scenario.start_time || "2026-09-20T00:00:00Z";
  const startDt = fromIso(startStr);
  configureDemo(startDt, speed);
  return scenario;
}

export function getDemoWeatherAt(scenario, nowDt) {
  const events = scenario.weather_events || [];
  let wind = scenario.base_wind_kmh || 10.0;
  let rainMm = 0.0;
  for (const ev of events) {
    const evDt = fromIso(ev.at);
    if (evDt <= nowDt) {
      if (ev.type === "wind") wind = ev.wind_kmh ?? wind;
      if (ev.type === "rain") {
        const diff = (nowDt - evDt) / 1000.0;
        if (0 <= diff && diff < 3600) rainMm = ev.mm ?? 0.0;
      }
    }
  }
  return [wind, rainMm];
}

export function getDemoForecastAt(scenario, nowDt) {
  const events = (scenario.forecast_events || []).slice().sort((a, b) => fromIso(b.at) - fromIso(a.at));
  for (const ev of events) {
    if (fromIso(ev.at) <= nowDt) {
      return [ev.precip_mm ?? 0.0, ev.precip_prob ?? 0];
    }
  }
  return [0.0, 0];
}

export function getDropoutZones(scenario, nowDt) {
  const dropouts = scenario.dropout_events || [];
  const active = new Set();
  for (const ev of dropouts) {
    const s = fromIso(ev.start);
    const e = fromIso(ev.end);
    if (s <= nowDt && nowDt <= e) active.add(ev.zone_id);
  }
  return active;
}

export function getDemoWeatherObject(scenario, nowDt) {
  const [wkm, rMm] = getDemoWeatherAt(scenario, nowDt);
  const [fMm, fProb] = getDemoForecastAt(scenario, nowDt);
  const times = Array.from({ length: 12 }, (_, i) => toIso(new Date(nowDt.getTime() + (i + 1) * 3600000)));
  return {
    wind_kmh: wkm, temperature_c: 30.0, current_precip_mm: rMm,
    hourly_times: times, hourly_precip_mm: new Array(12).fill(fMm / 12.0),
    hourly_precip_prob: new Array(12).fill(fProb), hourly_evaporation_mm: new Array(12).fill(0.3),
    hourly_wind_kmh: new Array(12).fill(wkm), hourly_temp_c: new Array(12).fill(30.0),
    source: "scripted", fetched_at: toIso(nowDt)
  };
}
