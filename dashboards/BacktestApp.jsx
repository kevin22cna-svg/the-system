import { useState, useCallback } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from "recharts";

// ─────────────────────────────────────────────────────────────────
// BACKTEST ENGINE — Ported from Python to JavaScript
// Mirrors backtest_engine.py exactly
// ─────────────────────────────────────────────────────────────────

const BARS_PER_DAY = 195;
const DELTA_ATM = 0.50;

// Seeded random for reproducibility (LCG)
function makeRng(seed) {
  let s = seed >>> 0;
  return {
    next() { s = (1664525 * s + 1013904223) >>> 0; return s / 4294967296; },
    normal(mu = 0, sigma = 1) {
      // Box-Muller
      const u1 = Math.max(1e-10, this.next());
      const u2 = this.next();
      return mu + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    },
    lognormal(mu, sigma) { return Math.exp(this.normal(mu, sigma)); },
    uniform(lo, hi) { return lo + this.next() * (hi - lo); },
  };
}

function ewm(values, span) {
  const alpha = 2 / (span + 1);
  const result = new Float64Array(values.length);
  result[0] = values[0];
  for (let i = 1; i < values.length; i++) result[i] = alpha * values[i] + (1 - alpha) * result[i - 1];
  return result;
}

function generateDay(prevClose, params, rng) {
  const n = BARS_PER_DAY;
  const vol = params.dailyVol / Math.sqrt(n);
  const trending = rng.next() < 0.60;
  const dir = rng.next() < 0.55 ? 1 : -1;

  const prices = new Float64Array(n);
  prices[0] = prevClose;
  for (let i = 1; i < n; i++) {
    const noise = trending ? rng.normal(dir * vol * 0.3, vol) : rng.normal(0, vol * 0.5);
    prices[i] = prices[i - 1] * (1 + noise);
  }

  const highs  = prices.map(p => p * (1 + Math.abs(rng.normal(0, vol * 0.4))));
  const lows   = prices.map(p => p * (1 - Math.abs(rng.normal(0, vol * 0.4))));
  const closes = prices.map(p => p * (1 + rng.normal(0, vol * 0.2)));
  const vols   = Array.from({length: n}, () =>
    Math.max(1, Math.round(rng.lognormal(Math.log(params.avgVolume / n), 0.4)))
  );
  // Volume spikes on ~5% of bars
  for (let i = 0; i < Math.floor(n * 0.05); i++) {
    const idx = Math.floor(rng.next() * n);
    vols[idx] *= (2 + Math.floor(rng.next() * 4));
  }

  const open0 = prices[0];
  const PMH = open0 * (1 + rng.uniform(0.002, 0.006));
  const PML = open0 * (1 - rng.uniform(0.002, 0.006));
  const PDH = prevClose * (1 + rng.uniform(0.005, 0.015));
  const PDL = prevClose * (1 - rng.uniform(0.005, 0.015));

  // VWAP
  const typical = closes.map((c, i) => (highs[i] + lows[i] + c) / 3);
  const vwap = new Float64Array(n);
  let cumTPV = 0, cumV = 0;
  for (let i = 0; i < n; i++) {
    cumTPV += typical[i] * vols[i];
    cumV   += vols[i];
    vwap[i] = cumTPV / cumV;
  }

  const ema13  = ewm(closes, 13);
  const ema48  = ewm(closes, 48);
  const ema200 = ewm(closes, 200);

  // 15min closes (every 8 bars)
  const close15m = new Float64Array(n).fill(NaN);
  for (let i = 7; i < n; i += 8) close15m[i] = closes[i];
  // forward fill
  let last = NaN;
  for (let i = 0; i < n; i++) {
    if (!isNaN(close15m[i])) last = close15m[i];
    else close15m[i] = last;
  }

  return { prices, highs, lows, closes, vols, PMH, PML, PDH, PDL, vwap, ema13, ema48, ema200, close15m, trending };
}

