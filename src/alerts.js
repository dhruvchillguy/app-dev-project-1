import { now, toIso } from "./clock.js";
import { insertAlert } from "./db.js";

const SEVERITY = {
  LOW_MOISTURE: "warning",
  WATERLOGGING: "critical",
  SENSOR_OFFLINE: "critical",
  SENSOR_FAULT: "warning",
  RAIN_INCOMING: "info",
  HEAT: "warning",
  WEATHER_OFFLINE: "info"
};

const lastRaised = new Map();
const COOLDOWN_MS = 300000;

export function raiseAlert(db, kind, message, zoneId = null) {
  const key = `${zoneId}:${kind}`;
  const nowDt = now();
  const last = lastRaised.get(key);
  if (last && (nowDt - last) < COOLDOWN_MS) return;
  lastRaised.set(key, nowDt);
  const ts = toIso(nowDt);
  const severity = SEVERITY[kind] || "info";
  insertAlert(db, ts, zoneId, kind, severity, message);
}

export function clearKind(db, kind, zoneId = null) {
  const ts = toIso(now());
  if (zoneId !== null && zoneId !== undefined) {
    db.prepare("UPDATE alerts SET cleared_ts = ? WHERE kind = ? AND zone_id = ? AND cleared_ts IS NULL").run(ts, kind, zoneId);
    lastRaised.delete(`${zoneId}:${kind}`);
  } else {
    db.prepare("UPDATE alerts SET cleared_ts = ? WHERE kind = ? AND cleared_ts IS NULL").run(ts, kind);
    for (const key of lastRaised.keys()) {
      if (key.endsWith(`:${kind}`)) lastRaised.delete(key);
    }
  }
}

export function checkAlerts(db, zone, readings, weather, rec, cfg) {
  const zid = zone.id;
  if (!readings || readings.length === 0) {
    raiseAlert(db, "SENSOR_OFFLINE", `${zone.name}: no sensor data`, zid);
    return;
  }
  const ageMin = (now() - new Date(readings[0].ts)) / 60000.0;
  if (ageMin > cfg.engine.sensor_offline_minutes) {
    raiseAlert(db, "SENSOR_OFFLINE", `${zone.name}: sensor offline (${Math.round(ageMin)} min since last reading)`, zid);
    return;
  }
  clearKind(db, "SENSOR_OFFLINE", zid);
  const m = readings[0].moisture_pct;
  const mn = zone.min_pct ?? cfg.crops[zone.crop]?.min_pct ?? 45;
  if (m < mn) {
    raiseAlert(db, "LOW_MOISTURE", `${zone.name}: moisture ${Math.round(m)}% below minimum ${Math.round(mn)}%`, zid);
  } else {
    clearKind(db, "LOW_MOISTURE", zid);
  }
  if (rec.action === "STOP") {
    raiseAlert(db, "WATERLOGGING", `${zone.name}: waterlogged`, zid);
  } else {
    clearKind(db, "WATERLOGGING", zid);
  }
  if (!weather) {
    raiseAlert(db, "WEATHER_OFFLINE", "weather data unavailable");
  } else {
    clearKind(db, "WEATHER_OFFLINE");
    if ((weather.temperature_c ?? 0) >= cfg.engine.heat_alert_c) {
      raiseAlert(db, "HEAT", `temperature ${Math.round(weather.temperature_c)} C`, zid);
    } else {
      clearKind(db, "HEAT", zid);
    }
    if (rec.action === "SKIP_RAIN") {
      raiseAlert(db, "RAIN_INCOMING", `${zone.name}: rain expected, skipping irrigation`, zid);
    } else {
      clearKind(db, "RAIN_INCOMING", zid);
    }
  }
}
