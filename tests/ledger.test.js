import { describe, it, expect } from "vitest";
import { openDb } from "../src/db.js";
import { maybeOpenSkip, resolveDueSkips, ledgerSummary } from "../src/ledger.js";
import { loadDefaults } from "../src/config.js";
import { configureDemo, fromIso } from "../src/clock.js";

describe("rain check ledger", () => {
  const cfg = loadDefaults();
  const zone = { id: 1, crop: "tomato", flow_mm_hr: 8.0, area_m2: 400 };

  function setupDb() {
    const db = openDb(":memory:", "src/schema.sql");
    db.prepare("INSERT INTO crops (name, crop_factor, water_holding_mm, min_pct, target_pct) VALUES ('tomato', 1.15, 75, 60, 85)").run();
    db.prepare("INSERT INTO zones (id, name, crop, area_m2, irrigation, flow_mm_hr) VALUES (1, 'Zone 1', 'tomato', 400, 'drip', 8.0)").run();
    return db;
  }

  it("opens a skip row when recommendation is SKIP_RAIN", () => {
    const db = setupDb();
    configureDemo(fromIso("2026-09-20T00:00:00Z"), 1.0);
    const rec = { action: "SKIP_RAIN", minutes: 60, forecast_mm: 8.0, forecast_prob: 80 };
    maybeOpenSkip(db, zone, rec, cfg);

    const rows = db.prepare("SELECT * FROM skips").all();
    expect(rows.length).toBe(1);
    expect(rows[0].forecast_mm).toBe(8.0);
    expect(rows[0].resolved_at).toBeNull();
  });

  it("resolves as HIT when rain reaches threshold", () => {
    const db = setupDb();
    configureDemo(fromIso("2026-09-20T00:00:00Z"), 1.0);
    const rec = { action: "SKIP_RAIN", minutes: 60, forecast_mm: 8.0, forecast_prob: 80 };
    maybeOpenSkip(db, zone, rec, cfg);

    db.prepare("INSERT INTO rain_obs (hour_ts, mm) VALUES ('2026-09-20T02:00:00Z', 6.0)").run();
    db.prepare("INSERT INTO readings (zone_id, ts, moisture_pct) VALUES (1, '2026-09-20T01:00:00Z', 50.0)").run();

    configureDemo(fromIso("2026-09-20T13:00:00Z"), 1.0);
    resolveDueSkips(db, [zone], cfg);

    const row = db.prepare("SELECT * FROM skips WHERE id = 1").get();
    expect(row.verdict).toBe("HIT");
    expect(row.actual_mm).toBe(6.0);
  });

  it("resolves as MISS when no rain falls", () => {
    const db = setupDb();
    configureDemo(fromIso("2026-09-20T00:00:00Z"), 1.0);
    const rec = { action: "SKIP_RAIN", minutes: 60, forecast_mm: 8.0, forecast_prob: 80 };
    maybeOpenSkip(db, zone, rec, cfg);

    db.prepare("INSERT INTO readings (zone_id, ts, moisture_pct) VALUES (1, '2026-09-20T01:00:00Z', 42.0)").run();

    configureDemo(fromIso("2026-09-20T13:00:00Z"), 1.0);
    resolveDueSkips(db, [zone], cfg);

    const row = db.prepare("SELECT * FROM skips WHERE id = 1").get();
    expect(row.verdict).toBe("MISS");
    expect(row.actual_mm).toBe(0.0);
    expect(row.min_moisture).toBe(42.0);

    const summary = ledgerSummary(db);
    expect(summary).toContain("1 misses");
    expect(summary).toContain("42%");
  });
});