function scoreBar(day, bar) {
  if (bar < 50 || bar >= BARS_PER_DAY - 2) return { score: 0, direction: null };
  const { closes, highs, lows, vols, PMH, PDL, PDH, vwap, ema13, ema48, ema200, close15m } = day;

  const e13 = ema13[bar], e48 = ema48[bar], e200 = ema200[bar];
  const price = closes[bar], pmh = PMH, pdl = PDL, pdh = PDH;
  const c15 = close15m[bar];

  // EMA fan hard gate
  const bull = e13 > e48 && e48 > e200 && (e13-e48)/e48 > 0.0002 && (e48-e200)/e200 > 0.0002;
  const bear = e200 > e48 && e48 > e13 && (e48-e13)/e13 > 0.0002 && (e200-e48)/e48 > 0.0002;
  if (!bull && !bear) return { score: 0, direction: null };
  const direction = bull ? "CALLS" : "PUTS";

  // 15min confirm hard gate
  if (isNaN(c15)) return { score: 0, direction: null };
  if (direction === "CALLS" && c15 <= pmh) return { score: 0, direction: null };
  if (direction === "PUTS"  && c15 >= pdl) return { score: 0, direction: null };

  // Chop zone hard gate
  if (Math.abs(pdh - pmh) / pmh < 0.002) return { score: 0, direction: null };

  let score = 4; // EMA fan + 15min confirm

  // Key level retest (3rd candle rule)
  if (bar >= 2) {
    const p2c = closes[bar-2], p2h = highs[bar-2], p2l = lows[bar-2];
    const p1c = closes[bar-1], p1h = highs[bar-1], p1l = lows[bar-1];
    if (direction === "CALLS") {
      if (p2h > pmh && p2c < pmh && p1h > pmh && p1c < pmh && price > pmh) score += 2;
      else if (price > pmh) score += 1;
    } else {
      if (p2l < pdl && p2c > pdl && p1l < pdl && p1c > pdl && price < pdl) score += 2;
      else if (price < pdl) score += 1;
    }
  }

  // 13 EMA pullback (Casey entry)
  const prevClose2 = closes[bar - 1];
  if (direction === "CALLS" && prevClose2 < e13 && price > e13) score += 1;
  if (direction === "PUTS"  && prevClose2 > e13 && price < e13) score += 1;

  // Volume
  let avgVol = 0;
  const start = Math.max(0, bar - 20);
  for (let i = start; i < bar; i++) avgVol += vols[i];
  avgVol /= (bar - start);
  if (avgVol > 0 && vols[bar] > avgVol * 1.5) score += 1;

  // VWAP
  if ((direction === "CALLS" && price > vwap[bar]) || (direction === "PUTS" && price < vwap[bar])) score += 1;

  return { score: Math.min(score, 10), direction, price };
}

function estTimeValue(stockPrice, dailyVol, barsLeft) {
  const T = Math.max(barsLeft / BARS_PER_DAY, 0.001);
  return Math.max(stockPrice * dailyVol * Math.sqrt(T) * 0.4, 0.01);
}

function optionValue(stockPrice, entryPrice, direction, dailyVol, barsLeft) {
  const tv = estTimeValue(stockPrice, dailyVol, barsLeft);
  let move = stockPrice - entryPrice;
  if (direction === "PUTS") move = -move;
  const intrinsic = Math.max(0, move * DELTA_ATM);
  return Math.max(0.01, tv + intrinsic);
}

