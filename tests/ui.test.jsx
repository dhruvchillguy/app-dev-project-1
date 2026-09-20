import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "ink-testing-library";
import { openDb } from "../src/db.js";
import { getConfig } from "../src/config.js";
import { seedData } from "../src/farm.js";
import { setupDemo } from "../src/demo.js";
import { SimulatedSensor } from "../src/sensors.js";
import { App } from "../src/ui/app.jsx";

describe("terminal interface with ink", () => {
  it("renders dashboard with 3 zones, weather, and simulated banner after ticks", async () => {
    const db = openDb(":memory:", "src/schema.sql");
    const cfg = getConfig();
    seedData(db, cfg);
    const scenario = setupDemo(1800.0);
    const zones = db.prepare("SELECT * FROM zones ORDER BY id").all();
    const sensor = new SimulatedSensor(zones, cfg, 42);
    if (scenario.zone_initial_moisture) {
      for (const [zid, m] of Object.entries(scenario.zone_initial_moisture)) {
        sensor.moisture[Number(zid)] = Number(m);
      }
    }

    const { lastFrame, stdin, unmount } = render(
      <App
        db={db}
        cfg={cfg}
        demo={true}
        scenario={scenario}
        sensor={sensor}
        source="sim"
        mode="auto"
      />
    );

    await new Promise(r => setTimeout(r, 350));
    const frame = lastFrame();

    expect(frame).toContain("Sinchai");
    expect(frame).toContain("[SIMULATED DATA]");
    expect(frame).toContain("Zone 1");
    expect(frame).toContain("Zone 2");
    expect(frame).toContain("Zone 3");
    expect(frame).toContain("Weather |");

    stdin.write("m");
    await new Promise(r => setTimeout(r, 60));
    expect(lastFrame()).toContain("mode MANUAL");

    stdin.write("v");
    await new Promise(r => setTimeout(r, 60));
    expect(lastFrame()).toContain("OPEN");

    stdin.write("r");
    await new Promise(r => setTimeout(r, 60));
    expect(lastFrame()).toContain("[REPORTS]");
    expect(lastFrame()).toContain("Baseline:");

    stdin.write("l");
    await new Promise(r => setTimeout(r, 60));
    expect(lastFrame()).toContain("[RAINCHECK]");

    stdin.write("z");
    await new Promise(r => setTimeout(r, 60));
    expect(lastFrame()).toContain("[ZONES]");

    unmount();
  });
});
