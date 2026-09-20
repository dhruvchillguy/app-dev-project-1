import { describe, it, expect } from "vitest";
import { openDb, getZones, insertReading, getRecentReadings, setValve, closeAllValves, upsertController, getControllerRow, clearController } from "../src/db.js";

describe("database operations", () => {
  it("opens in-memory db with schema and executes operations", () => {
    const db = openDb(":memory:", "src/schema.sql");
    db.prepare("INSERT INTO crops (name, crop_factor, water_holding_mm, min_pct, target_pct) VALUES (?, ?, ?, ?, ?)").run("tomato", 1.15, 75, 60, 85);
    db.prepare("INSERT INTO zones (id, name, crop, area_m2, irrigation, flow_mm_hr) VALUES (?, ?, ?, ?, ?, ?)").run(1, "Zone 1", "tomato", 400, "drip", 8.0);
    
    const zones = getZones(db);
    expect(zones.length).toBe(1);
    expect(zones[0].crop).toBe("tomato");

    insertReading(db, 1, "2026-09-20T05:00:00Z", 55.0, 2000, "sim");
    const readings = getRecentReadings(db, 1);
    expect(readings.length).toBe(1);
    expect(readings[0].moisture_pct).toBe(55.0);

    setValve(db, 1, true, "2026-09-20T05:00:00Z", "auto", 30, 1600);
    expect(getZones(db)[0].valve_open).toBe(1);

    const closed = closeAllValves(db, "2026-09-20T05:30:00Z", "failsafe");
    expect(closed).toBe(1);
    expect(getZones(db)[0].valve_open).toBe(0);

    upsertController(db, 1234, "2026-09-20T05:00:00Z", "2026-09-20T05:00:00Z", "2026-09-20T05:00:00Z", "auto", "sim", true, 1800.0);
    expect(getControllerRow(db).pid).toBe(1234);
    clearController(db);
    expect(getControllerRow(db)).toBeUndefined();
  });
});
