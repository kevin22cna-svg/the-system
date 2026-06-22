import { useState, useEffect, useRef } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

// ── Wiley Strat — AAL $16C June 26 Live Sim ──────────────────────────────
const ENTRY_PREMIUM  = 0.450;   // current mark price
const ENTRY_STOCK    = 15.884;  // AAL current price
const STRIKE         = 16.00;
const EXPIRY         = "June 26, 2026";
const DTE            = 9;
const CONTRACTS      = 1;
const COST           = ENTRY_PREMIUM * 100;

// Wiley Strat targets (swing = 2-5 DTE rules scaled for 9 DTE)
const PROFIT_TARGET  = 0.50;   // +50%
const STOP_LOSS      = 0.30;   // -30%

const TARGET_PREM    = ENTRY_PREMIUM * (1 + PROFIT_TARGET);  // $0.675
const STOP_PREM      = ENTRY_PREMIUM * (1 - STOP_LOSS);      // $0.315

// Greeks at entry
const DELTA          = 0.484;
const GAMMA          = 0.320;
const THETA          = -0.028;   // per day
const VEGA           = 0.010;

// Simulate realistic AAL price movement
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

function estimateOptionValue(stockPrice, minutesElapsed) {
  const priceMv   = stockPrice - ENTRY_STOCK;
  const deltaP    = DELTA * priceMv;
  const gammaP    = 0.5 * GAMMA * priceMv * priceMv;
  const daysElapsed = minutesElapsed / 390;  // 390 min per trading day
  const thetaD    = THETA * daysElapsed;
  return Math.max(ENTRY_PREMIUM + deltaP + gammaP + thetaD, 0.01);
}

