import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";

export function openDb(dbPath, schemaPath) {
  if (dbPath !== ":memory:") {
    fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  }
  const db = new DatabaseSync(dbPath);
  db.exec("PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;");
  if (schemaPath) {
    db.exec(fs.readFileSync(schemaPath, "utf8"));
  }
  return db;
}

export function getZones(db) {
  return db.prepare("SELECT * FROM zones ORDER BY id").all();
}

export function getCrop(db, name) {
  return db.prepare("SELECT * FROM crops WHERE name = ?").get(name);
}

export function insertReading(db, zoneId, ts, moisture, raw, source) {
  db.prepare("INSERT INTO readings (zone_id, ts, moisture_pct, raw, source) VALUES (?, ?, ?, ?, ?)").run(zoneId, ts, moisture, raw, source);
}

export function getRecentReadings(db, zoneId, n = 12) {
  return db.prepare("SELECT * FROM readings WHERE zone_id = ? ORDER BY ts DESC LIMIT ?").all(zoneId, n);
}

export function setValve(db, zoneId, open, ts, source, minutes = null, litres = null) {
  if (open) {
    db.prepare("UPDATE zones SET valve_open = 1, valve_opened_at = ? WHERE id = ?").run(ts, zoneId);
  } else {
    db.prepare("UPDATE zones SET valve_open = 0, valve_opened_at = NULL, last_closed_at = ? WHERE id = ?").run(ts, zoneId);
  }
  const action = open ? "open" : "close";
  db.prepare("INSERT INTO valve_events (zone_id, ts, action, source, minutes, litres) VALUES (?, ?, ?, ?, ?, ?)").run(zoneId, ts, action, source, minutes, litres);
}

export function closeAllValves(db, ts, source = "failsafe") {
  const rows = db.prepare("SELECT id FROM zones WHERE valve_open = 1").all();
  for (const row of rows) {
    setValve(db, row.id, false, ts, source);
  }
  return rows.length;
}

export function upsertRainObs(db, hourTs, mm, source = "weather") {
  db.prepare(`INSERT INTO rain_obs (hour_ts, mm, source) VALUES (?, ?, ?)
    ON CONFLICT(hour_ts) DO UPDATE SET mm = excluded.mm, source = excluded.source`).run(hourTs, mm, source);
}

export function insertAlert(db, ts, zoneId, kind, severity, message) {
  return db.prepare("INSERT INTO alerts (ts, zone_id, kind, severity, message) VALUES (?, ?, ?, ?, ?)").run(ts, zoneId, kind, severity, message).lastInsertRowid;
}

export function clearAlert(db, alertId, ts) {
  db.prepare("UPDATE alerts SET cleared_ts = ? WHERE id = ?").run(ts, alertId);
}

export function getActiveAlerts(db) {
  return db.prepare("SELECT * FROM alerts WHERE cleared_ts IS NULL ORDER BY ts DESC").all();
}

export function upsertController(db, pid, startedAt, hbAt, clockNow, mode, source, demo, speed) {
  db.prepare(`INSERT INTO controller (id, pid, started_at, heartbeat_at, clock_now, mode, source, demo, speed)
    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET heartbeat_at = excluded.heartbeat_at, clock_now = excluded.clock_now, mode = excluded.mode`).run(pid, startedAt, hbAt, clockNow, mode, source, demo ? 1 : 0, speed);
}

export function getControllerRow(db) {
  return db.prepare("SELECT * FROM controller WHERE id = 1").get();
}

export function clearController(db) {
  db.prepare("DELETE FROM controller WHERE id = 1").run();
}
