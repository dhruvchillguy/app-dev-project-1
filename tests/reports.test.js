import { describe, it, expect } from "vitest";
import { openDb } from "../src/db.js";
import { getConfig } from "../src/config.js";
import { seedData } from "../src/farm.js";
import { baselineLitres, zoneReport } from "../src/reports.js";
import { duration } from "../src/engine.js";

describe("reports", () => {
  it("computes litres formula correctly", () => {
    const mm = 20.0;
    const area = 500.0;
    const litres = (mm / 1000.0) * 1000.0 * area;
    expect(Math.abs(litres - 10000.0)).toBeLessThan(0.01);
  });

  it("computes baseline litres for 1 day", () => {
    const zone = { flow_mm_hr: 8.0, area_m2: 400, id: 1, name: "Z1", crop: "tomato" };
    const cfg = getConfig();
    const base = baselineLitres(zone, cfg, 1);
    const expected = 8.0 * (30.0 / 60.0) * 400.0;
    expect(Math.abs(base - expected)).toBeLessThan(0.01);
  });

  it("computes duration for tomato drip without cap", () => {
    const [minutes, capped] = duration(60, 85, 75, 8, 0.9, 180);
    expect(Math.abs(minutes - 156.25)).toBeLessThan(0.1);
    expect(capped).toBe(false);
  });

  it("computes duration cap", () => {
    const [minutes, capped] = duration(0, 100, 500, 8, 0.9, 180);
    expect(minutes).toBe(180);
    expect(capped).toBe(true);
  });

  it("computes baseline litres for 7 days", () => {
    const zone = { flow_mm_hr: 10.0, area_m2: 400, id: 2, name: "Z2", crop: "maize" };
    const cfg = getConfig();
    const base = baselineLitres(zone, cfg, 7);
    expect(Math.abs(base - 14000.0)).toBeLessThan(0.01);
  });

  it("computes zoneReport with db records", () => {
    const db = openDb(":memory:", "src/schema.sql");
    const cfg = getConfig();
    seedData(db, cfg);
    const zones = db.prepare("SELECT * FROM zones").all();
    const rep = zoneReport(db, zones, cfg, 7);
    expect(rep).toHaveLength(3);
    expect(rep[0].name).toBe("Zone 1");
    expect(rep[0].litres_used).toBe(0);
    expect(rep[0].baseline_litres).toBeGreaterThan(0);
  });
});
