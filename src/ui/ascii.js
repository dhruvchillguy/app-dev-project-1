export function renderProgressBar(moisture, minPct) {
  const totalBars = 10;
  const pct = Math.max(0, Math.min(100, moisture));
  const filled = Math.round((pct / 100) * totalBars);
  const empty = totalBars - filled;
  const bar = "█".repeat(filled) + "░".repeat(empty);
  let status = "OK";
  if (moisture < minPct) status = "LOW";
  else if (moisture >= 90) status = "WET";
  return `[${bar}] ${status}`;
}

export function renderSparkline(readings, width = 30) {
  if (!readings || readings.length === 0) return "no history";
  const pts = readings.slice(0, width).map(r => r.moisture_pct).reverse();
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = max - min || 1;
  const chars = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"];
  return pts.map(p => {
    const idx = Math.min(chars.length - 1, Math.floor(((p - min) / range) * chars.length));
    return chars[idx];
  }).join("");
}
