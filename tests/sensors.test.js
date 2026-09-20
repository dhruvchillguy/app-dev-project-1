import { describe, it, expect } from "vitest";
import { parseSerialLine, SimulatedSensor } from "../src/sensors.js";
import { loadDefaults } from "../src/config.js";

describe("sensors and serial line parser", () => {
  it("parses valid JSON serial line", () => {
    const res = parseSerialLine('{"zone_id": 1, "raw": 2150}\n');
    expect(res.zone_id).toBe(1);
    expect(res.raw).toBe(2150);
  });

  it("rejects overlong serial line", () => {
    const longLine = "a".repeat(300);
    expect(() => parseSerialLine(longLine)).toThrow("line too long");
  });

  it("rejects malformed serial line", () => {
    expect(() => parseSerialLine('{"zone_id": "one"}')).toThrow();
  });

  it("simulates sensor ticks within valid range", () => {
    const cfg = loadDefaults();
    const zones = [{ id: 1, crop: "tomato", irrigation: "drip", flow_mm_hr: 8.0 }];
    const sensor = new SimulatedSensor(zones, cfg, 42);
    const crop = cfg.crops.tomato;
    const m = sensor.tick(zones[0], crop, 5.0 / 60.0, false);
    expect(m).toBeGreaterThan(0);
    expect(m).toBeLessThanOrEqual(110);
  });
});
