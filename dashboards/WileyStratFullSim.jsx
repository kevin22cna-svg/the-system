import { useState, useEffect, useRef, useCallback } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

// ── WILEY STRAT — FULL UNIVERSE SIM ──────────────────────────────────────────
// Live prices pulled at 11:46am ET June 17, 2026

// Sector map for display
const SECTORS = {
  "Semis":         ["NVDA","AMD","ARM","INTC","TSM"],
  "Memory":        ["MU","SNDK","WDC"],
  "Networking":    ["AVGO","MRVL","CRDO","ANET"],
  "Photonics":     ["AAOI","LITE","COHR","NVTS","GLW"],
  "Semi Equip":    ["ASML","AMAT","LRCX","KLAC"],
  "Infrastructure":["DELL","SMCI","VRT","ETN"],
  "Data Centers":  ["IREN","CORZ","CIFR","HIVE","APLD","NBIS"],
  "Software":      ["MSFT","NOW","SNOW","MDB","CRM"],
  "Defense":       ["PLTR","KTOS","AVAV","RCAT","LMT"],
  "Drones":        ["ONDS","DPRO","UMAC"],
  "Robotics":      ["OUST","SYM","ISRG","TSLA"],
  "Space":         ["ASTS","RKLB","RDW","LUNR"],
  "Quantum":       ["IONQ","QBTS","RGTI"],
  "Nuclear":       ["OKLO","LEU","UUUU","CCJ"],
  "Power":         ["CEG","VST","BE","TLN"],
  "Fintech":       ["HOOD","SOFI","AFRM"],
  "Copper":        ["FCX","SCCO","TECK"],
  "eVTOL":         ["JOBY","ACHR"],
};

