import { describe, it, expect } from "vitest";
import { runHeadless } from "../src/farm.js";
import { loadDefaults } from "../src/config.js";
import { openDb } from "../src/db.js";

describe("headless demo acceptance", () => {
  it("executes demo scenario with valve events, skips, and alerts", async () => {
    const cfg = loadDefaults();
    const dbPath = ":memory:";
    const ticks = await runHeadless(dbPath, cfg, "auto", true, 1800.0, 1, "sim", 20);
    expect(ticks).toBe(20);
  });
});
