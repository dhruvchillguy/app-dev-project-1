import React from "react";
import { Box, Text } from "ink";
import { renderSparkline } from "./ascii.js";

export function ZoneView({ state }) {
  const { zones, selectedZoneId, recs, readingsMap, cfg } = state;
  const zone = zones.find(z => z.id === selectedZoneId) || zones[0];
  if (!zone) return <Text>No zone selected</Text>;
  const rec = recs[zone.id] || {};
  const crop = cfg?.crops[zone.crop] || {};
  const mn = zone.min_pct ?? crop.min_pct ?? 45;
  const tg = zone.target_pct ?? crop.target_pct ?? 85;
  const crit = mn - (cfg?.engine?.critical_margin_pts ?? 15);
  const readings = readingsMap[zone.id] || [];
  const sparkline = renderSparkline(readings, 40);

  return (
    <Box flexDirection="column" paddingX={1} marginY={1}>
      <Text bold color="cyan">Zone {zone.id}: {zone.name} ({zone.crop})</Text>
      <Text>Area: {zone.area_m2} m2 | Method: {zone.irrigation} | Flow: {zone.flow_mm_hr} mm/hr</Text>
      <Text>Thresholds: Min {mn}% | Target {tg}% | Critical {crit.toFixed(1)}%</Text>
      <Text>Valve: {zone.valve_open ? "OPEN" : "CLOSED"}</Text>
      <Box marginY={1} flexDirection="column">
        <Text bold>Moisture History (recent readings):</Text>
        <Text color="yellow">{sparkline}</Text>
      </Box>
      <Box flexDirection="column">
        <Text bold>Engine Recommendation:</Text>
        <Text color="green">Action: {rec.action || "OK"} ({rec.reason || "no reason"})</Text>
        <Text color="gray">Trace: {(rec.trace || []).join(" -> ")}</Text>
      </Box>
    </Box>
  );
}
