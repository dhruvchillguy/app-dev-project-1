import { describe, it, expect } from "vitest";
import { duration, decide } from "../src/engine.js";
import { loadDefaults } from "../src/config.js";

describe("engine decisions and duration", () => {
  const cfg = loadDefaults();
  const crop = { crop_factor: 1.15, water_holding_mm: 75, min_pct: 60, target_pct: 85 };
  const zone = { id: 1, name: "Zone 1", crop: "tomato", area_m2: 400, irrigation: "drip", flow_mm_hr: 8.0, min_pct: null, target_pct: null };

  it("calculates exact hand-checked duration of 156.25 minutes", () => {
    const [mins, capped] = duration(60.0, 85.0, 75.0, 8.0, 0.9, 180);
    expect(mins).toBeCloseTo(156.25, 2);
    expect(capped).toBe(false);
  });

  it("caps duration at max_run_minutes", () => {
    const [mins, capped] = duration(50.0, 85.0, 75.0, 8.0, 0.9, 180);
    expect(mins).toBe(180);
    expect(capped).toBe(true);
  });

  it("returns NO_DATA when no readings exist", () => {
    const rec = decide(zone, crop, [], null, "2026-09-20T05:30:00Z", 330, cfg);
    expect(rec.action).toBe("NO_DATA");
  });

  it("returns OK when moisture is at or above minimum", () => {
    const readings = [{ ts: "2026-09-20T05:30:00Z", moisture_pct: 65.0 }];
    const rec = decide(zone, crop, readings, null, "2026-09-20T05:30:00Z", 330, cfg);
    expect(rec.action).toBe("OK");
  });

  it("returns IRRIGATE_NOW inside allowed window when moisture is below minimum", () => {
    const readings = [{ ts: "2026-09-20T05:30:00Z", moisture_pct: 54.0 }];
    const rec = decide(zone, crop, readings, null, "2026-09-20T05:30:00Z", 330, cfg);
    expect(rec.action).toBe("IRRIGATE_NOW");
    expect(rec.reason).toContain("below minimum");
  });

  it("returns WAIT_WIND for sprinkler zone when wind is above limit", () => {
    const sprinklerZone = { id: 2, name: "Zone 2", crop: "maize", area_m2: 1200, irrigation: "sprinkler", flow_mm_hr: 10.0, min_pct: null, target_pct: null };
    const maizeCrop = { crop_factor: 1.20, water_holding_mm: 120, min_pct: 45, target_pct: 85 };
    const readings = [{ ts: "2026-09-20T05:30:00Z", moisture_pct: 40.0 }];
    const weather = { wind_kmh: 28.0, hourly_times: [], hourly_precip_mm: [], hourly_precip_prob: [] };
    const rec = decide(sprinklerZone, maizeCrop, readings, weather, "2026-09-20T05:30:00Z", 330, cfg);
    expect(rec.action).toBe("WAIT_WIND");
  });
});
