import { now, toIso, fromIso, localMinutes } from "./clock.js";
import { openDb, getZones, getCrop, insertReading, getRecentReadings, upsertController, getControllerRow, clearController, closeAllValves, upsertRainObs } from "./db.js";
import { decide } from "./engine.js";
import { checkAlerts } from "./alerts.js";
import { maybeOpenSkip, resolveDueSkips } from "./ledger.js";
import { checkMaxRuntime, handleAuto, openValve, closeValve } from "./valves.js";
import { setupDemo, getDemoWeatherAt, getDemoWeatherObject, getDropoutZones } from "./demo.js";
import { SimulatedSensor } from "./sensors.js";
import { getWeather } from "./weather.js";

const autoCooldowns = new Set();

export function seedData(db, cfg) {
  for (const [name, crop] of Object.entries(cfg.crops || {})) {
    db.prepare(`INSERT OR IGNORE INTO crops (name, crop_factor, water_holding_mm, min_pct, target_pct, note)
      VALUES (?, ?, ?, ?, ?, ?)`).run(name, crop.crop_factor, crop.water_holding_mm, crop.min_pct, crop.target_pct, crop.note || "approx");
  }
  for (const z of (cfg.zones || [])) {
    db.prepare(`INSERT OR IGNORE INTO zones (id, name, crop, area_m2, irrigation, flow_mm_hr)
      VALUES (?, ?, ?, ?, ?, ?)`).run(z.id, z.name, z.crop, z.area_m2, z.irrigation, z.flow_mm_hr);
  }
}

export function checkSecondController(db) {
  const row = getControllerRow(db);
  if (row && (now() - fromIso(row.heartbeat_at)) / 1000.0 < 10) {
    throw new Error("Another controller is already running");
  }
}

export function recoverValves(db) {
  if (getControllerRow(db)) {
    closeAllValves(db, toIso(now()), "failsafe");
  }
}

export function tick(db, zones, sensor, w, mode, demo, scenario, cfg) {
  const nowDt = now();
  const nowIso = toIso(nowDt);
  const localMin = localMinutes(nowDt, cfg.location.utc_offset_minutes);
  const dropouts = demo && scenario ? getDropoutZones(scenario, nowDt) : new Set();

  for (let z of zones) {
    const zid = z.id;
    const crop = getCrop(db, z.crop);
    if (!dropouts.has(zid)) {
      const valveOpen = z.valve_open === 1;
      const rainMm = demo && scenario ? getDemoWeatherAt(scenario, nowDt)[1] : 0.0;
      const m = sensor.tick(z, crop, 5.0 / 60.0, valveOpen, rainMm, w);
      insertReading(db, zid, nowIso, m, null, "sim");
    }
    const readings = getRecentReadings(db, zid, 48);
    z = getZones(db).find(item => item.id === zid) || z;
    const rec = decide(z, crop, readings, w, nowIso, localMin, cfg);
    checkAlerts(db, z, readings, w, rec, cfg);
    maybeOpenSkip(db, z, rec, cfg);
    if (mode === "auto") {
      checkMaxRuntime(db, [z], cfg);
      handleAuto(db, z, rec, autoCooldowns, cfg);
    }
  }
  resolveDueSkips(db, zones, cfg);
  return nowIso;
}

export async function runHeadless(dbPath, cfg, mode, demo, speed, seed, source, ticksLimit) {
  const db = openDb(dbPath, "src/schema.sql");
  seedData(db, cfg);
  checkSecondController(db);
  recoverValves(db);
  const scenario = demo ? setupDemo(speed) : null;
  const zones = getZones(db);
  const sensor = new SimulatedSensor(zones, cfg, seed);
  if (scenario && scenario.zone_initial_moisture) {
    for (const [zid, m] of Object.entries(scenario.zone_initial_moisture)) {
      sensor.moisture[Number(zid)] = Number(m);
    }
  }
  const startedAt = toIso(now());
  let tickCount = 0;
  let w = null;
  try {
    while (ticksLimit === null || tickCount < ticksLimit) {
      const hb = toIso(now());
      upsertController(db, process.pid, startedAt, hb, hb, mode, source, demo, speed);
      const currentZones = getZones(db);
      if (!demo) {
        w = await getWeather(db, cfg);
      } else if (scenario) {
        w = getDemoWeatherObject(scenario, now());
        if (w.current_precip_mm > 0) upsertRainObs(db, hb.slice(0, 13) + ":00:00Z", w.current_precip_mm);
      }
      tick(db, currentZones, sensor, w, mode, demo, scenario, cfg);
      tickCount++;
      await new Promise(r => setTimeout(r, demo ? 50 : cfg.sensor.poll_seconds * 1000));
    }
  } finally {
    closeAllValves(db, toIso(now()), "failsafe");
    clearController(db);
  }
  return tickCount;
}
