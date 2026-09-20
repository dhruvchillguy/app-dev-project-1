export function rawToMoisture(raw, dryRaw, wetRaw, lowFault = 50, highFault = 4045) {
  if (dryRaw === wetRaw) throw new Error("dry_raw equals wet_raw, calibration invalid");
  if (raw < lowFault || raw > highFault) throw new Error(`raw ${raw} in fault range`);
  const pct = (dryRaw - raw) / (dryRaw - wetRaw) * 100.0;
  return Math.max(0.0, Math.min(100.0, pct));
}

export function parseSerialLine(line) {
  if (line.length > 256) throw new Error("line too long");
  const data = JSON.parse(line.trim());
  if (typeof data.zone_id !== "number" || typeof data.raw !== "number") {
    throw new Error("malformed reading line");
  }
  const raw = Math.round(data.raw);
  if (raw < 0 || raw > 4095) throw new Error(`raw out of range: ${raw}`);
  return { zone_id: data.zone_id, raw };
}

function createRng(seed = 42) {
  let s = seed;
  function next() {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  }
  return {
    gauss(mean = 0, std = 1) {
      const u1 = Math.max(1e-15, next());
      const u2 = next();
      const z = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
      return mean + z * std;
    }
  };
}

export class SimulatedSensor {
  constructor(zones, cfg, seed = 42) {
    this.cfg = cfg;
    this.rng = createRng(seed);
    this.moisture = {};
    for (const z of zones) {
      const crop = cfg.crops[z.crop] || {};
      this.moisture[z.id] = ((crop.min_pct || 50) + (crop.target_pct || 85)) / 2;
    }
  }

  tick(zone, crop, dtHours, valveOpen, rainMm = 0.0, weather = null, evaporationMmHr = null) {
    const wh = crop.water_holding_mm;
    const zid = zone.id;
    let m = this.moisture[zid];
    let loss = 0.3 * crop.crop_factor * dtHours / wh * 100.0;
    if (evaporationMmHr !== null) {
      loss = evaporationMmHr * crop.crop_factor * dtHours / wh * 100.0;
    } else if (weather && weather.hourly_evaporation_mm) {
      const vals = weather.hourly_evaporation_mm.filter(v => v !== null && v !== undefined);
      const meanEt = vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : 0.3;
      loss = meanEt * crop.crop_factor * dtHours / wh * 100.0;
    }
    const gain = valveOpen ? zone.flow_mm_hr * this.cfg.efficiency[zone.irrigation] * dtHours / wh * 100.0 : 0.0;
    const rainGain = rainMm > 0 ? rainMm * 0.8 / wh * 100.0 : 0.0;
    m = m - loss + gain + rainGain;
    if (m > 100.0) m = m - (m - 100.0) * 3.0 * dtHours;
    m += this.rng.gauss(0, 0.5);
    m = Math.max(0.0, Math.min(110.0, m));
    this.moisture[zid] = m;
    return m;
  }
}
