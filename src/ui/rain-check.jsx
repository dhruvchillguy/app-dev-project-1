import React from "react";
import { Box, Text } from "ink";

export function RainCheckView({ state }) {
  const { ledgerSummaryText, skipsList } = state;
  return (
    <Box flexDirection="column" paddingX={1} marginY={1}>
      <Text color="gray">Actual rain comes from a weather model, not a rain gauge.</Text>
      <Text bold color="cyan">{ledgerSummaryText}</Text>
      <Box flexDirection="column" marginTop={1}>
        {skipsList.map(s => {
          const act = s.actual_mm !== null && s.actual_mm !== undefined ? `${s.actual_mm.toFixed(1)}mm` : "pending";
          const low = s.min_moisture !== null && s.min_moisture !== undefined ? `${s.min_moisture.toFixed(1)}%` : "n/a";
          return (
            <Text key={s.id}>
              {s.decided_at.slice(0, 16)} | Zone {s.zone_id} ({s.crop || ""}) | Forecast: {s.forecast_mm.toFixed(1)}mm | Actual: {act} | Verdict: {s.verdict || "PENDING"} | Lowest: {low}
            </Text>
          );
        })}
        {skipsList.length === 0 && <Text color="gray">No rain skips recorded yet.</Text>}
      </Box>
    </Box>
  );
}
