import fs from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export function loadDefaults() {
  const p = path.join(__dirname, "defaults.json");
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

export function loadDbSettings(dbPath) {
  try {
    const db = new DatabaseSync(dbPath);
    const rows = db.prepare("SELECT key, value FROM settings").all();
    const map = {};
    for (const r of rows) {
      map[r.key] = r.value;
    }
    return map;
  } catch {
    return {};
  }
}

export function applySettings(cfg, dbSettings) {
  for (const [dotkey, raw] of Object.entries(dbSettings)) {
    const parts = dotkey.split(".");
    let node = cfg;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!node[parts[i]]) node[parts[i]] = {};
      node = node[parts[i]];
    }
    const last = parts[parts.length - 1];
    if (raw.toLowerCase() === "true" || raw.toLowerCase() === "false") {
      node[last] = raw.toLowerCase() === "true";
    } else {
      const num = Number(raw);
      node[last] = isNaN(num) ? raw : num;
    }
  }
  return cfg;
}

export function getConfig(dbPath) {
  return applySettings(loadDefaults(), loadDbSettings(dbPath));
}
