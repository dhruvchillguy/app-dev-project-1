import { describe, it, expect } from "vitest";
import { rawToMoisture } from "../src/sensors.js";

describe("sensor calibration", () => {
  it("converts midpoint raw to exactly 50.0 percent", () => {
    const pct = rawToMoisture(2150, 3000, 1300);
    expect(pct).toBe(50.0);
  });

  it("converts dry raw to 0.0 percent", () => {
    expect(rawToMoisture(3000, 3000, 1300)).toBe(0.0);
  });

  it("converts wet raw to 100.0 percent", () => {
    expect(rawToMoisture(1300, 3000, 1300)).toBe(100.0);
  });

  it("throws when dry_raw equals wet_raw", () => {
    expect(() => rawToMoisture(2000, 2000, 2000)).toThrow("dry_raw equals wet_raw");
  });

  it("throws when raw is in low fault range", () => {
    expect(() => rawToMoisture(40, 3000, 1300)).toThrow("fault range");
  });

  it("throws when raw is in high fault range", () => {
    expect(() => rawToMoisture(4050, 3000, 1300)).toThrow("fault range");
  });
});
