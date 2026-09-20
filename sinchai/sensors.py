import json
import math
import random
import logging

log = logging.getLogger(__name__)


class SensorReader:
    def read(self):
        raise NotImplementedError


class SimulatedSensor(SensorReader):
    def __init__(self, zones, cfg, seed=None):
        self.zones = zones
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.moisture = {}
        for z in zones:
            crop = cfg["crops"].get(z["crop"], {})
            self.moisture[z["id"]] = (crop.get("min_pct", 50) + crop.get("target_pct", 85)) / 2

    def apply_rain(self, rain_mm, zone_id, water_holding_mm):
        gain = rain_mm * 0.8 / water_holding_mm * 100.0
        self.moisture[zone_id] = min(110.0, self.moisture[zone_id] + gain)

    def tick(self, zone, crop, dt_hours, valve_open, rain_mm=0.0, weather=None, evaporation_mm_hr=None):
        wh = crop["water_holding_mm"]
        zid = zone["id"]
        m = self.moisture[zid]
        if evaporation_mm_hr is not None:
            loss = evaporation_mm_hr * crop["crop_factor"] * dt_hours / wh * 100.0
        elif weather and weather.get("hourly_evaporation_mm"):
            vals = [v for v in weather["hourly_evaporation_mm"] if v is not None]
            mean_et = sum(vals) / len(vals) if vals else 0.3
            loss = mean_et * crop["crop_factor"] * dt_hours / wh * 100.0
        else:
            loss = 0.3 * crop["crop_factor"] * dt_hours / wh * 100.0
        if valve_open:
            eff = self.cfg["efficiency"][zone["irrigation"]]
            gain = zone["flow_mm_hr"] * eff * dt_hours / wh * 100.0
        else:
            gain = 0.0
        if rain_mm > 0:
            gain += rain_mm * 0.8 / wh * 100.0
        m = m - loss + gain
        if m > 100.0:
            m = m - (m - 100.0) * 3.0 * dt_hours
        m += self.rng.gauss(0, 0.5)
        m = max(0.0, min(110.0, m))
        self.moisture[zid] = m
        return m

    def read(self):
        return dict(self.moisture)


class SerialSensor(SensorReader):
    def __init__(self, port, cfg):
        import serial
        self.cfg = cfg
        self.port = serial.Serial(port, baudrate=115200, timeout=1)
        self._latest = {}
        self._rejects = 0

    def _convert(self, raw):
        dry = self.cfg["sensor"]["dry_raw"]
        wet = self.cfg["sensor"]["wet_raw"]
        if dry == wet:
            raise ValueError("dry_raw equals wet_raw, calibration invalid")
        fl = self.cfg["sensor"]["raw_fault_low"]
        fh = self.cfg["sensor"]["raw_fault_high"]
        if raw <= fl or raw >= fh:
            raise ValueError(f"raw {raw} in fault range")
        pct = (dry - raw) / (dry - wet) * 100.0
        return max(0.0, min(110.0, pct))

    def _parse_line(self, line):
        if len(line) > 256:
            raise ValueError("line too long")
        data = json.loads(line)
        zone_id = data["zone"]
        raw = data["raw"]
        if not isinstance(zone_id, int) or not isinstance(raw, int):
            raise TypeError("zone and raw must be integers")
        if not 0 <= raw <= 4095:
            raise ValueError(f"raw out of range: {raw}")
        return zone_id, raw, self._convert(raw)

    def read(self):
        line = self.port.readline().decode(errors="replace").strip()
        if not line:
            return {}
        try:
            zone_id, raw, pct = self._parse_line(line)
            self._latest[zone_id] = (raw, pct)
            return dict(self._latest)
        except Exception as e:
            self._rejects += 1
            log.warning("serial reject #%d: %s", self._rejects, e)
            return dict(self._latest)
