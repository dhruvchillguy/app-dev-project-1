import { describe, it, expect } from "vitest";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { openDb } from "../src/db.js";
import { getConfig } from "../src/config.js";
import { seedData } from "../src/farm.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

describe("MCP Server", () => {
  it("connects over stdio, lists tools, and executes queries", async () => {
    const tmpDb = path.join(__dirname, "test-mcp.db");
    if (fs.existsSync(tmpDb)) fs.unlinkSync(tmpDb);

    const db = openDb(tmpDb, "src/schema.sql");
    const cfg = getConfig();
    seedData(db, cfg);
    db.close();

    const serverScript = path.resolve(__dirname, "../src/mcp-server.js");
    const transport = new StdioClientTransport({
      command: "node",
      args: ["--no-warnings", serverScript],
      env: { ...process.env, SINCHAI_DB: tmpDb }
    });

    const client = new Client({ name: "test-client", version: "1.0.0" });
    await client.connect(transport);

    const tools = await client.listTools();
    const names = tools.tools.map(t => t.name);
    expect(names).toContain("list_zones");
    expect(names).toContain("get_zone_status");
    expect(names).toContain("explain_recommendation");
    expect(names).toContain("get_weather_outlook");
    expect(names).toContain("water_report");
    expect(names).toContain("rain_check_ledger");
    expect(names).toContain("request_valve");

    const badStatus = await client.callTool({ name: "get_zone_status", arguments: { zone_id: 999 } });
    expect(badStatus.content[0].text).toContain("not found");

    const valveReq = await client.callTool({ name: "request_valve", arguments: { zone_id: 1, action: "open", minutes: 30 } });
    expect(valveReq.content[0].text).toContain("disabled");

    const listRes = await client.callTool({ name: "list_zones", arguments: {} });
    expect(listRes.content[0].text).toContain("Zone 1");

    await client.close();
    if (fs.existsSync(tmpDb)) fs.unlinkSync(tmpDb);
  });
});