function runBacktest(cfg) {
  const {
    tradingDays, positionUsd, profitTarget, stopLoss,
    minConfluence, maxDayTrades, seed,
    instruments
  } = cfg;

  const results = {};
  const rng = makeRng(seed);

  for (const [sym, params] of Object.entries(instruments)) {
    const trades = [];
    let prevClose = params.startPrice;
    let equity = 0;

    for (let day = 0; day < tradingDays; day++) {
      const dayData = generateDay(prevClose, params, rng);
      let dayTrades = 0;

      const entryStart = 50;
      const entryEnd = 175;

      for (let bar = entryStart; bar < entryEnd; bar++) {
        if (dayTrades >= maxDayTrades) break;
        const r = scoreBar(dayData, bar);
        if (r.score < minConfluence) continue;

        const { direction, price: entryPrice } = r;
        const barsLeft = BARS_PER_DAY - bar;
        let entryPrem = estTimeValue(entryPrice, params.dailyVol, barsLeft);
        entryPrem *= (1 + params.spreadPct);
        // Scale P&L by position size ratio (1 contract = ~$100-200, scale from $15 base)
        const scaleFactor = positionUsd / 15.0;
        const contracts = 1;

        let exitPnl = null;
        let exitReason = "TIME_EXPIRE";

        for (let fwd = 1; fwd < Math.min(barsLeft - 1, 80); fwd++) {
          const fwdP = dayData.closes[bar + fwd];
          const blRem = barsLeft - fwd;
          const currV = optionValue(fwdP, entryPrice, direction, params.dailyVol, blRem);
          const pctChg = (currV - entryPrem) / entryPrem;

          if (pctChg >= profitTarget) {
            exitPnl = contracts * (currV - entryPrem) * 100;
            exitReason = "PROFIT_TARGET";
            break;
          } else if (pctChg <= -stopLoss) {
            exitPnl = -contracts * entryPrem * stopLoss * 100;
            exitReason = "STOP_LOSS";
            break;
          }
        }

        if (exitPnl === null) {
          const endBar = Math.min(bar + barsLeft - 2, BARS_PER_DAY - 1);
          const fwdP = dayData.closes[endBar];
          const finalV = optionValue(fwdP, entryPrice, direction, params.dailyVol, 3);
          exitPnl = (finalV - entryPrem) * 100 * scaleFactor;
        }

        equity += exitPnl;
        dayTrades++;
        trades.push({
          day, bar, direction, score: r.score,
          entry: Math.round(entryPrice * 100) / 100,
          prem: Math.round(entryPrem * 1000) / 1000,
          pnl: Math.round(exitPnl * 100) / 100,
          exit: exitReason,
          equity: Math.round(equity * 100) / 100,
        });
      }

      prevClose = dayData.closes[BARS_PER_DAY - 1];
    }

    if (!trades.length) { results[sym] = null; continue; }

    const wins   = trades.filter(t => t.pnl > 0);
    const losses = trades.filter(t => t.pnl <= 0);
    const wr     = wins.length / trades.length * 100;
    const totalWin  = wins.reduce((s, t) => s + t.pnl, 0);
    const totalLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));
    const pf     = totalLoss > 0 ? totalWin / totalLoss : 999;
    const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);

    let peak = 0, maxDD = 0;
    for (const t of trades) {
      if (t.equity > peak) peak = t.equity;
      maxDD = Math.max(maxDD, peak - t.equity);
    }

    const byScore = {};
    for (const t of trades) {
      if (!byScore[t.score]) byScore[t.score] = { count: 0, wins: 0, totalPnl: 0 };
      byScore[t.score].count++;
      if (t.pnl > 0) byScore[t.score].wins++;
      byScore[t.score].totalPnl += t.pnl;
    }

    results[sym] = {
      totalTrades:    trades.length,
      tradesPerDay:   Math.round(trades.length / tradingDays * 100) / 100,
      winRate:        Math.round(wr * 10) / 10,
      totalPnl:       Math.round(totalPnl),
      avgWin:         Math.round(wins.reduce((s,t) => s+t.pnl, 0) / (wins.length||1) * 100) / 100,
      avgLoss:        Math.round(losses.reduce((s,t) => s+t.pnl, 0) / (losses.length||1) * 100) / 100,
      profitFactor:   Math.round(pf * 100) / 100,
      maxDrawdown:    Math.round(maxDD),
      profitTargets:  trades.filter(t => t.exit === "PROFIT_TARGET").length,
      stopLosses:     trades.filter(t => t.exit === "STOP_LOSS").length,
      timeExpires:    trades.filter(t => t.exit === "TIME_EXPIRE").length,
      callsPnl:       Math.round(trades.filter(t=>t.direction==="CALLS").reduce((s,t)=>s+t.pnl,0)),
      putsPnl:        Math.round(trades.filter(t=>t.direction==="PUTS").reduce((s,t)=>s+t.pnl,0)),
      byScore:        Object.fromEntries(Object.entries(byScore).map(([sc, d]) => [sc, {
        count: d.count,
        winRate: Math.round(d.wins/d.count*1000)/10,
        avgPnl: Math.round(d.totalPnl/d.count*100)/100,
        totalPnl: Math.round(d.totalPnl),
      }])),
      equityCurve: trades.map((t, i) => ({ i, equity: t.equity })),
    };
  }
  return results;
}

