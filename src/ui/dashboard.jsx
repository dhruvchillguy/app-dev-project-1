import React from "react";
import { Box, Text } from "ink";
import { renderProgressBar } from "./ascii.js";

export function Dashboard({ state }) {
  const { source, mode, clockNow, openValvesCount, weather, zones, recs, alerts } = state;
  const weatherStatus = weather?.source ? weather.source.toUpperCase() : "OFFLINE";
  const weatherText = weather
    ? `Weather | Temp: ${weather.temperature_c?.toFixed(1)}°C | Wind: ${weather.wind_kmh?.toFixed(1)} km/h | Rain next 12h: ${weather.hourly_precip_mm?.slice(0, 12).reduce((a, b) => a + (b || 0), 0).toFixed(1)}mm (${Math.max(...(weather.hourly_precip_prob?.slice(0, 12) || [0]))}%) | Evap: ${weather.hourly_evaporation_mm?.slice(0, 12).reduce((a, b) => a + (b || 0), 0).toFixed(1)}mm`
    : "Weather | OFFLINE";

  return (
    <Box flexDirection="column">
      <Box paddingX={1} backgroundColor="blue">
        <Text color="white">
          {source.toUpperCase()} | weather {weatherStatus} | mode {mode.toUpperCase()} | {clockNow ? clockNow.replace("T", " ").slice(0, 19) : ""} | {openValvesCount} open
        </Text>
      </Box>
      {source === "sim" && (
        <Box paddingX={1} backgroundColor="yellow" justifyContent="center">
          <Text color="black" bold>[SIMULATED DATA]</Text>
        </Box>
      )}
      <Box flexDirection="column" marginY={1} paddingX={1}>
        <Box>
          <Text bold color="cyan">
            {"Zone".padEnd(8)} {"Crop".padEnd(10)} {"Moist".padEnd(8)} {"Status Bar".padEnd(18)} {"Recommendation".padEnd(35)} {"Valve".padEnd(10)} {"Next Due"}
          </Text>
        </Box>
        {zones.map(z => {
          const rec = recs[z.id] || {};
          const m = z.moisture !== undefined && z.moisture !== null ? `${Math.round(z.moisture)}%` : "no data";
          const bar = z.moisture !== undefined && z.moisture !== null ? renderProgressBar(z.moisture, z.min_pct ?? 50) : "[░░░░░░░░░░] OK";
          const recStr = rec.action ? `${rec.action} (${rec.reason || ""})`.slice(0, 34) : "OK";
          const vStr = z.valve_open ? "OPEN" : "CLOSED";
          const dueStr = rec.hours_until !== undefined && rec.hours_until !== null ? `${rec.hours_until.toFixed(1)}h` : "unknown";
          return (
            <Box key={z.id}>
              <Text>
                {z.name.padEnd(8)} {z.crop.padEnd(10)} {m.padEnd(8)} {bar.padEnd(18)} {recStr.padEnd(35)} {vStr.padEnd(10)} {dueStr}
              </Text>
            </Box>
          );
        })}
      </Box>
      <Box paddingX={1}>
        <Text color="green">{weatherText}</Text>
      </Box>
      <Box flexDirection="column" marginTop={1} paddingX={1}>
        <Text bold color="magenta">Alerts Feed:</Text>
        {alerts.slice(0, 8).map((a, i) => {
          const time = a.ts.slice(11, 19);
          const zName = a.zone_id ? `Zone ${a.zone_id}` : "Farm";
          return (
            <Text key={a.id || i}>
              {"  "}[{time}] {zName} | {a.severity.toUpperCase()} | {a.message}
            </Text>
          );
        })}
        {alerts.length === 0 && <Text color="gray">{"  "}No active alerts.</Text>}
      </Box>
    </Box>
  );
}