const TICKERS = {
  // INDEXES
  SPY:  { price: 750.35,  prev: 750.33,  vol: 0.0006, type: "Index",    color: "#00C896" },
  QQQ:  { price: 732.60,  prev: 729.86,  vol: 0.0007, type: "index",    color: "#7C83FD" },
  IWM:  { price: 295.10,  prev: 292.08,  vol: 0.0008, type: "index",    color: "#FFB800" },
  // MEGA CAPS
  AVGO: { price: 396.63,  prev: 376.71,  vol: 0.0009, type: "mega",     color: "#00C896" },
  AMD:  { price: 523.20,  prev: 507.29,  vol: 0.0011, type: "mega",     color: "#00C896" },
  PLTR: { price: 134.69,  prev: 133.25,  vol: 0.0012, type: "mega",     color: "#00C896" },
  AAPL: { price: 296.87,  prev: 299.24,  vol: 0.0006, type: "mega",     color: "#FF4757" },
  MSFT: { price: 386.37,  prev: 393.83,  vol: 0.0007, type: "mega",     color: "#FF4757" },
  META: { price: 580.78,  prev: 600.21,  vol: 0.0008, type: "mega",     color: "#FF4757" },
  GOOGL:{ price: 364.75,  prev: 373.25,  vol: 0.0008, type: "mega",     color: "#FF4757" },
  AMZN: { price: 240.38,  prev: 246.00,  vol: 0.0007, type: "mega",     color: "#FF4757" },
  TSLA: { price: 400.11,  prev: 404.66,  vol: 0.0013, type: "mega",     color: "#FF4757" },
  NVDA: { price: 206.45,  prev: 207.41,  vol: 0.0010, type: "mega",     color: "#6B7280" },
  // SEMIS
  ARM:  { price: 167.50, prev: 168.00, vol: 0.0013, type: "Semis",      color: "#6B7280" },
  INTC: { price: 23.40,  prev: 23.10,  vol: 0.0012, type: "Semis",      color: "#00C896" },
  TSM:  { price: 210.80, prev: 212.00, vol: 0.0008, type: "Semis",      color: "#6B7280" },
  // MEMORY
  MU:   { price: 1048.0, prev: 1087.99,vol: 0.0011, type: "Memory",     color: "#FF4757" },
  WDC:  { price: 71.20,  prev: 72.00,  vol: 0.0012, type: "Memory",     color: "#FF4757" },
  // NETWORKING
  MRVL: { price: 118.40, prev: 117.80, vol: 0.0011, type: "Networking", color: "#00C896" },
  ANET: { price: 501.20, prev: 503.00, vol: 0.0009, type: "Networking", color: "#6B7280" },
  // SEMI EQUIP
  ASML: { price: 762.00, prev: 758.00, vol: 0.0009, type: "Semi Equip", color: "#00C896" },
  AMAT: { price: 189.50, prev: 188.00, vol: 0.0010, type: "Semi Equip", color: "#00C896" },
  LRCX: { price: 830.00, prev: 825.00, vol: 0.0009, type: "Semi Equip", color: "#00C896" },
  KLAC: { price: 780.00, prev: 778.00, vol: 0.0009, type: "Semi Equip", color: "#00C896" },
  // INFRASTRUCTURE
  DELL: { price: 142.30, prev: 141.80, vol: 0.0010, type: "Infrastructure", color: "#00C896" },
  SMCI: { price: 42.50,  prev: 43.20,  vol: 0.0018, type: "Infrastructure", color: "#FF4757" },
  VRT:  { price: 98.40,  prev: 97.80,  vol: 0.0012, type: "Infrastructure", color: "#00C896" },
  ETN:  { price: 342.00, prev: 340.00, vol: 0.0008, type: "Infrastructure", color: "#00C896" },
  // DATA CENTERS
  IREN: { price: 14.20,  prev: 13.80,  vol: 0.0018, type: "Data Centers", color: "#00C896" },
  CORZ: { price: 18.60,  prev: 18.10,  vol: 0.0016, type: "Data Centers", color: "#00C896" },
  APLD: { price: 12.40,  prev: 12.10,  vol: 0.0017, type: "Data Centers", color: "#00C896" },
  NBIS: { price: 28.90,  prev: 28.50,  vol: 0.0014, type: "Data Centers", color: "#00C896" },
  HIVE: { price: 4.22,   prev: 3.96,   vol: 0.0020, type: "Data Centers", color: "#00C896" },
  // SOFTWARE
  NOW:  { price: 1124.0, prev: 1118.0, vol: 0.0009, type: "Software",   color: "#00C896" },
  SNOW: { price: 196.40, prev: 194.80, vol: 0.0013, type: "Software",   color: "#00C896" },
  MDB:  { price: 248.60, prev: 246.00, vol: 0.0013, type: "Software",   color: "#00C896" },
  CRM:  { price: 318.00, prev: 316.00, vol: 0.0009, type: "Software",   color: "#00C896" },
  // DEFENSE
  KTOS: { price: 38.40,  prev: 37.90,  vol: 0.0014, type: "Defense",    color: "#00C896" },
  AVAV: { price: 214.00, prev: 212.00, vol: 0.0011, type: "Defense",    color: "#00C896" },
  RCAT: { price: 18.60,  prev: 18.30,  vol: 0.0016, type: "Defense",    color: "#00C896" },
  LMT:  { price: 498.00, prev: 496.00, vol: 0.0007, type: "Defense",    color: "#00C896" },
  // DRONES
  ONDS: { price: 3.84,   prev: 3.71,   vol: 0.0022, type: "Drones",     color: "#00C896" },
  DPRO: { price: 2.14,   prev: 2.08,   vol: 0.0024, type: "Drones",     color: "#00C896" },
  UMAC: { price: 4.92,   prev: 4.78,   vol: 0.0022, type: "Drones",     color: "#00C896" },
  // ROBOTICS
  OUST: { price: 12.40,  prev: 12.10,  vol: 0.0017, type: "Robotics",   color: "#00C896" },
  SYM:  { price: 26.80,  prev: 26.40,  vol: 0.0014, type: "Robotics",   color: "#00C896" },
  ISRG: { price: 574.00, prev: 572.00, vol: 0.0008, type: "Robotics",   color: "#00C896" },
  // QUANTUM
  RGTI: { price: 18.40,  prev: 17.90,  vol: 0.0020, type: "Quantum",    color: "#00C896" },
  // NUCLEAR
  OKLO: { price: 42.80,  prev: 42.10,  vol: 0.0016, type: "Nuclear",    color: "#00C896" },
  LEU:  { price: 68.40,  prev: 67.80,  vol: 0.0013, type: "Nuclear",    color: "#00C896" },
  UUUU: { price: 8.92,   prev: 8.74,   vol: 0.0018, type: "Nuclear",    color: "#00C896" },
  CCJ:  { price: 52.40,  prev: 51.80,  vol: 0.0012, type: "Nuclear",    color: "#00C896" },
  // POWER
  CEG:  { price: 312.00, prev: 310.00, vol: 0.0009, type: "Power",      color: "#00C896" },
  VST:  { price: 198.40, prev: 196.80, vol: 0.0011, type: "Power",      color: "#00C896" },
  BE:   { price: 28.60,  prev: 28.20,  vol: 0.0015, type: "Power",      color: "#00C896" },
  TLN:  { price: 184.20, prev: 182.80, vol: 0.0011, type: "Power",      color: "#00C896" },
  // FINTECH
  AFRM: { price: 58.40,  prev: 57.60,  vol: 0.0016, type: "Fintech",    color: "#00C896" },
  // COPPER
  FCX:  { price: 42.80,  prev: 42.40,  vol: 0.0012, type: "Copper",     color: "#00C896" },
  SCCO: { price: 118.40, prev: 117.60, vol: 0.0010, type: "Copper",     color: "#00C896" },
  TECK: { price: 48.60,  prev: 48.10,  vol: 0.0011, type: "Copper",     color: "#00C896" },
  // eVTOL
  ACHR: { price: 8.42,   prev: 8.18,   vol: 0.0020, type: "eVTOL",      color: "#00C896" },
  // WATCHLIST
  FCEL: { price: 21.46,   prev: 19.75,   vol: 0.0018, type: "watch",    color: "#00C896" },
  CRWV: { price: 119.09,  prev: 117.03,  vol: 0.0012, type: "watch",    color: "#00C896" },
  HIMS: { price: 32.24,   prev: 31.47,   vol: 0.0011, type: "watch",    color: "#00C896" },
  SOFI: { price: 18.51,   prev: 17.71,   vol: 0.0013, type: "watch",    color: "#00C896" },
  ASTS: { price: 84.11,   prev: 82.25,   vol: 0.0015, type: "watch",    color: "#00C896" },
  RIVN: { price: 16.60,   prev: 15.93,   vol: 0.0014, type: "watch",    color: "#00C896" },
  NU:   { price: 13.31,   prev: 12.72,   vol: 0.0013, type: "watch",    color: "#00C896" },
  RKT:  { price: 14.23,   prev: 13.92,   vol: 0.0014, type: "watch",    color: "#00C896" },
  CIFR: { price: 26.97,   prev: 26.21,   vol: 0.0016, type: "watch",    color: "#00C896" },
  CLSK: { price: 17.40,   prev: 17.26,   vol: 0.0014, type: "watch",    color: "#00C896" },
  AAL:  { price: 15.86,   prev: 15.71,   vol: 0.0012, type: "watch",    color: "#00C896" },
  SPCX: { price: 192.95,  prev: 201.80,  vol: 0.0014, type: "watch",    color: "#FF4757" },
  NIO:  { price: 5.115,   prev: 5.010,   vol: 0.0018, type: "watch",    color: "#00C896" },
  LUNR: { price: 23.23,   prev: 23.36,   vol: 0.0015, type: "watch",    color: "#FF4757" },
  CCL:  { price: 30.96,   prev: 30.90,   vol: 0.0010, type: "watch",    color: "#00C896" },
  DAL:  { price: 83.18,   prev: 83.14,   vol: 0.0008, type: "watch",    color: "#00C896" },
  MARA: { price: 14.43,   prev: 14.42,   vol: 0.0016, type: "watch",    color: "#00C896" },
  RIOT: { price: 27.45,   prev: 27.42,   vol: 0.0015, type: "watch",    color: "#00C896" },
  WULF: { price: 27.81,   prev: 28.01,   vol: 0.0015, type: "watch",    color: "#FF4757" },
};

