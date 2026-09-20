import { now, toIso, fromIso } from "./clock.js";

export function maybeOpenSkip(db, zone, rec, cfg) {
  if (rec.action !== "SKIP_RAIN") return;
  const existing = db.prepare("SELECT id FROM skips WHERE zone_id = ? AND resolved_at IS NULL").get(zone.id);
  if (existing) return;
  const nowDt = now();
  const ts = toIso(nowDt);
  const lookaheadMs = cfg.engine.rain_lookahead_hours * 3600000;
  const deadline = toIso(new Date(nowDt.getTime() + lookaheadMs));
  const hours = (rec.minutes || 0) / 60.0;
  const litres = hours * zone.flow_mm_hr * zone.area_m2;
  db.prepare(`INSERT INTO skips (zone_id, decided_at, forecast_mm, forecast_prob, deadline_at, litres_withheld)
    VALUES (?, ?, ?, ?, ?, ?)`).run(zone.id, ts, rec.forecast_mm || 0.0, rec.forecast_prob || 0.0, deadline, litres);
}

export function resolveDueSkips(db, zones, cfg) {
  const nowIso = toIso(now());
  const due = db.prepare("SELECT * FROM skips WHERE resolved_at IS NULL AND deadline_at <= ?").all(nowIso);
  for (const skip of due) {
    const rainRow = db.prepare("SELECT SUM(mm) as total FROM rain_obs WHERE hour_ts >= ? AND hour_ts <= ?").get(skip.decided_at, skip.deadline_at);
    const actualMm = rainRow?.total ?? 0.0;
    const threshold = Math.max(cfg.ledger.hit_min_mm, cfg.ledger.hit_fraction * (skip.forecast_mm || 0.0));
    const verdict = actualMm >= threshold ? "HIT" : "MISS";
    const minRow = db.prepare("SELECT MIN(moisture_pct) as min_m FROM readings WHERE zone_id = ? AND ts >= ? AND ts <= ?").get(skip.zone_id, skip.decided_at, skip.deadline_at);
    const minM = minRow?.min_m ?? null;
    db.prepare(`UPDATE skips SET resolved_at = ?, actual_mm = ?, verdict = ?, min_moisture = ? WHERE id = ?`).run(nowIso, actualMm, verdict, minM, skip.id);
  }
}

export function ledgerSummary(db) {
  const rows = db.prepare("SELECT verdict, litres_withheld, min_moisture FROM skips WHERE resolved_at IS NOT NULL").all();
  if (rows.length === 0) return "No rain skips recorded yet.";
  const hits = rows.filter(r => r.verdict === "HIT").length;
  const misses = rows.filter(r => r.verdict === "MISS").length;
  const totalL = rows.reduce((sum, r) => sum + (r.litres_withheld || 0), 0);
  const missRows = rows.filter(r => r.verdict === "MISS");
  const parts = [`${rows.length} skips: ${hits} hits, ${misses} misses. ${Math.round(totalL).toLocaleString()} L not applied.`];
  if (missRows.length > 0) {
    const lows = missRows.map(r => r.min_moisture ?? 999);
    const low = Math.min(...lows);
    parts.push(`In misses, moisture dropped as low as ${Math.round(low)}%.`);
  }
  return parts.join(" ");
}