export default function WileyStratSim() {
  const rngRef      = useRef(makeRng(Date.now()));
  const priceRef    = useRef(ENTRY_STOCK);
  const minutesRef  = useRef(0);

  const [stockPrice,  setStockPrice]  = useState(ENTRY_STOCK);
  const [optionValue, setOptionValue] = useState(ENTRY_PREMIUM);
  const [history,     setHistory]     = useState([]);
  const [status,      setStatus]      = useState("ACTIVE");  // ACTIVE | PROFIT | STOP | RUNNING
  const [exitPrice,   setExitPrice]   = useState(null);
  const [running,     setRunning]     = useState(false);
  const [bar,         setBar]         = useState(0);

  const statusRef = useRef("ACTIVE");

  function startSim() {
    // Reset
    priceRef.current   = ENTRY_STOCK;
    minutesRef.current = 0;
    statusRef.current  = "RUNNING";
    rngRef.current     = makeRng(Date.now());
    setHistory([]);
    setBar(0);
    setStatus("RUNNING");
    setExitPrice(null);
    setRunning(true);
  }

  function resetSim() {
    setRunning(false);
    setStatus("ACTIVE");
    setHistory([]);
    setBar(0);
    setStockPrice(ENTRY_STOCK);
    setOptionValue(ENTRY_PREMIUM);
    setExitPrice(null);
    statusRef.current = "ACTIVE";
  }

  useEffect(() => {
    if (!running) return;
    const interval = setInterval(() => {
      if (statusRef.current === "PROFIT" || statusRef.current === "STOP") {
        setRunning(false);
        clearInterval(interval);
        return;
      }

      minutesRef.current += 5;
      const b = minutesRef.current;

      // Realistic AAL intraday movement
      // Travel names tend to be correlated with oil/macro
      const vol   = 0.0008;  // per 5-min bar
      const drift = 0.00002; // slight upward drift (Iran oil deal thesis)
      const noise = rngRef.current.normal(drift, vol);
      priceRef.current = Math.max(14.0, priceRef.current * (1 + noise));

      const sp  = Math.round(priceRef.current * 1000) / 1000;
      const ov  = estimateOptionValue(sp, b);
      const pct = (ov - ENTRY_PREMIUM) / ENTRY_PREMIUM * 100;

      setStockPrice(sp);
      setOptionValue(Math.round(ov * 1000) / 1000);
      setBar(b);

      const point = {
        bar:    b,
        stock:  sp,
        option: Math.round(ov * 1000) / 1000,
        pnlPct: Math.round(pct * 10) / 10,
      };
      setHistory(h => [...h.slice(-120), point]);

      // Check exits
      if (pct >= PROFIT_TARGET * 100) {
        statusRef.current = "PROFIT";
        setStatus("PROFIT");
        setExitPrice(Math.round(ov * 1000) / 1000);
      } else if (pct <= -(STOP_LOSS * 100)) {
        statusRef.current = "STOP";
        setStatus("STOP");
        setExitPrice(Math.round(ov * 1000) / 1000);
      }
    }, 400); // 400ms per bar = fast sim
    return () => clearInterval(interval);
  }, [running]);

  const pnlUsd = (optionValue - ENTRY_PREMIUM) * 100;
  const pnlPct = (optionValue - ENTRY_PREMIUM) / ENTRY_PREMIUM * 100;
  const pnlColor = pnlPct >= 0 ? "#00C896" : "#FF4757";

  const progressPct = Math.min(100, Math.max(0,
    (optionValue - STOP_PREM) / (TARGET_PREM - STOP_PREM) * 100
  ));

  const statusCfg = {
    ACTIVE:  { color: "#FFB800", label: "⏳ READY — Hit Start to simulate" },
    RUNNING: { color: "#00C896", label: "🔥 IN TRADE — Wiley Strat tracking live" },
    PROFIT:  { color: "#00C896", label: `🎉 PROFIT TARGET HIT — Exit at $${exitPrice}` },
    STOP:    { color: "#FF4757", label: `🛑 STOP LOSS HIT — Exit at $${exitPrice}` },
  }[status];

  const exitPnl   = exitPrice ? (exitPrice - ENTRY_PREMIUM) * 100 : null;
  const exitPct   = exitPrice ? (exitPrice - ENTRY_PREMIUM) / ENTRY_PREMIUM * 100 : null;
  const daysElapsed = Math.round(bar / 390 * 10) / 10;

  return (
    <div style={{ background: "#080C14", minHeight: "100vh", color: "#E2E8F0",
      fontFamily: "'JetBrains Mono', monospace", padding: "20px 16px" }}>
      <div style={{ maxWidth: 800, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#FFF" }}>
            📊 WILEY STRAT — OPTION SIM
          </div>
          <div style={{ fontSize: 10, color: "#4B5563", marginTop: 2, letterSpacing: "0.08em" }}>
            AAL $16C JUNE 26  ·  9 DTE  ·  SWING TRADE  ·  TARGET +50% / STOP -30%
          </div>
        </div>

        {/* Status Banner */}
        <div style={{
          background: statusCfg.color + "22",
          border: `1px solid ${statusCfg.color}44`,
          borderRadius: 10, padding: "12px 16px", marginBottom: 16,
          display: "flex", justifyContent: "space-between", alignItems: "center"
        }}>
          <div style={{ fontSize: 12, color: statusCfg.color, fontWeight: 700 }}>
            {statusCfg.label}
          </div>
          {status === "RUNNING" && (
            <div style={{ fontSize: 14, color: pnlColor, fontWeight: 700 }}>
              {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%
            </div>
          )}
        </div>

        {/* Trade Setup */}
        <div style={{ background: "#0F1724", border: "1px solid #1E2A3A",
          borderRadius: 10, padding: "14px 16px", marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 12, letterSpacing: "0.08em" }}>
            TRADE SETUP
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
            {[
              { l: "Symbol",    v: "AAL $16C",     c: "#FFB800" },
              { l: "Expiry",    v: EXPIRY,           c: "#E2E8F0" },
              { l: "DTE",       v: `${DTE} days`,    c: "#E2E8F0" },
              { l: "Entry",     v: `$${ENTRY_PREMIUM}`, c: "#9CA3AF" },
              { l: "Cost",      v: `$${COST.toFixed(2)}`, c: "#E2E8F0" },
              { l: "Stock",     v: `$${ENTRY_STOCK}`, c: "#9CA3AF" },
              { l: "🎯 Target", v: `$${TARGET_PREM.toFixed(3)} (+50%)`, c: "#00C896" },
              { l: "🛑 Stop",   v: `$${STOP_PREM.toFixed(3)} (-30%)`, c: "#FF4757" },
              { l: "Break-even",v: `$${(STRIKE + ENTRY_PREMIUM).toFixed(2)}`, c: "#9CA3AF" },
            ].map((m, i) => (
              <div key={i} style={{ background: "#080C14", borderRadius: 6, padding: "8px 10px" }}>
                <div style={{ fontSize: 9, color: "#4B5563", marginBottom: 2 }}>{m.l}</div>
                <div style={{ fontSize: 11, color: m.c, fontWeight: 600 }}>{m.v}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Live Metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginBottom: 16 }}>
          {[
            { l: "AAL PRICE",   v: `$${stockPrice.toFixed(3)}`, sub: `${((stockPrice/ENTRY_STOCK-1)*100).toFixed(2)}%`, c: stockPrice >= ENTRY_STOCK ? "#00C896" : "#FF4757" },
            { l: "OPTION VAL",  v: `$${optionValue.toFixed(3)}`, sub: `entry $${ENTRY_PREMIUM}`, c: pnlColor },
            { l: "P&L",         v: `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%`, sub: `$${pnlUsd >= 0 ? "+" : ""}${pnlUsd.toFixed(2)}`, c: pnlColor },
            { l: "DAYS ELAPSED",v: `${daysElapsed}d`, sub: `${bar} bars`, c: "#9CA3AF" },
          ].map((m, i) => (
            <div key={i} style={{ background: "#0F1724", border: "1px solid #1E2A3A",
              borderRadius: 8, padding: "10px 12px" }}>
              <div style={{ fontSize: 9, color: "#4B5563", letterSpacing: "0.08em", marginBottom: 3 }}>{m.l}</div>
              <div style={{ fontSize: 14, color: m.c, fontWeight: 700 }}>{m.v}</div>
              <div style={{ fontSize: 9, color: "#6B7280", marginTop: 1 }}>{m.sub}</div>
            </div>
          ))}
        </div>

        {/* Progress Bar */}
        <div style={{ background: "#0F1724", border: "1px solid #1E2A3A",
          borderRadius: 10, padding: "14px 16px", marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#6B7280", marginBottom: 8 }}>
            <span style={{ color: "#FF4757" }}>🛑 STOP ${STOP_PREM.toFixed(3)} (-30%)</span>
            <span style={{ color: "#FFB800" }}>ENTRY ${ENTRY_PREMIUM}</span>
            <span style={{ color: "#00C896" }}>🎯 TARGET ${TARGET_PREM.toFixed(3)} (+50%)</span>
          </div>
          <div style={{ background: "#1E2A3A", borderRadius: 4, height: 10, position: "relative" }}>
            <div style={{
              position: "absolute", left: 0, top: 0, height: "100%",
              width: `${progressPct}%`,
              background: pnlPct >= 0 ? "#00C896" : "#FF4757",
              borderRadius: 4, transition: "width 0.3s ease"
            }} />
            <div style={{ position: "absolute", left: "37.5%", top: -3, width: 2, height: 16, background: "#FFB800" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "#4B5563", marginTop: 4 }}>
            <span>-30%</span><span style={{ color: "#FFB800" }}>▲ entry</span><span>+50%</span>
          </div>
        </div>

        {/* Charts */}
        {history.length > 3 && (
          <>
            <div style={{ background: "#0F1724", border: "1px solid #1E2A3A",
              borderRadius: 10, padding: "14px 16px", marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10, letterSpacing: "0.06em" }}>
                OPTION P&L % — LIVE
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E2A3A" />
                  <XAxis dataKey="bar" tick={{ fill: "#4B5563", fontSize: 8 }} />
                  <YAxis tick={{ fill: "#6B7280", fontSize: 9 }} tickFormatter={v => `${v}%`} />
                  <Tooltip contentStyle={{ background: "#0F1724", border: "1px solid #2A3040", fontSize: 10 }}
                    formatter={(v, n) => [n === "pnlPct" ? `${v}%` : `$${v}`, n === "pnlPct" ? "P&L%" : "Stock"]} />
                  <ReferenceLine y={0}                   stroke="#374151" strokeDasharray="3 3" />
                  <ReferenceLine y={PROFIT_TARGET * 100} stroke="#00C896" strokeDasharray="4 4"
                    label={{ value: "+50%", fill: "#00C896", fontSize: 9, position: "right" }} />
                  <ReferenceLine y={-(STOP_LOSS * 100)}  stroke="#FF4757" strokeDasharray="4 4"
                    label={{ value: "-30%", fill: "#FF4757", fontSize: 9, position: "right" }} />
                  <Line type="monotone" dataKey="pnlPct" stroke={pnlColor} strokeWidth={2} dot={false} name="pnlPct" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div style={{ background: "#0F1724", border: "1px solid #1E2A3A",
              borderRadius: 10, padding: "14px 16px", marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10, letterSpacing: "0.06em" }}>
                AAL STOCK PRICE
              </div>
              <ResponsiveContainer width="100%" height={130}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E2A3A" />
                  <XAxis dataKey="bar" tick={{ fill: "#4B5563", fontSize: 8 }} />
                  <YAxis tick={{ fill: "#6B7280", fontSize: 9 }} domain={["auto","auto"]} tickFormatter={v => `$${v}`} />
                  <Tooltip contentStyle={{ background: "#0F1724", border: "1px solid #2A3040", fontSize: 10 }}
                    formatter={v => [`$${v}`, "AAL"]} />
                  <ReferenceLine y={STRIKE} stroke="#FFB800" strokeDasharray="3 3"
                    label={{ value: "$16 strike", fill: "#FFB800", fontSize: 9 }} />
                  <ReferenceLine y={ENTRY_STOCK} stroke="#7C83FD" strokeDasharray="3 3"
                    label={{ value: "entry", fill: "#7C83FD", fontSize: 9 }} />
                  <Line type="monotone" dataKey="stock" stroke="#60A5FA" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}

        {/* Exit Summary */}
        {(status === "PROFIT" || status === "STOP") && exitPrice && (
          <div style={{
            background: status === "PROFIT" ? "#00C89622" : "#FF475722",
            border: `1px solid ${status === "PROFIT" ? "#00C896" : "#FF4757"}`,
            borderRadius: 10, padding: "16px 20px", marginBottom: 16
          }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: status === "PROFIT" ? "#00C896" : "#FF4757", marginBottom: 10 }}>
              {status === "PROFIT" ? "🎉 WILEY STRAT — PROFIT TARGET HIT" : "🛑 WILEY STRAT — STOP LOSS HIT"}
            </div>
            {[
              { l: "Entry Premium", v: `$${ENTRY_PREMIUM}` },
              { l: "Exit Premium",  v: `$${exitPrice}` },
              { l: "P&L",           v: `${exitPct >= 0 ? "+" : ""}${exitPct?.toFixed(1)}%  ($${exitPnl?.toFixed(2)})` },
              { l: "Days in Trade", v: `${daysElapsed} days` },
              { l: "Wiley Rule",    v: status === "PROFIT" ? "PROFIT FIRST — sold immediately ✅" : "Stop honored — capital protected ✅" },
            ].map((m, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 11 }}>
                <span style={{ color: "#6B7280" }}>{m.l}</span>
                <span style={{ color: "#E2E8F0", fontWeight: 600 }}>{m.v}</span>
              </div>
            ))}
          </div>
        )}

        {/* Buttons */}
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={startSim} disabled={running} style={{
            flex: 1, background: running ? "#1E2A3A" : "#00C896",
            border: "none", borderRadius: 8,
            color: running ? "#6B7280" : "#000",
            fontSize: 13, fontWeight: 700, padding: "12px",
            cursor: running ? "not-allowed" : "pointer", fontFamily: "inherit",
          }}>
            {running ? "⏳ Simulating..." : "▶ START SIM"}
          </button>
          <button onClick={resetSim} style={{
            flex: 1, background: "transparent",
            border: "1px solid #2A3040", borderRadius: 8,
            color: "#9CA3AF", fontSize: 13, padding: "12px",
            cursor: "pointer", fontFamily: "inherit",
          }}>
            🔄 RESET
          </button>
        </div>

        {/* Greeks */}
        <div style={{ background: "#0F1724", border: "1px solid #1E2A3A",
          borderRadius: 10, padding: "14px 16px", marginTop: 16 }}>
          <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10, letterSpacing: "0.06em" }}>
            GREEKS AT ENTRY
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8 }}>
            {[
              { l: "Delta", v: DELTA.toFixed(3), note: "~$0.05 per $0.10 move" },
              { l: "Gamma", v: GAMMA.toFixed(3), note: "Delta accel" },
              { l: "Theta", v: THETA.toFixed(3), note: "-$2.76/day" },
              { l: "Vega",  v: VEGA.toFixed(3),  note: "IV sensitivity" },
            ].map((g, i) => (
              <div key={i} style={{ background: "#080C14", borderRadius: 6, padding: "8px 10px", textAlign: "center" }}>
                <div style={{ fontSize: 9, color: "#4B5563", marginBottom: 2 }}>{g.l}</div>
                <div style={{ fontSize: 14, color: "#E2E8F0", fontWeight: 700 }}>{g.v}</div>
                <div style={{ fontSize: 8, color: "#6B7280", marginTop: 2 }}>{g.note}</div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