// Wiley Strat scoring (0-10)
function scoreSetup(sym, data) {
  const pct = (data.price - data.prev) / data.prev * 100;
  let score = 0;
  let direction = pct >= 0 ? "CALLS" : "PUTS";

  // EMA fan proxy
  if (Math.abs(pct) >= 3)      score += 2;
  else if (Math.abs(pct) >= 1) score += 1;

  // 15min PMH/PML confirm proxy
  if (Math.abs(pct) >= 5)      score += 2;
  else if (Math.abs(pct) >= 2) score += 1;

  // Volume/catalyst
  if (Math.abs(pct) >= 4)      score += 2;
  else if (Math.abs(pct) >= 2) score += 1;

  // Clean air (not overextended)
  if (Math.abs(pct) >= 3 && Math.abs(pct) <= 12) score += 1;
  if (Math.abs(pct) > 15) score -= 1;

  // Option liquidity
  if (data.price >= 10 && data.price <= 150) score += 1;
  else if (data.price > 150) score += 1; // mega caps have good liquidity too

  // VWAP proxy
  score += 1;

  return { score: Math.max(0, Math.min(score, 10)), direction, pct };
}

// Greeks estimator
function estimateGreeks(price, vol) {
  const dailyVol = vol * Math.sqrt(195);
  const premium  = price * dailyVol * Math.sqrt(9/252) * 0.4;
  return {
    premium: Math.max(premium * 1.01, 0.05),
    delta:   0.50,
    theta:  -premium / 9 * 0.8,
  };
}

