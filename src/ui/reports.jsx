import React from "react";
import { Box, Text } from "ink";

export function ReportsView({ state }) {
  const { reportsList } = state;
  return (
    <Box flexDirection="column" paddingX={1} marginY={1}>
      <Text color="gray">Baseline: 30 min irrigation per day per zone at zone flow rate (assumed, not measured).</Text>
      <Box flexDirection="column" marginTop={1}>
        {reportsList.map((r, i) => (
          <Text key={r.zone_id || i}>
            {r.name} ({r.crop}): {Math.round(r.litres_used).toLocaleString()} L used / {Math.round(r.baseline_litres).toLocaleString()} L baseline | stress: {r.stress_hours.toFixed(1)} h below min
          </Text>
        ))}
        {reportsList.length === 0 && <Text color="gray">No reports available.</Text>}
      </Box>
    </Box>
  );
}
