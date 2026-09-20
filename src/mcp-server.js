import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { openDb, getZones, getCrop, getRecentReadings, getActiveAlerts, getControllerRow } from "./db.js";
import { getConfig } from "./config.js";
import { decide } from "./engine.js";
import { zoneReport } from "./reports.js";
import { ledgerSummary } from "./ledger.js";
import { now, toIso, fromIso, localMinutes } from "./clock.js";

function getBase(db) {
  const row = getControllerRow(db);
  const nowDt = now();
  if (!row) return { as_of: toIso(nowDt), data_age_minutes: null, controller_running: false, simulated: true };
  const running = (nowDt - fromIso(row.heartbeat_at)) / 1000.0 < 15;
  const age = row.clock_now ? Math.round(((nowDt - fromIso(row.clock_now)) / 60000.0) * 10) / 10 : null;
  return { as_of: row.clock_now, data_age_minutes: age, controller_running: running, simulated: row.source === "sim" || row.demo === 1 };
}

function getZoneRec(db, zoneId, cfg) {
  const zone = getZones(db).find(z => z.id === zoneId);
  if (!zone) return null;
  const readings = getRecentReadings(db, zoneId, 24);
  const crop = getCrop(db, zone.crop);
  const nowDt = now();
  const rec = decide(zone, crop, readings, null, toIso(nowDt), localMinutes(nowDt, cfg.location.utc_offset_minutes), cfg);
  return { zone, readings, rec };
}

export function createMcpServer(dbPath) {
  const db = openDb(dbPath, "src/schema.sql");
  const cfg = getConfig(dbPath);
  const server = new McpServer({ name: "sinchai", version: "1.0.0" });

  server.tool("list_zones", {}, async () => {
    const base = getBase(db);
    const zones = getZones(db).map(z => {
      const r = getRecentReadings(db, z.id, 1)[0];
      const age = r ? Math.round(((now() - fromIso(r.ts)) / 60000.0) * 10) / 10 : null;
      return { id: z.id, name: z.name, crop: z.crop, flow_mm_hr: z.flow_mm_hr, irrigation: z.irrigation, moisture_pct: r?.moisture_pct ?? null, reading_age_minutes: age, valve_open: Boolean(z.valve_open) };
    });
    return { content: [{ type: "text", text: JSON.stringify({ ...base, zones }, null, 2) }] };
  });

  server.tool("get_zone_status", { zone_id: z.number() }, async ({ zone_id }) => {
    const res = getZoneRec(db, zone_id, cfg);
    if (!res) return { content: [{ type: "text", text: JSON.stringify({ error: `zone ${zone_id} not found` }) }] };
    const { zone, readings, rec } = res;
    const alerts = getActiveAlerts(db).filter(a => a.zone_id === zone_id).map(a => ({ kind: a.kind, message: a.message }));
    return { content: [{ type: "text", text: JSON.stringify({ ...getBase(db), zone: zone.name, crop: zone.crop, moisture_pct: readings[0]?.moisture_pct ?? null, action: rec.action, minutes: rec.minutes, reason: rec.reason, alerts }, null, 2) }] };
  });

  server.tool("explain_recommendation", { zone_id: z.number() }, async ({ zone_id }) => {
    const res = getZoneRec(db, zone_id, cfg);
    if (!res) return { content: [{ type: "text", text: JSON.stringify({ error: `zone ${zone_id} not found` }) }] };
    return { content: [{ type: "text", text: JSON.stringify({ ...getBase(db), action: res.rec.action, reason: res.rec.reason, trace: res.rec.trace }, null, 2) }] };
  });

  server.tool("get_weather_outlook", {}, async () => {
    const cached = db.prepare("SELECT * FROM weather_cache WHERE key = 'forecast'").get();
    if (!cached) return { content: [{ type: "text", text: JSON.stringify({ ...getBase(db), status: "OFFLINE" }) }] };
    const ageH = (now() - fromIso(cached.fetched_at)) / 3600000.0;
    const cur = JSON.parse(cached.payload)?.current || {};
    return { content: [{ type: "text", text: JSON.stringify({ ...getBase(db), status: ageH < 0.5 ? "LIVE" : "CACHED", cache_age_hours: Math.round(ageH * 10) / 10, temperature_c: cur.temperature_2m, wind_kmh: cur.wind_speed_10m, precip_current_mm: cur.precipitation }, null, 2) }] };
  });

  server.tool("water_report", { days: z.number().optional().default(7) }, async ({ days }) => {
    if (days < 1 || days > 30) return { content: [{ type: "text", text: JSON.stringify({ error: "days must be between 1 and 30" }) }] };
    const zList = zoneReport(db, getZones(db), cfg, days);
    return { content: [{ type: "text", text: JSON.stringify({ ...getBase(db), assumption: "Baseline assumes 30 min irrigation per day per zone at zone flow rate.", zones: zList }, null, 2) }] };
  });

  server.tool("rain_check_ledger", { limit: z.number().optional().default(10) }, async ({ limit }) => {
    if (limit < 1 || limit > 50) return { content: [{ type: "text", text: JSON.stringify({ error: "limit must be between 1 and 50" }) }] };
    const skips = db.prepare("SELECT * FROM skips ORDER BY decided_at DESC LIMIT ?").all(limit);
    return { content: [{ type: "text", text: JSON.stringify({ ...getBase(db), summary: ledgerSummary(db), skips }, null, 2) }] };
  });

  server.tool("request_valve", { zone_id: z.number(), action: z.enum(["open", "close"]), minutes: z.number().optional().default(30) }, async ({ zone_id, action, minutes }) => {
    if (!cfg.mcp?.allow_valve_requests) return { content: [{ type: "text", text: JSON.stringify({ error: "valve requests disabled (allow_valve_requests=false in config)" }) }] };
    if (minutes < 1 || minutes > (cfg.mcp?.max_request_minutes || 60)) return { content: [{ type: "text", text: JSON.stringify({ error: "invalid minutes" }) }] };
    const zone = getZones(db).find(z => z.id === zone_id);
    if (!zone) return { content: [{ type: "text", text: JSON.stringify({ error: `zone ${zone_id} not found` }) }] };
    const info = db.prepare("INSERT INTO valve_requests (zone_id, action, minutes, requested_at) VALUES (?, ?, ?, ?)").run(zone_id, action, minutes, toIso(now()));
    return { content: [{ type: "text", text: JSON.stringify({ request_id: Number(info.lastInsertRowid), status: "pending", controller_running: getBase(db).controller_running }) }] };
  });

  return server;
}

export async function runMcpServer(dbPath) {
  const server = createMcpServer(dbPath || process.env.SINCHAI_DB || "data/sinchai.db");
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

if (process.argv[1] && process.argv[1].endsWith("mcp-server.js")) {
  runMcpServer(process.env.SINCHAI_DB || "data/sinchai.db").catch(err => {
    console.error("MCP Server Error:", err);
    process.exit(1);
  });
}