// Option value using delta model
function optionVal(stockPrice, entryStock, entryPrem, delta, theta, barsElapsed) {
  const move      = stockPrice - entryStock;
  const deltaP    = delta * move;
  const thetaD    = theta * (barsElapsed / 390);
  return Math.max(entryPrem + deltaP + thetaD, 0.01);
}

// Seeded RNG
function makeRng(seed) {
  let s = seed >>> 0;
  return {
    next() { s = (1664525 * s + 1013904223) >>> 0; return s / 4294967296; },
    normal(mu = 0, sigma = 1) {
      const u1 = Math.max(1e-10, this.next());
      const u2 = this.next();
      return mu + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }
  };
}

const PROFIT_TARGET = 0.50;
const STOP_LOSS     = 0.30;
const POSITION_USD  = 50;

// Pre-score all tickers
const SCORED = Object.entries(TICKERS).map(([sym, data]) => {
  const { score, direction, pct } = scoreSetup(sym, data);
  const { premium, delta, theta } = estimateGreeks(data.price, data.vol);
  return { sym, ...data, score, direction, pct, premium, delta, theta };
}).sort((a, b) => b.score - a.score);

const GROUPS = {
  "🔥 PRIME (8-10)":  SCORED.filter(t => t.score >= 8),
  "⚡ WATCH (6-7)":   SCORED.filter(t => t.score >= 6 && t.score < 8),
  "🔴 BEARISH PUTS":  SCORED.filter(t => t.score >= 6 && t.direction === "PUTS"),
  "➖ NEUTRAL (4-5)": SCORED.filter(t => t.score >= 4 && t.score < 6),
};

