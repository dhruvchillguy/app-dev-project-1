import { now, toIso, fromIso } from "./clock.js";
import { setValve } from "./db.js";

export function openValve(db, zone, source, minutes, cfg) {
  const ts = toIso(now());
  const litres = (minutes / 60.0) * zone.flow_mm_hr * zone.area_m2;
  setValve(db, zone.id, true, ts, source, minutes, litres);
}

export function closeValve(db, zone, source) {
  const ts = toIso(now());
  let minutes = null;
  let litres = null;
  if (zone.valve_opened_at) {
    const elapsedMin = (now() - fromIso(zone.valve_opened_at)) / 60000.0;
    minutes = elapsedMin;
    litres = (elapsedMin / 60.0) * zone.flow_mm_hr * zone.area_m2;
  }
  setValve(db, zone.id, false, ts, source, minutes, litres);
}

export function checkMaxRuntime(db, zones, cfg) {
  const nowDt = now();
  for (const z of zones) {
    if (z.valve_open && z.valve_opened_at) {
      const elapsedMin = (nowDt - fromIso(z.valve_opened_at)) / 60000.0;
      if (elapsedMin >= cfg.engine.max_run_minutes) {
        closeValve(db, z, "failsafe");
      }
    }
  }
}

export function handleAuto(db, zone, rec, cooldowns, cfg) {
  const action = rec.action;
  const zid = zone.id;
  const nowDt = now();
  if (zone.valve_open) {
    if (action !== "IRRIGATE_NOW") {
      closeValve(db, zone, "auto");
    }
    return;
  }
  if (action !== "IRRIGATE_NOW") return;
  if (zone.last_closed_at) {
    const elapsedMin = (nowDt - fromIso(zone.last_closed_at)) / 60000.0;
    if (elapsedMin < cfg.engine.cooldown_minutes) return;
  }
  if (cooldowns.has(zid)) return;
  openValve(db, zone, "auto", rec.minutes, cfg);
  cooldowns.add(zid);
}
