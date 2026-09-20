import { describe, it, expect } from "vitest";
import fs from "node:fs";
import { parseWeather, getWeather } from "../src/weather.js";
import { openDb } from "../src/db.js";
import { loadDefaults } from "../src/config.js";

describe("weather client and cache", () => {
  it("parses raw Open-Meteo fixture correctly", () => {
    const raw = JSON.parse(fs.readFileSync("tests/fixtures/open_meteo_live.json", "utf8"));
    const parsed = parseWeather(raw, "2026-09-20T05:00:00Z");
    expect(parsed.temperature_c).toBeDefined();
    expect(parsed.wind_kmh).toBeDefined();
    expect(parsed.hourly_times.length).toBeGreaterThan(0);
  });

  it("returns cached weather when cache is fresh", async () => {
    const db = openDb(":memory:", "src/schema.sql");
    const cfg = loadDefaults();
    const raw = JSON.parse(fs.readFileSync("tests/fixtures/open_meteo_live.json", "utf8"));
    const ts = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    db.prepare("INSERT INTO weather_cache (key, fetched_at, payload) VALUES ('forecast', ?, ?)").run(ts, JSON.stringify(raw));

    const w = await getWeather(db, cfg);
    expect(w).not.toBeNull();
    expect(w.hourly_times.length).toBeGreaterThan(0);
  });
});
