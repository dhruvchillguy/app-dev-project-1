#!/usr/bin/env -S node --no-warnings --import tsx
import { parseArgs } from "node:util";
import fs from "node:fs";
import React from "react";
import { render } from "ink";
import { openDb, getZones } from "./db.js";
import { getConfig } from "./config.js";
import { seedData, runHeadless } from "./farm.js";
import { setupDemo } from "./demo.js";
import { SimulatedSensor } from "./sensors.js";
import { runMcpServer } from "./mcp-server.js";
import { farmBrief } from "./reports.js";

const options = {
  demo: { type: "boolean", default: false },
  mode: { type: "string", default: "auto" },
  speed: { type: "string", default: "1800" },
  seed: { type: "string", default: "42" },
  ticks: { type: "string" },
  source: { type: "string", default: "sim" },
  db: { type: "string", default: process.env.SINCHAI_DB || "data/sinchai.db" },
  port: { type: "string" },
  table: { type: "string" },
  out: { type: "string" },
  force: { type: "boolean", default: false },
  headless: { type: "boolean", default: false }
};

async function doctor(dbPath) {
  const v = process.versions.node.split(".").map(Number);
  const okNode = v[0] > 22 || (v[0] === 22 && v[1] >= 13);
  console.log(`${okNode ? "PASS" : "FAIL"}  Node >= 22.13: ${process.version}`);
  try {
    const db = openDb(dbPath, "src/schema.sql");
    db.prepare("SELECT 1 FROM zones LIMIT 1").get();
    console.log(`PASS  Database access: ${dbPath}`);
  } catch (e) {
    console.log(`FAIL  Database access: ${e.message}`);
  }
  try {
    const res = await fetch("https://api.open-meteo.com/v1/forecast?latitude=15.45&longitude=75.0&current=temperature_2m", { signal: AbortSignal.timeout(5000) });
    console.log(`PASS  Weather API: HTTP ${res.status}`);
  } catch (e) {
    console.log(`FAIL  Weather API: ${e.message}`);
  }
  const term = process.stdout.columns && process.stdout.rows ? `${process.stdout.columns}x${process.stdout.rows}` : "unknown";
  console.log(`PASS  Terminal: ${term}`);
}

function exportCsv(dbPath, table, out, force) {
  const db = openDb(dbPath, "src/schema.sql");
  const rows = db.prepare(`SELECT * FROM ${table}`).all();
  if (rows.length === 0) return console.log(`No rows in ${table}.`);
  const keys = Object.keys(rows[0]);
  const lines = [keys.join(","), ...rows.map(r => keys.map(k => JSON.stringify(r[k] ?? "")).join(","))];
  if (out) {
    if (fs.existsSync(out) && !force) throw new Error(`File ${out} exists. Use --force.`);
    fs.writeFileSync(out, lines.join("\n"));
    console.log(`Exported ${rows.length} rows to ${out}`);
  } else {
    console.log(lines.join("\n"));
  }
}

export async function main(args = process.argv.slice(2)) {
  const { values, positionals } = parseArgs({ args, options, allowPositionals: true });
  const cmd = positionals[0] || (values.demo ? "demo" : "run");
  const dbPath = values.db;
  const cfg = getConfig(dbPath);
  const isDemo = values.demo || cmd === "demo";

  if (cmd === "mcp") return runMcpServer(dbPath);
  if (cmd === "doctor") return doctor(dbPath);
  if (cmd === "brief") {
    const db = openDb(dbPath, "src/schema.sql");
    seedData(db, cfg);
    return console.log(farmBrief(db, getZones(db), cfg));
  }
  if (cmd === "export") return exportCsv(dbPath, values.table || "readings", values.out, values.force);

  if (values.headless || cmd === "headless") {
    const ticks = values.ticks ? Number(values.ticks) : null;
    const n = await runHeadless(dbPath, cfg, values.mode, isDemo, Number(values.speed), Number(values.seed), values.source, ticks);
    return console.log(`Ran ${n} ticks.`);
  }

  const { App } = await import("./ui/app.jsx");
  const db = openDb(dbPath, "src/schema.sql");
  seedData(db, cfg);
  const scenario = isDemo ? setupDemo(Number(values.speed)) : null;
  const zones = getZones(db);
  const sensor = new SimulatedSensor(zones, cfg, Number(values.seed));
  if (scenario?.zone_initial_moisture) {
    for (const [zid, m] of Object.entries(scenario.zone_initial_moisture)) {
      sensor.moisture[Number(zid)] = Number(m);
    }
  }
  render(React.createElement(App, { db, cfg, demo: isDemo, scenario, sensor, source: values.source, mode: values.mode }));
}

if (process.argv[1] && (process.argv[1].endsWith("cli.js") || process.argv[1].endsWith("index.js"))) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}