// ─────────────────────────────────────────────────────────────────
// UI
// ─────────────────────────────────────────────────────────────────
const SYM_COLORS = { SPY: "#00C896", QQQ: "#7C83FD", IWM: "#FFB800" };
const DEFAULT_INSTRUMENTS = {
  SPY: { startPrice: 480, dailyVol: 0.011, drift: 0.0003, avgVolume: 80_000_000, spreadPct: 0.010 },
  QQQ: { startPrice: 415, dailyVol: 0.014, drift: 0.0004, avgVolume: 45_000_000, spreadPct: 0.012 },
  IWM: { startPrice: 200, dailyVol: 0.013, drift: 0.0002, avgVolume: 35_000_000, spreadPct: 0.015 },
};

function Stat({ label, value, color = "#E2E8F0", sub }) {
  return (
    <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ fontSize: 9, color: "#4B5563", letterSpacing: "0.08em", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 15, color, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ fontSize: 9, color: "#6B7280", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export default function BacktestApp() {
  const [cfg, setCfg] = useState({
    tradingDays: 252, positionUsd: 50, profitTarget: 0.25, stopLoss: 0.25,
    minConfluence: 5, maxDayTrades: 3, seed: 42,
    instruments: DEFAULT_INSTRUMENTS,
  });
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const [activeSym, setActiveSym] = useState("SPY");
  const [tab, setTab] = useState("metrics");
  const [showCfg, setShowCfg] = useState(false);

  const handleRun = useCallback(() => {
    setRunning(true);
    setResults(null);
    setTimeout(() => {
      try {
        const r = runBacktest(cfg);
        setResults(r);
        setActiveSym(Object.keys(r).find(s => r[s]) || "SPY");
      } catch(e) { console.error(e); }
      setRunning(false);
    }, 50);
  }, [cfg]);

  const r = results?.[activeSym];

  const scoreData = r ? Object.entries(r.byScore).map(([sc, d]) => ({
    score: `S${sc}`, winRate: d.winRate, avgPnl: d.avgPnl, count: d.count
  })) : [];

  const eqSampled = r ? r.equityCurve.filter((_, i) => i % 4 === 0) : [];

  const inp = (label, key, type = "number", min, max, step = 1) => (
    <div style={{ marginBottom: 10 }}>
      <label style={{ fontSize: 10, color: "#9CA3AF", display: "block", marginBottom: 3 }}>{label}</label>
      <input
        type={type} min={min} max={max} step={step}
        value={key.includes(".") ? cfg.instruments[key.split(".")[0]][key.split(".")[1]] : cfg[key]}
        onChange={e => {
          const val = type === "number" ? parseFloat(e.target.value) : parseInt(e.target.value);
          if (key.includes(".")) {
            const [sym, field] = key.split(".");
            setCfg(c => ({ ...c, instruments: { ...c.instruments, [sym]: { ...c.instruments[sym], [field]: val }}}));
          } else {
            setCfg(c => ({ ...c, [key]: val }));
          }
        }}
        style={{
          width: "100%", background: "#080C14", border: "1px solid #2A3040",
          borderRadius: 6, color: "#E2E8F0", fontSize: 12, padding: "6px 10px",
          fontFamily: "inherit", boxSizing: "border-box",
        }}
      />
    </div>
  );

  return (
    <div style={{ background: "#080C14", minHeight: "100vh", color: "#E2E8F0", fontFamily: "'JetBrains Mono', monospace", padding: "20px 16px" }}>
      <div style={{ maxWidth: 820, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#FFF" }}>📊 0DTE BACKTEST ENGINE</div>
          <div style={{ fontSize: 10, color: "#4B5563", marginTop: 2, letterSpacing: "0.08em" }}>
            KEVIN + CASEY EMA SYSTEM  ·  SPY / QQQ / IWM  ·  ADJUSTABLE PARAMETERS
          </div>
        </div>

        {/* Config toggle + Run */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <button onClick={() => setShowCfg(v => !v)} style={{
            background: showCfg ? "#1E2A3A" : "transparent",
            border: "1px solid #2A3040", borderRadius: 8,
            color: "#9CA3AF", fontSize: 11, padding: "8px 14px", cursor: "pointer", fontFamily: "inherit",
          }}>⚙️ {showCfg ? "Hide" : "Show"} Config</button>
          <button onClick={handleRun} disabled={running} style={{
            flex: 1, background: running ? "#1E2A3A" : "#00C896",
            border: "none", borderRadius: 8,
            color: running ? "#6B7280" : "#000", fontSize: 13, fontWeight: 700,
            padding: "8px 20px", cursor: running ? "not-allowed" : "pointer", fontFamily: "inherit",
            transition: "all 0.15s",
          }}>
            {running ? "⏳ Running backtest..." : "▶ RUN BACKTEST"}
          </button>
        </div>

        {/* Config Panel */}
        {showCfg && (
          <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 10, padding: 16, marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 14, letterSpacing: "0.08em" }}>STRATEGY PARAMETERS</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
              {inp("Trading Days", "tradingDays", "number", 21, 504)}
              {inp("Position Size ($)", "positionUsd", "number", 5, 500)}
              {inp("Profit Target (%)", "profitTarget", "number", 0.05, 1.0, 0.05)}
              {inp("Stop Loss (%)", "stopLoss", "number", 0.05, 1.0, 0.05)}
              {inp("Min Confluence Score", "minConfluence", "number", 4, 9)}
              {inp("Max Trades/Day", "maxDayTrades", "number", 1, 10)}
              {inp("Random Seed", "seed", "number", 1, 9999)}
            </div>
            <div style={{ fontSize: 11, color: "#6B7280", margin: "14px 0 10px", letterSpacing: "0.08em" }}>INSTRUMENT PARAMETERS</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0 12px" }}>
              {["SPY","QQQ","IWM"].map(sym => (
                <div key={sym}>
                  <div style={{ fontSize: 10, color: SYM_COLORS[sym], fontWeight: 700, marginBottom: 8 }}>{sym}</div>
                  {inp("Start Price", `${sym}.startPrice`, "number", 50, 1000)}
                  {inp("Daily Vol", `${sym}.dailyVol`, "number", 0.005, 0.05, 0.001)}
                </div>
              ))}
            </div>
            <div style={{ fontSize: 10, color: "#4B5563", marginTop: 8 }}>
              Tip: Lower Min Confluence to 4 to see more trades. Raise to 7 for prime-only setups.
            </div>
          </div>
        )}

        {/* Results */}
        {results && (
          <>
            {/* Symbol selector */}
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              {Object.entries(results).map(([sym, res]) => res && (
                <button key={sym} onClick={() => setActiveSym(sym)} style={{
                  flex: 1, background: activeSym === sym ? SYM_COLORS[sym] + "22" : "transparent",
                  border: `1px solid ${activeSym === sym ? SYM_COLORS[sym] : "#1E2A3A"}`,
                  borderRadius: 8, color: activeSym === sym ? SYM_COLORS[sym] : "#6B7280",
                  fontSize: 11, padding: "10px 6px", cursor: "pointer", fontFamily: "inherit",
                  fontWeight: activeSym === sym ? 700 : 400,
                }}>
                  <div style={{ fontSize: 14 }}>{sym}</div>
                  <div style={{ fontSize: 10, marginTop: 2 }}>WR: {res.winRate}%</div>
                  <div style={{ fontSize: 10 }}>${res.totalPnl.toLocaleString()}</div>
                </button>
              ))}
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
              {[["metrics","📊 Metrics"],["equity","📈 Equity"],["scores","🎯 By Score"],["calls","📉 Calls/Puts"]].map(([id,label]) => (
                <button key={id} onClick={() => setTab(id)} style={{
                  background: tab === id ? "#1E3A5F" : "transparent",
                  border: `1px solid ${tab === id ? "#3B82F6" : "#1E2A3A"}`,
                  borderRadius: 7, color: tab === id ? "#93C5FD" : "#6B7280",
                  fontSize: 10, padding: "5px 10px", cursor: "pointer", fontFamily: "inherit",
                }}>{label}</button>
              ))}
            </div>

            {r && tab === "metrics" && (
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
                  <Stat label="WIN RATE"       value={`${r.winRate}%`}            color="#00C896" />
                  <Stat label="PROFIT FACTOR"  value={`${r.profitFactor}x`}       color="#00C896" />
                  <Stat label="TOTAL P&L"      value={`$${r.totalPnl.toLocaleString()}`} color="#00C896" />
                  <Stat label="TOTAL TRADES"   value={r.totalTrades}              sub={`${r.tradesPerDay}/day avg`} />
                  <Stat label="AVG WIN"        value={`$${r.avgWin}`}             color="#00C896" />
                  <Stat label="AVG LOSS"       value={`$${r.avgLoss}`}            color="#FF4757" />
                  <Stat label="MAX DRAWDOWN"   value={`$${r.maxDrawdown}`}        color="#FFB800" />
                  <Stat label="+25% TARGETS"   value={`${r.profitTargets}`}       color="#00C896" sub={`${Math.round(r.profitTargets/r.totalTrades*100)}% of trades`} />
                  <Stat label="STOPS HIT"      value={`${r.stopLosses}`}          color="#FF4757" sub={`${Math.round(r.stopLosses/r.totalTrades*100)}% of trades`} />
                </div>
                {/* Combined row */}
                <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 8, padding: "12px 16px" }}>
                  <div style={{ fontSize: 10, color: "#6B7280", marginBottom: 8, letterSpacing: "0.06em" }}>ALL 3 COMBINED</div>
                  {["SPY","QQQ","IWM"].map(sym => results[sym] && (
                    <div key={sym} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 11 }}>
                      <span style={{ color: SYM_COLORS[sym], fontWeight: 700, minWidth: 40 }}>{sym}</span>
                      <span style={{ color: "#9CA3AF" }}>WR: {results[sym].winRate}%</span>
                      <span style={{ color: "#9CA3AF" }}>PF: {results[sym].profitFactor}x</span>
                      <span style={{ color: "#00C896", fontWeight: 600 }}>${results[sym].totalPnl.toLocaleString()}</span>
                    </div>
                  ))}
                  <div style={{ borderTop: "1px solid #1E2A3A", marginTop: 8, paddingTop: 8, display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <span style={{ color: "#6B7280" }}>Combined P&L</span>
                    <span style={{ color: "#00C896", fontWeight: 700 }}>
                      ${Object.values(results).filter(Boolean).reduce((s,r2) => s + r2.totalPnl, 0).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {r && tab === "equity" && (
              <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 10, padding: 16 }}>
                <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 12, letterSpacing: "0.08em" }}>
                  EQUITY CURVE — {activeSym}
                </div>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={eqSampled}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E2A3A" />
                    <XAxis dataKey="i" tick={{ fill: "#4B5563", fontSize: 9 }} label={{ value: "Trade #", fill: "#4B5563", fontSize: 9 }} />
                    <YAxis tick={{ fill: "#6B7280", fontSize: 9 }} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
                    <Tooltip contentStyle={{ background: "#0F1724", border: "1px solid #2A3040", fontSize: 11 }}
                      formatter={v => [`$${v.toLocaleString()}`, "Equity"]} />
                    <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 4" />
                    <Line type="monotone" dataKey="equity" stroke={SYM_COLORS[activeSym]} strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, fontSize: 11 }}>
                  <span style={{ color: "#6B7280" }}>Start: $0</span>
                  <span style={{ color: "#FF4757" }}>Max DD: ${r.maxDrawdown.toLocaleString()}</span>
                  <span style={{ color: SYM_COLORS[activeSym], fontWeight: 700 }}>End: ${r.totalPnl.toLocaleString()}</span>
                </div>
              </div>
            )}

            {r && tab === "scores" && (
              <div>
                <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 10, padding: 16, marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 12, letterSpacing: "0.08em" }}>WIN RATE BY CONFLUENCE SCORE</div>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={scoreData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E2A3A" />
                      <XAxis dataKey="score" tick={{ fill: "#9CA3AF", fontSize: 10 }} />
                      <YAxis tick={{ fill: "#6B7280", fontSize: 9 }} domain={[0, 100]} tickFormatter={v => `${v}%`} />
                      <Tooltip contentStyle={{ background: "#0F1724", border: "1px solid #2A3040", fontSize: 11 }}
                        formatter={v => [`${v}%`, "Win Rate"]} />
                      <Bar dataKey="winRate" radius={[4,4,0,0]}>
                        {scoreData.map((s, i) => (
                          <Cell key={i} fill={s.winRate >= 85 ? "#00C896" : s.winRate >= 70 ? "#FFB800" : "#FF4757"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                {scoreData.map((s, i) => (
                  <div key={i} style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 8, padding: "10px 14px", marginBottom: 6, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 13, color: SYM_COLORS[activeSym], fontWeight: 700 }}>{s.score}</div>
                      <div style={{ fontSize: 10, color: "#6B7280" }}>{s.count} trades</div>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: s.winRate >= 85 ? "#00C896" : s.winRate >= 70 ? "#FFB800" : "#FF4757" }}>{s.winRate}%</div>
                      <div style={{ fontSize: 9, color: "#6B7280" }}>win rate</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 12, color: "#E2E8F0" }}>${s.avgPnl}/trade</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {r && tab === "calls" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[["📈 CALLS", r.callsPnl, "#00C896"], ["📉 PUTS", r.putsPnl, "#FF9F7F"]].map(([label, pnl, color]) => (
                  <div key={label} style={{ background: "#0F1724", border: `1px solid ${color}33`, borderRadius: 10, padding: "16px 20px" }}>
                    <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 6 }}>{label}</div>
                    <div style={{ fontSize: 22, color, fontWeight: 700 }}>${pnl.toLocaleString()}</div>
                    <div style={{ fontSize: 11, color: "#6B7280", marginTop: 4 }}>
                      {Math.round(pnl / (r.callsPnl + r.putsPnl) * 100)}% of total P&L
                    </div>
                  </div>
                ))}
                <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 10, padding: "14px 16px", fontSize: 11, color: "#9CA3AF", lineHeight: 1.8 }}>
                  {r.callsPnl > r.putsPnl
                    ? "📈 Calls outperforming — bullish drift in simulation. Favor calls on neutral/bullish days."
                    : "📉 Puts slightly ahead — watch for trending bear days to maximize put entries."}
                  <br/>
                  Tip: On IWM, calls and puts stay close — good for range-bound or balanced market conditions.
                </div>
              </div>
            )}
          </>
        )}

        {!results && !running && (
          <div style={{ textAlign: "center", padding: "40px 0", color: "#4B5563", fontSize: 13 }}>
            Adjust parameters above and hit <span style={{ color: "#00C896" }}>▶ RUN BACKTEST</span> to simulate 252 trading days
          </div>
        )}
      </div>
    </div>
  );
}
