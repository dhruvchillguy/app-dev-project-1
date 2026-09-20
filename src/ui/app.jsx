import React, { useState, useEffect, useRef } from "react";
import { Box, Text, useInput, useApp } from "ink";
import { Dashboard } from "./dashboard.jsx";
import { ZoneView } from "./zone-view.jsx";
import { ReportsView } from "./reports.jsx";
import { RainCheckView } from "./rain-check.jsx";
import { getZones, getRecentReadings, getActiveAlerts } from "../db.js";
import { decide } from "../engine.js";
import { openValve, closeValve } from "../valves.js";
import { ledgerSummary } from "../ledger.js";
import { zoneReport } from "../reports.js";
import { tick } from "../farm.js";
import { now, toIso } from "../clock.js";
import { getDemoWeatherObject } from "../demo.js";

export function App({ db, cfg, demo, scenario, sensor, source: initialSource, mode: initialMode }) {
  const { exit } = useApp();
  const [activeTab, setActiveTab] = useState("dashboard");
  const [source] = useState(initialSource || "sim");
  const [mode, setMode] = useState(initialMode || "auto");
  const [selectedZoneId, setSelectedZoneId] = useState(1);
  const [state, setState] = useState({
    source: initialSource || "sim", mode: initialMode || "auto",
    clockNow: toIso(now()), openValvesCount: 0, weather: null,
    zones: [], recs: {}, alerts: [], selectedZoneId: 1,
    readingsMap: {}, cfg, reportsList: [], ledgerSummaryText: "", skipsList: []
  });
  const lastValvePress = useRef(0);

  function refresh() {
    const currentZones = getZones(db);
    const readingsMap = {};
    const recs = {};
    const currentWeather = demo && scenario ? getDemoWeatherObject(scenario, now()) : null;
    for (const z of currentZones) {
      const readings = getRecentReadings(db, z.id, 48);
      readingsMap[z.id] = readings;
      z.moisture = readings[0]?.moisture_pct ?? null;
      recs[z.id] = decide(z, cfg.crops[z.crop], readings, currentWeather, toIso(now()), 330, cfg);
    }
    const openValvesCount = currentZones.filter(z => z.valve_open === 1).length;
    const alerts = getActiveAlerts(db);
    const reportsList = zoneReport(db, currentZones, cfg, 7);
    const ledgerSummaryText = ledgerSummary(db);
    const skipsList = db.prepare("SELECT s.*, z.crop FROM skips s JOIN zones z ON s.zone_id = z.id ORDER BY s.decided_at DESC LIMIT 20").all();
    setState(prev => ({
      ...prev, mode, clockNow: toIso(now()), openValvesCount, weather: currentWeather,
      zones: currentZones, recs, alerts, selectedZoneId, readingsMap,
      reportsList, ledgerSummaryText, skipsList
    }));
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(() => {
      const w = demo && scenario ? getDemoWeatherObject(scenario, now()) : null;
      tick(db, getZones(db), sensor, w, mode, demo, scenario, cfg);
      refresh();
    }, demo ? 50 : 1000);
    return () => clearInterval(interval);
  }, [mode, selectedZoneId]);

  useInput((input, key) => {
    if (input === "q") exit();
    else if (input === "d") setActiveTab("dashboard");
    else if (input === "z") setActiveTab("zones");
    else if (input === "r") setActiveTab("reports");
    else if (input === "l") setActiveTab("raincheck");
    else if (input === "m") setMode(m => m === "auto" ? "manual" : "auto");
    else if (input === "1" || input === "2" || input === "3") setSelectedZoneId(Number(input));
    else if (input === "a") {
      db.prepare("UPDATE alerts SET acknowledged = 1 WHERE cleared_ts IS NULL").run();
      refresh();
    } else if (input === "v") {
      const nowMs = Date.now();
      if (nowMs - lastValvePress.current < 1000) return;
      lastValvePress.current = nowMs;
      const zone = getZones(db).find(z => z.id === selectedZoneId);
      if (zone) {
        if (zone.valve_open) closeValve(db, zone, "manual");
        else openValve(db, zone, "manual", 30, cfg);
        refresh();
      }
    }
  });

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="cyan">
      <Box paddingX={1} justifyContent="space-between">
        <Text bold color="green">Sinchai</Text>
        <Text color="gray">[{activeTab.toUpperCase()}]</Text>
      </Box>
      <Box paddingX={1} gap={2}>
        <Text bold={activeTab === "dashboard"} color={activeTab === "dashboard" ? "cyan" : "gray"}>[d] Dashboard</Text>
        <Text bold={activeTab === "zones"} color={activeTab === "zones" ? "cyan" : "gray"}>[z] Zones</Text>
        <Text bold={activeTab === "reports"} color={activeTab === "reports" ? "cyan" : "gray"}>[r] Reports</Text>
        <Text bold={activeTab === "raincheck"} color={activeTab === "raincheck" ? "cyan" : "gray"}>[l] Rain-check</Text>
      </Box>
      {activeTab === "dashboard" && <Dashboard state={state} />}
      {activeTab === "zones" && <ZoneView state={state} />}
      {activeTab === "reports" && <ReportsView state={state} />}
      {activeTab === "raincheck" && <RainCheckView state={state} />}
      <Box paddingX={1} borderStyle="single" borderColor="gray" justifyContent="space-between">
        <Text color="yellow">Keys: [d/z/r/l] Tabs | [1-3] Zone | [v] Valve | [m] Mode | [a] Ack Alerts | [q] Quit</Text>
      </Box>
    </Box>
  );
}
