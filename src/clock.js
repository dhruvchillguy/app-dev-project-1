let demoStartReal = null;
let demoStartSim = null;
let speed = 1.0;

export function configureDemo(startSim, spd) {
  demoStartReal = new Date();
  demoStartSim = startSim;
  speed = spd;
}

export function reset() {
  demoStartReal = null;
  demoStartSim = null;
  speed = 1.0;
}

export function now() {
  if (!demoStartReal) {
    return new Date();
  }
  const elapsedMs = (new Date() - demoStartReal) * speed;
  return new Date(demoStartSim.getTime() + elapsedMs);
}

export function toIso(d) {
  return d.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function fromIso(s) {
  return new Date(s);
}

export function localMinutes(d, utcOffsetMinutes) {
  const utcMinutes = d.getUTCHours() * 60 + d.getUTCMinutes();
  const total = (utcMinutes + utcOffsetMinutes + 1440) % 1440;
  return total;
}
