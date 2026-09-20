export function waterUsed(db, zoneId, days = 7) {
  const rows = db.prepare(`
    SELECT substr(ts,1,10) as day, SUM(litres) as litres
    FROM valve_events WHERE zone_id=? AND action='close' AND litres IS NOT NULL
    AND ts >= datetime('now', ?)
    GROUP BY day ORDER BY day
  `).all(zoneId, `-${days} days`);
  return rows.map(r => ({ day: r.day, litres: r.litres || 0 }));
}

export function baselineLitres(zone, cfg, days = 7) {
  const baseMin = cfg?.reports?.baseline_minutes_per_day ?? 30;
  const litresPerDay = zone.flow_mm_hr * (baseMin / 60.0) * zone.area_m2;
  return litresPerDay * days;
}

export function stressHours(db, zoneId, minPct, days = 7) {
  const row = db.prepare(`
    SELECT COUNT(*) as count FROM readings WHERE zone_id=? AND moisture_pct < ?
    AND ts >= datetime('now', ?)
  `).get(zoneId, minPct, `-${days} days`);
  return (row?.count || 0) * (5.0 / 60.0);
}

export function zoneReport(db, zones, cfg, days = 7) {
  const rows = [];
  for (const zone of zones) {
    const crop = db.prepare("SELECT * FROM crops WHERE name=?").get(zone.crop);
    const mn = zone.min_pct != null ? zone.min_pct : (crop?.min_pct ?? 45);
    const used = waterUsed(db, zone.id, days).reduce((acc, r) => acc + r.litres, 0);
    const base = baselineLitres(zone, cfg, days);
    const sh = stressHours(db, zone.id, mn, days);
    rows.push({
      zone_id: zone.id,
      name: zone.name,
      crop: zone.crop,
      litres_used: used,
      baseline_litres: base,
      stress_hours: sh,
      days
    });
  }
  return rows;
}