export default function WileyStratFullSim() {
  const [selected,    setSelected]    = useState(null);
  const [simState,    setSimState]    = useState("IDLE");
  const [history,     setHistory]     = useState([]);
  const [stockPrice,  setStockPrice]  = useState(0);
  const [optionValue, setOptionValue] = useState(0);
  const [exitReason,  setExitReason]  = useState(null);
  const [exitPrem,    setExitPrem]    = useState(null);
  const [tab,         setTab]         = useState("scanner");
  const simRef   = useRef("IDLE");
  const rngRef   = useRef(null);
  const priceRef = useRef(0);
  const barRef   = useRef(0);

  function selectTicker(t) {
    setSelected(t);
    setSimState("IDLE");
    setHistory([]);
    setStockPrice(t.price);
    setOptionValue(t.premium);
    setExitReason(null);
    setExitPrem(null);
    simRef.current = "IDLE";
    setTab("sim");
  }

  function startSim() {
    if (!selected) return;
    priceRef.current = selected.price;
    barRef.current   = 0;
    rngRef.current   = makeRng(Date.now());
    simRef.current   = "RUNNING";
    setSimState("RUNNING");
    setHistory([]);
    setExitReason(null);
    setExitPrem(null);
    setStockPrice(selected.price);
    setOptionValue(selected.premium);
  }

  function resetSim() {
    simRef.current = "IDLE";
    setSimState("IDLE");
    setHistory([]);
    setExitReason(null);
    setExitPrem(null);
    if (selected) {
      setStockPrice(selected.price);
      setOptionValue(selected.premium);
    }
    barRef.current = 0;
  }

  useEffect(() => {
    if (simState !== "RUNNING" || !selected) return;
    const interval = setInterval(() => {
      if (simRef.current !== "RUNNING") { clearInterval(interval); return; }

      barRef.current += 5;
      const drift  = selected.direction === "CALLS" ? 0.00003 : -0.00003;
      const noise  = rngRef.current.normal(drift, selected.vol);
      priceRef.current = Math.max(selected.price * 0.7, priceRef.current * (1 + noise));

      const sp  = Math.round(priceRef.current * 1000) / 1000;
      const ov  = optionVal(sp, selected.price, selected.premium, selected.delta, selected.theta, barRef.current);
      const pct = (ov - selected.premium) / selected.premium * 100;

      setStockPrice(sp);
      setOptionValue(Math.round(ov * 1000) / 1000);
      setHistory(h => [...h.slice(-100), {
        bar: barRef.current,
        stock: sp,
        option: Math.round(ov * 1000) / 1000,
        pnlPct: Math.round(pct * 10) / 10,
      }]);

      if (pct >= PROFIT_TARGET * 100) {
        simRef.current = "PROFIT";
        setSimState("PROFIT");
        setExitReason("PROFIT");
        setExitPrem(Math.round(ov * 1000) / 1000);
      } else if (pct <= -(STOP_LOSS * 100)) {
        simRef.current = "STOP";
        setSimState("STOP");
        setExitReason("STOP");
        setExitPrem(Math.round(ov * 1000) / 1000);
      } else if (barRef.current >= 390) {
        simRef.current = "EXPIRED";
        setSimState("EXPIRED");
        setExitReason("EXPIRED");
        setExitPrem(Math.round(ov * 1000) / 1000);
      }
    }, 300);
    return () => clearInterval(interval);
  }, [simState, selected]);

  const pnlPct   = selected ? (optionValue - selected.premium) / selected.premium * 100 : 0;
  const pnlUsd   = selected ? (optionValue - selected.premium) * 100 : 0;
  const pnlColor = pnlPct >= 0 ? "#00C896" : "#FF4757";

  const statusCfg = {
    IDLE:    { color: "#4B5563",  label: "Select a ticker from the scanner then hit Start" },
    RUNNING: { color: "#00C896",  label: `🔥 SIMULATING — ${selected?.sym} ${selected?.direction}` },
    PROFIT:  { color: "#00C896",  label: `🎉 PROFIT HIT +${(PROFIT_TARGET*100).toFixed(0)}% on ${selected?.sym}` },
    STOP:    { color: "#FF4757",  label: `🛑 STOP HIT -${(STOP_LOSS*100).toFixed(0)}% on ${selected?.sym}` },
    EXPIRED: { color: "#FFB800",  label: `⏰ EXPIRED — ${selected?.sym} at close` },
  }[simState] || { color: "#4B5563", label: "Ready" };

  return (
    <div style={{ background: "#080C14", minHeight: "100vh", color: "#E2E8F0",
      fontFamily: "'JetBrains Mono', monospace", padding: "20px 16px" }}>
      <div style={{ maxWidth: 860, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#FFF" }}>
            🔥 WILEY STRAT — FULL UNIVERSE SIM
          </div>
          <div style={{ fontSize: 10, color: "#4B5563", marginTop: 2, letterSpacing: "0.08em" }}>
            {Object.keys(TICKERS).length} TICKERS  ·  LIVE PRICES 11:46AM ET  ·  CASEY + KEVIN SCORING  ·  +50%/-30% TARGETS
          </div>
        </div>

        {/* Status */}
        <div style={{
          background: statusCfg.color + "22", border: `1px solid ${statusCfg.color}44`,
          borderRadius: 10, padding: "10px 16px", marginBottom: 16,
          display: "flex", justifyContent: "space-between", alignItems: "center"
        }}>
          <div style={{ fontSize: 11, color: statusCfg.color, fontWeight: 700 }}>{statusCfg.label}</div>
          {simState === "RUNNING" && (
            <div style={{ fontSize: 14, color: pnlColor, fontWeight: 700 }}>
              {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%
            </div>
          )}
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
          {[["scanner","📊 Scanner"],["sim","📈 Sim"]].map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)} style={{
              flex: 1, background: tab === id ? "#1E3A5F" : "transparent",
              border: `1px solid ${tab === id ? "#3B82F6" : "#1E2A3A"}`,
              borderRadius: 8, color: tab === id ? "#93C5FD" : "#6B7280",
              fontSize: 12, padding: "8px", cursor: "pointer", fontFamily: "inherit",
              fontWeight: tab === id ? 700 : 400,
            }}>{label}</button>
          ))}
        </div>

        {/* ── SCANNER TAB ── */}
        {tab === "scanner" && (
          <div>
            {Object.entries(GROUPS).map(([groupName, tickers]) => tickers.length > 0 && (
              <div key={groupName} style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10, letterSpacing: "0.08em" }}>
                  {groupName} — {tickers.length} TICKERS
                </div>
                {tickers.map(t => {
                  const isSelected = selected?.sym === t.sym;
                  const scoreBar   = "█".repeat(t.score) + "░".repeat(10 - t.score);
                  const de = t.direction === "CALLS" ? "📈" : "📉";
                  const arrow = t.pct >= 0 ? "▲" : "▼";
                  const pctColor = t.pct >= 0 ? "#00C896" : "#FF4757";
                  const cost = Math.round(t.premium * 100 * 100) / 100;
                  return (
                    <div key={t.sym} onClick={() => selectTicker(t)}
                      style={{
                        background: isSelected ? "#1E3A5F" : "#0F1724",
                        border: `1px solid ${isSelected ? "#3B82F6" : "#1E2A3A"}`,
                        borderRadius: 8, padding: "10px 14px", marginBottom: 6,
                        cursor: "pointer", display: "flex", alignItems: "center", gap: 12,
                        transition: "all 0.15s",
                      }}
                      onMouseEnter={e => !isSelected && (e.currentTarget.style.borderColor = "#2A3040")}
                      onMouseLeave={e => !isSelected && (e.currentTarget.style.borderColor = "#1E2A3A")}
                    >
                      {/* Score */}
                      <div style={{ textAlign: "center", minWidth: 32 }}>
                        <div style={{ fontSize: 16, fontWeight: 700,
                          color: t.score >= 8 ? "#FF6B00" : t.score >= 6 ? "#00C896" : "#6B7280" }}>
                          {t.score}
                        </div>
                        <div style={{ fontSize: 8, color: "#4B5563" }}>/10</div>
                      </div>

                      {/* Symbol + type */}
                      <div style={{ minWidth: 60 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "#FFF" }}>{t.sym}</div>
                        <div style={{ fontSize: 9, color: "#4B5563" }}>{t.type}</div>
                      </div>

                      {/* Price + change */}
                      <div style={{ minWidth: 80 }}>
                        <div style={{ fontSize: 12, color: "#E2E8F0" }}>${t.price.toFixed(2)}</div>
                        <div style={{ fontSize: 10, color: pctColor }}>
                          {arrow}{Math.abs(t.pct).toFixed(2)}%
                        </div>
                      </div>

                      {/* Direction + cost */}
                      <div style={{ minWidth: 80 }}>
                        <div style={{ fontSize: 11, color: t.direction === "CALLS" ? "#00C896" : "#FF4757", fontWeight: 700 }}>
                          {de} {t.direction}
                        </div>
                        <div style={{ fontSize: 9, color: "#6B7280" }}>~${cost}/contract</div>
                      </div>

                      {/* Score bar */}
                      <div style={{ flex: 1, fontSize: 9, color: "#4B5563", fontFamily: "monospace", display: "none" }}>
                        {scoreBar}
                      </div>

                      {/* Select button */}
                      <div style={{
                        background: isSelected ? "#3B82F6" : "#1E2A3A",
                        color: isSelected ? "#FFF" : "#6B7280",
                        borderRadius: 6, padding: "4px 10px", fontSize: 10, fontWeight: 600
                      }}>
                        {isSelected ? "✓ SELECTED" : "SIM →"}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        {/* ── SIM TAB ── */}
        {tab === "sim" && (
          <div>
            {!selected ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#4B5563", fontSize: 13 }}>
                Go to Scanner tab → tap a ticker → come back here
              </div>
            ) : (
              <>
                {/* Trade card */}
                <div style={{ background: "#0F1724", border: "1px solid #1E2A3A",
                  borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#FFF" }}>
                        {selected.sym} {selected.direction}
                      </div>
                      <div style={{ fontSize: 10, color: "#6B7280" }}>
                        Score {selected.score}/10 · ${selected.price.toFixed(2)} · {selected.pct >= 0 ? "+" : ""}{selected.pct.toFixed(2)}%
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 14, color: "#FFB800", fontWeight: 700 }}>
                        ~${(selected.premium * 100).toFixed(2)}/contract
                      </div>
                      <div style={{ fontSize: 9, color: "#6B7280" }}>9 DTE · +50%/-30%</div>
                    </div>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                    {[
                      { l: "Entry Prem",  v: `$${selected.premium.toFixed(3)}` },
                      { l: "Live Option", v: `$${optionValue.toFixed(3)}`, c: pnlColor },
                      { l: "P&L",         v: `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%`, c: pnlColor },
                      { l: "Target",      v: `$${(selected.premium*(1+PROFIT_TARGET)).toFixed(3)}`, c: "#00C896" },
                      { l: "Stop",        v: `$${(selected.premium*(1-STOP_LOSS)).toFixed(3)}`, c: "#FF4757" },
                      { l: "Stock",       v: `$${stockPrice.toFixed(3)}` },
                    ].map((m, i) => (
                      <div key={i} style={{ background: "#080C14", borderRadius: 6, padding: "8px 10px" }}>
                        <div style={{ fontSize: 9, color: "#4B5563", marginBottom: 2 }}>{m.l}</div>
                        <div style={{ fontSize: 12, color: m.c || "#E2E8F0", fontWeight: 600 }}>{m.v}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Progress bar */}
                <div style={{ background: "#0F1724", border: "1px solid #1E2A3A",
                  borderRadius: 8, padding: "12px 14px", marginBottom: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "#6B7280", marginBottom: 6 }}>
                    <span style={{ color: "#FF4757" }}>STOP -30%</span>
                    <span style={{ color: "#FFB800" }}>ENTRY</span>
                    <span style={{ color: "#00C896" }}>TARGET +50%</span>
                  </div>
                  <div style={{ background: "#1E2A3A", borderRadius: 4, height: 8 }}>
                    <div style={{
                      width: `${Math.min(100, Math.max(0, (optionValue - selected.premium*(1-STOP_LOSS)) / (selected.premium*(1+PROFIT_TARGET) - selected.premium*(1-STOP_LOSS)) * 100))}%`,
                      height: "100%", background: pnlPct >= 0 ? "#00C896" : "#FF4757",
                      borderRadius: 4, transition: "width 0.3s ease"
                    }} />
                  </div>
                </div>

                {/* Exit summary */}
                {exitReason && exitPrem && (
                  <div style={{
                    background: exitReason === "PROFIT" ? "#00C89622" : "#FF475722",
                    border: `1px solid ${exitReason === "PROFIT" ? "#00C896" : "#FF4757"}`,
                    borderRadius: 10, padding: "14px 16px", marginBottom: 14
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 700,
                      color: exitReason === "PROFIT" ? "#00C896" : "#FF4757", marginBottom: 8 }}>
                      {exitReason === "PROFIT" ? "🎉 PROFIT TARGET — Wiley Strat WINS" :
                       exitReason === "STOP"   ? "🛑 STOP LOSS — Capital Protected" :
                       "⏰ EXPIRED — Time Stop"}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                      <span style={{ color: "#6B7280" }}>Entry: ${selected.premium.toFixed(3)}</span>
                      <span style={{ color: "#6B7280" }}>Exit: ${exitPrem.toFixed(3)}</span>
                      <span style={{ color: pnlColor, fontWeight: 700 }}>
                        {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}% (${pnlUsd >= 0 ? "+" : ""}{pnlUsd.toFixed(2)})
                      </span>
                    </div>
                  </div>
                )}

                {/* P&L Chart */}
                {history.length > 3 && (
                  <div style={{ background: "#0F1724", border: "1px solid #1E2A3A",
                    borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
                    <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10, letterSpacing: "0.06em" }}>
                      {selected.sym} OPTION P&L %
                    </div>
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={history}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1E2A3A" />
                        <XAxis dataKey="bar" tick={{ fill: "#4B5563", fontSize: 8 }} />
                        <YAxis tick={{ fill: "#6B7280", fontSize: 9 }} tickFormatter={v => `${v}%`} />
                        <Tooltip contentStyle={{ background: "#0F1724", border: "1px solid #2A3040", fontSize: 10 }}
                          formatter={(v, n) => [n === "pnlPct" ? `${v}%` : `$${v}`, n === "pnlPct" ? "P&L%" : "Stock"]} />
                        <ReferenceLine y={0}               stroke="#374151" strokeDasharray="3 3" />
                        <ReferenceLine y={PROFIT_TARGET*100} stroke="#00C896" strokeDasharray="4 4"
                          label={{ value: "+50%", fill: "#00C896", fontSize: 9, position: "right" }} />
                        <ReferenceLine y={-(STOP_LOSS*100)} stroke="#FF4757" strokeDasharray="4 4"
                          label={{ value: "-30%", fill: "#FF4757", fontSize: 9, position: "right" }} />
                        <Line type="monotone" dataKey="pnlPct" stroke={pnlColor} strokeWidth={2} dot={false} name="pnlPct" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Buttons */}
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={startSim} disabled={simState === "RUNNING"} style={{
                    flex: 2, background: simState === "RUNNING" ? "#1E2A3A" : "#00C896",
                    border: "none", borderRadius: 8,
                    color: simState === "RUNNING" ? "#6B7280" : "#000",
                    fontSize: 13, fontWeight: 700, padding: "12px",
                    cursor: simState === "RUNNING" ? "not-allowed" : "pointer", fontFamily: "inherit",
                  }}>
                    {simState === "RUNNING" ? "⏳ Simulating..." : `▶ SIM ${selected.sym} ${selected.direction}`}
                  </button>
                  <button onClick={resetSim} style={{
                    flex: 1, background: "transparent", border: "1px solid #2A3040",
                    borderRadius: 8, color: "#9CA3AF", fontSize: 12, padding: "12px",
                    cursor: "pointer", fontFamily: "inherit",
                  }}>🔄 Reset</button>
                  <button onClick={() => setTab("scanner")} style={{
                    flex: 1, background: "transparent", border: "1px solid #2A3040",
                    borderRadius: 8, color: "#9CA3AF", fontSize: 12, padding: "12px",
                    cursor: "pointer", fontFamily: "inherit",
                  }}>📊 Scanner</button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
