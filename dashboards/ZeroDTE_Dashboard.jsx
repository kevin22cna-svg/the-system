import { useState } from "react";

const CONFLUENCE = [
  { pts: "+2", cat: "EMA",    label: "EMA fan aligned & spacing out (bullish: 13>48>200 | bearish: 200>48>13)", bull: true, bear: true },
  { pts: "+2", cat: "15MIN",  label: "15min BODY close above PMH (calls) or below PML (puts) — not a wick", bull: true, bear: true },
  { pts: "+2", cat: "STRUCT", label: "PDH rejection + lower high (puts) OR PDL hold + higher low (calls) — structure confirmed", bull: true, bear: true },
  { pts: "+1", cat: "ENTRY",  label: "2min 13 EMA pullback/bounce in trend direction (Casey entry trigger)", bull: true, bear: true },
  { pts: "+1", cat: "VOL",    label: "Volume above average on the setup candle", bull: true, bear: true },
  { pts: "+1", cat: "VWAP",   label: "VWAP in agreement — above for calls, below for puts", bull: true, bear: true },
  { pts: "+1", cat: "AIR",    label: "Clean air — PDH and PMH/PML not within 0.2% (no chop zone)", bull: true, bear: true },
];

const VETOS = [
  "EMAs bunched / crossing — no fan present",
  "15min candle hasn't confirmed direction yet",
  "Price stuck in chop zone (PDH ≈ PMH, <0.2% apart)",
  "Time is after 3:45pm ET — no new entries",
  "First or second candle wick only — wait for 3rd close",
];

const LEVELS = [
  { rank: 1, name: "PDH", full: "Previous Day High", note: "Major resistance. Break above = bull trend day = CALLS. PDH + PMH both broken = STRONGEST signal. PDH→PDL = the smooth money zone." },
  { rank: 2, name: "PDL", full: "Previous Day Low",  note: "Major support. Break below = bear trend day = PUTS. PDL break + 1-sided fight = runners. Scale out heavy at PDL." },
  { rank: 3, name: "PMH", full: "Pre-Market High",   note: "First bullish sign when broken. Wait for PMH break BEFORE going long. PMH becomes SUPPORT after broken (S/R flip) — calls off PMH support. Price between PML/PMH = CHOP, avoid." },
  { rank: 4, name: "PML", full: "Pre-Market Low",    note: "First bearish sign when broken. Wait for PML break BEFORE going short. PML becomes RESISTANCE after broken. Break PDL + PML both = strong puts signal." },
  { rank: 5, name: "VWAP", full: "VWAP",             note: "Want price BELOW 200 EMA before entering puts — avoid 200 EMA bounces. Above VWAP = bullish bias." },
];

const DAY_TYPES = [
  { signal: "PDH + PMH both broken", type: "STRONGEST BULL 🔥🔥", action: "CALLS — buyers in total control. Join the trend, never short." },
  { signal: "PDH broken", type: "BULL TREND 🔥", action: "Favor CALLS until next resistance zone." },
  { signal: "PMH broken only", type: "BREAKOUT WATCH ⚡", action: "First bullish sign. Watch for PDH break next. Calls on 13 EMA dip." },
  { signal: "Between PML and PMH", type: "CHOP ZONE 🟡", action: "Avoid. Wait for expansion above PMH or below PML." },
  { signal: "PML broken only", type: "BREAKDOWN WATCH ⚡", action: "First bearish sign. Watch for PDL break next. Puts on 13 EMA bounce." },
  { signal: "PDL broken", type: "BEAR TREND 🔴", action: "Favor PUTS until next support zone." },
  { signal: "Holds all 4 levels", type: "BALANCED DAY ➖", action: "Range day. Cautious, reduced size. Play PDH→PDL bounces only." },
];

const CASEY_RULES = [
  { rule: "Step 1: Mark 4 Levels", detail: "Every morning before open mark ALL 4: PDH, PDL, PMH, PML. Casey: 'These 4 levels tell the story for the day. Crystal clear picture of what is happening.'" },
  { rule: "Step 2: Day Type", detail: "PDH+PMH both broken = strongest bull signal. PDH break = bull trend. PMH break only = first bullish sign. PML→PMH range = chop, avoid. PML break = first bearish. PDL break = bear trend." },
  { rule: "Scanner Rule", detail: "Best way to scan: break of BOTH PDH AND PMH = A+ calls. AMD example: broke PMH+PDH → flagged to 13 EMA → winner. Never short breaking resistance." },
  { rule: "Zone Numbering (Price Targets)", detail: "Zone 1 = PDH (breakout point). Zone 2 = next resistance above (first target). Zone 3 = next resistance above Zone 2. 'No resistance between zones = explosive moves.' Draw zones from wick to following candle body." },
  { rule: "Price Structure (HH/HL/LH/LL)", detail: "HH+HL = bullish = NO SHORTING. LH+LL = bearish = NO LONGING. Don't time tops or bottoms — wait for structure SHIFT. Bull flags = calls entry. Bear flags = puts entry. First flag after shift = best entry." },
  { rule: "Demand Zone Formula", detail: "PDH + PML together define next day's demand zone. SPY example: 'Used Previous Day High and Pre Market Low to create today's demand zone.'" },
  { rule: "Supply/Demand Range", detail: "Demand→Supply move = Bull Flag forms along the way → calls on break. Supply→Demand move = Bear Flag forms → puts on break. Flags are your entries within the range." },
  { rule: "Step 2: Map S&D Zones", detail: "Before open: mark supply zone (HOD), demand zone (LOD), intraday zones, and S/R flips from prior session. These are your targets AND your entry zones." },
  { rule: "Step 3: Zone Play Type", detail: "3 ways to play a zone: (1) Breakout — strong break through, enter on break. (2) Rejection — bounce back from zone. (3) Break & Retest — Casey's FAVORITE: breaks zone, retests, holds, enter on hold." },
  { rule: "Step 4: EMA Fan", detail: "13/48/200 must align and SPACE OUT. Bullish: 13>48>200. Bearish: 200>48>13. Closely spaced/crossing = chop = no trade. EMAs also act as dynamic S/R for 2-min entries." },
  { rule: "Step 5: Structure Confirm", detail: "Bearish: PDH rejection + lower high on first bounce = structure confirmed. Bullish: PDL hold + higher low on first pullback = structure confirmed." },
  { rule: "Step 6: 15min Gate", detail: "15min candle BODY (not wick) close above PMH = calls confirmed. Below PML = puts confirmed. This is the final gate before entry." },
  { rule: "Step 7: Pattern + Entry", detail: "Look for bear flag, bull flag, falling wedge, or rejection candle at the zone. Enter on 2-min 13 EMA dip/pullback after pattern confirms. This gives you a clear risk level." },
  { rule: "Step 8: Zone-Based Exits", detail: "Scale out HEAVY at next supply/demand zone — don't give back profits on bounces. Trail runners with 13 EMA. Use zones as targets WHILE in the trade." },
  { rule: "Below PDL = Runners", detail: '"Under the PDL is where the runners go nuts." Casey made 10x on runners below PDL. Scale most out at PDL, let small size run below.' },
  { rule: "Only 4 Red Days in 2 Months", detail: "Casey's documented result using this exact process. The key: map zones pre-market, wait for EMA fan, confirm with 15min gate, enter on 2-min 13 EMA pullback." },
];

const HOLES_FIXED = [
  { hole: "No day type read", fix: "Classify PDH/PDL break every morning FIRST — sets the bias for the whole day" },
  { hole: "Fake breakout", fix: "Require 15min candle BODY close above PMH/PML — not just a wick" },
  { hole: "No structure confirm", fix: "PDH rejection alone isn't enough — wait for lower high to confirm bearish structure" },
  { hole: "Missing zone plays", fix: "3 entries now: breakout, rejection, AND break & retest (Casey's favorite)" },
  { hole: "No pattern filter", fix: "Require candlestick pattern at zone — flag, wedge, or rejection candle" },
  { hole: "Chop entry", fix: "EMA fan spacing check — closely spaced/crossing EMAs = no trade" },
  { hole: "Giving back profits", fix: "Zone-based exits: scale out heavy at next S/D zone, don't hold through bounces" },
  { hole: "PDH/PMH squeeze", fix: "PDH and PMH within 0.2% = balanced day = reduced size or skip" },
  { hole: "Late entries", fix: "Hard cutoff 3:45pm ET for 0DTE — theta decay kills late entries" },
  { hole: "No exit plan", fix: "Profit target + stop + zone-based scale out + 3:45pm force close" },
];

const catColors = {
  EMA: "#00C896", "15MIN": "#FFB800", LEVEL: "#FF6B6B",
  ENTRY: "#7C83FD", VOL: "#A78BFA", VWAP: "#34D399", AIR: "#60A5FA"
};

export default function ZeroDTE() {
  const [tab, setTab] = useState("system");
  const [direction, setDirection] = useState("BULLISH");

  const tabs = [
    { id: "system",  label: "⚙️ System" },
    { id: "casey",   label: "📐 Casey Rules" },
    { id: "scoring", label: "🎯 Scoring" },
    { id: "holes",   label: "🔧 Holes Fixed" },
  ];

  return (
    <div style={{
      background: "#080C14",
      minHeight: "100vh",
      color: "#E2E8F0",
      fontFamily: "'JetBrains Mono', monospace",
      padding: "20px 16px",
    }}>
      <div style={{ maxWidth: 800, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 26 }}>🎯</span>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#FFF", letterSpacing: "0.04em" }}>
                KEVIN'S 0DTE SYSTEM
              </div>
              <div style={{ fontSize: 10, color: "#4B5563", letterSpacing: "0.1em" }}>
                CASEY EMA FAN × CONFLUENCE SCORING × SPY/QQQ/IWM
              </div>
            </div>
          </div>

          {/* Stats bar */}
          <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
            {[
              { l: "INSTRUMENTS", v: "SPY · QQQ · IWM" },
              { l: "WINDOW", v: "9:45am – 3:45pm ET" },
              { l: "TARGET", v: "+25% premium" },
              { l: "STOP", v: "-25% premium" },
              { l: "SIZE", v: "$15/trade" },
              { l: "MIN SCORE", v: "5/10 (prime: 7)" },
            ].map((s, i) => (
              <div key={i} style={{
                background: "#0F1724",
                border: "1px solid #1E2A3A",
                borderRadius: 6,
                padding: "4px 10px",
                fontSize: 10,
              }}>
                <span style={{ color: "#4B5563" }}>{s.l}: </span>
                <span style={{ color: "#E2E8F0", fontWeight: 600 }}>{s.v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 6, marginBottom: 20, flexWrap: "wrap" }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              background: tab === t.id ? "#1E3A5F" : "transparent",
              border: `1px solid ${tab === t.id ? "#3B82F6" : "#1E2A3A"}`,
              borderRadius: 8,
              color: tab === t.id ? "#93C5FD" : "#6B7280",
              fontSize: 11,
              padding: "7px 14px",
              cursor: "pointer",
              fontFamily: "inherit",
              fontWeight: tab === t.id ? 700 : 400,
            }}>{t.label}</button>
          ))}
        </div>

        {/* ── SYSTEM TAB ── */}
        {tab === "system" && (
          <div>
            {/* Direction toggle */}
            <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
              {["BULLISH", "BEARISH"].map(d => (
                <button key={d} onClick={() => setDirection(d)} style={{
                  flex: 1,
                  background: direction === d
                    ? (d === "BULLISH" ? "#00C89622" : "#FF4A4A22")
                    : "transparent",
                  border: `1px solid ${direction === d
                    ? (d === "BULLISH" ? "#00C896" : "#FF4A4A")
                    : "#1E2A3A"}`,
                  borderRadius: 8,
                  color: direction === d
                    ? (d === "BULLISH" ? "#00C896" : "#FF4A4A")
                    : "#4B5563",
                  fontSize: 12,
                  padding: "10px",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  fontWeight: 700,
                }}>
                  {d === "BULLISH" ? "📈 BULLISH — CALLS" : "📉 BEARISH — PUTS"}
                </button>
              ))}
            </div>

            {/* EMA Fan Visual */}
            <div style={{
              background: "#0F1724",
              border: `1px solid ${direction === "BULLISH" ? "#00C89644" : "#FF4A4A44"}`,
              borderRadius: 10,
              padding: "16px",
              marginBottom: 16,
            }}>
              <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 12, letterSpacing: "0.08em" }}>
                EMA FAN — {direction}
              </div>
              {direction === "BULLISH" ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {[
                    { ema: "13 EMA", pos: "TOP", color: "#FFD700", note: "Price bounces here on dips → entry" },
                    { ema: "48 EMA", pos: "MIDDLE", color: "#A855F7", note: "Mid support, trend confirmation" },
                    { ema: "200 EMA", pos: "BOTTOM", color: "#EF4444", note: "Major support floor" },
                  ].map((e, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 60, height: 3, background: e.color, borderRadius: 2 }} />
                      <span style={{ fontSize: 11, color: e.color, minWidth: 60 }}>{e.ema}</span>
                      <span style={{ fontSize: 10, color: "#6B7280" }}>{e.pos} — {e.note}</span>
                    </div>
                  ))}
                  <div style={{ fontSize: 10, color: "#00C896", marginTop: 6 }}>
                    ✅ EMAs spread apart = momentum confirmed → buy 13 EMA dips
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {[
                    { ema: "200 EMA", pos: "TOP", color: "#EF4444", note: "Major resistance ceiling" },
                    { ema: "48 EMA", pos: "MIDDLE", color: "#A855F7", note: "Mid resistance, trend confirmation" },
                    { ema: "13 EMA", pos: "BOTTOM", color: "#FFD700", note: "Price bounces up here → puts entry" },
                  ].map((e, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 60, height: 3, background: e.color, borderRadius: 2 }} />
                      <span style={{ fontSize: 11, color: e.color, minWidth: 60 }}>{e.ema}</span>
                      <span style={{ fontSize: 10, color: "#6B7280" }}>{e.pos} — {e.note}</span>
                    </div>
                  ))}
                  <div style={{ fontSize: 10, color: "#FF4A4A", marginTop: 6 }}>
                    ✅ EMAs spread apart downward = momentum confirmed → sell 13 EMA bounces
                  </div>
                </div>
              )}
            </div>

            {/* Key Levels */}
            <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 10, padding: "16px", marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 12, letterSpacing: "0.08em" }}>KEY LEVELS (PRIORITY ORDER)</div>
              {LEVELS.map((l, i) => (
                <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8, alignItems: "flex-start" }}>
                  <span style={{
                    background: "#1E2A3A", color: "#93C5FD",
                    borderRadius: 4, padding: "1px 6px", fontSize: 10, minWidth: 16, textAlign: "center"
                  }}>{l.rank}</span>
                  <span style={{ color: "#F59E0B", fontSize: 12, fontWeight: 700, minWidth: 44 }}>{l.name}</span>
                  <div>
                    <div style={{ fontSize: 11, color: "#9CA3AF" }}>{l.full}</div>
                    <div style={{ fontSize: 10, color: "#6B7280" }}>{l.note}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Day Types */}
        <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 10, padding: "16px", marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 12, letterSpacing: "0.08em" }}>
            DAY TYPE SIGNALS (read at open)
          </div>
          {DAY_TYPES.map((d, i) => (
            <div key={i} style={{ marginBottom: 8, padding: "8px 12px", background: "#080C14", borderRadius: 6, borderLeft: `3px solid ${d.type.includes("🔥🔥") ? "#FF6B00" : d.type.includes("🔥") ? "#00C896" : d.type.includes("🟡") ? "#FFB800" : d.type.includes("🔴") ? "#FF4757" : d.type.includes("⚡") ? "#7C83FD" : "#4B5563"}` }}>
              <div style={{ fontSize: 10, color: "#9CA3AF", marginBottom: 2 }}>IF: {d.signal}</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#E2E8F0", marginBottom: 2 }}>{d.type}</div>
              <div style={{ fontSize: 10, color: "#6B7280" }}>{d.action}</div>
            </div>
          ))}
        </div>

        {/* Hard Vetos */}
            <div style={{ background: "#1A0A0A", border: "1px solid #7F1D1D", borderRadius: 10, padding: "16px" }}>
              <div style={{ fontSize: 11, color: "#EF4444", marginBottom: 10, letterSpacing: "0.08em" }}>🚫 HARD VETOS — AUTO SCORE 0</div>
              {VETOS.map((v, i) => (
                <div key={i} style={{ fontSize: 11, color: "#FCA5A5", marginBottom: 5, paddingLeft: 8, borderLeft: "2px solid #7F1D1D" }}>
                  {v}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── CASEY RULES TAB ── */}
        {tab === "casey" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {CASEY_RULES.map((r, i) => (
              <div key={i} style={{
                background: "#0F1724",
                border: "1px solid #1E2A3A",
                borderRadius: 10,
                padding: "14px 16px",
              }}>
                <div style={{ fontSize: 12, color: "#FFB800", fontWeight: 700, marginBottom: 4 }}>{r.rule}</div>
                <div style={{ fontSize: 12, color: "#CBD5E1", lineHeight: 1.6 }}>{r.detail}</div>
              </div>
            ))}
          </div>
        )}

        {/* ── SCORING TAB ── */}
        {tab === "scoring" && (
          <div>
            <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 10, padding: "16px", marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 14, letterSpacing: "0.08em" }}>CONFLUENCE POINTS (0–10)</div>
              {CONFLUENCE.map((c, i) => (
                <div key={i} style={{ display: "flex", gap: 10, marginBottom: 10, alignItems: "flex-start" }}>
                  <span style={{
                    background: catColors[c.cat] + "33",
                    color: catColors[c.cat],
                    border: `1px solid ${catColors[c.cat]}66`,
                    borderRadius: 4, padding: "1px 7px",
                    fontSize: 11, fontWeight: 700, minWidth: 28, textAlign: "center"
                  }}>{c.pts}</span>
                  <div>
                    <span style={{
                      background: "#1E2A3A", color: catColors[c.cat],
                      borderRadius: 3, padding: "1px 6px", fontSize: 9,
                      letterSpacing: "0.06em", marginRight: 6
                    }}>{c.cat}</span>
                    <span style={{ fontSize: 11, color: "#CBD5E1" }}>{c.label}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Score legend */}
            <div style={{ background: "#0F1724", border: "1px solid #1E2A3A", borderRadius: 10, padding: "16px" }}>
              <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 12, letterSpacing: "0.08em" }}>SCORE INTERPRETATION</div>
              {[
                { range: "7–10", label: "🔥 PRIME SETUP", color: "#00C896", action: "Enter 0DTE — full $15 position" },
                { range: "5–6",  label: "⚡ DEVELOPING", color: "#FFB800", action: "Watch — wait for one more confirmation" },
                { range: "3–4",  label: "🔎 BUILDING",   color: "#6B7280", action: "On radar — EMA fan not fully formed" },
                { range: "0–2",  label: "🚫 NO TRADE",   color: "#EF4444", action: "Hard veto triggered or no momentum" },
              ].map((s, i) => (
                <div key={i} style={{
                  display: "flex", gap: 10, marginBottom: 8,
                  padding: "8px 12px",
                  background: s.color + "11",
                  border: `1px solid ${s.color}33`,
                  borderRadius: 8,
                }}>
                  <span style={{ color: s.color, fontSize: 13, fontWeight: 700, minWidth: 32 }}>{s.range}</span>
                  <div>
                    <div style={{ fontSize: 12, color: s.color, fontWeight: 600 }}>{s.label}</div>
                    <div style={{ fontSize: 10, color: "#9CA3AF" }}>{s.action}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── HOLES FIXED TAB ── */}
        {tab === "holes" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 4, letterSpacing: "0.08em" }}>
              HOLES IN ORIGINAL SYSTEM — NOW PLUGGED
            </div>
            {HOLES_FIXED.map((h, i) => (
              <div key={i} style={{
                background: "#0F1724",
                border: "1px solid #1E2A3A",
                borderRadius: 10,
                padding: "14px 16px",
              }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>🔧</span>
                  <span style={{ fontSize: 12, color: "#EF4444", fontWeight: 700 }}>HOLE: {h.hole}</span>
                </div>
                <div style={{ fontSize: 11, color: "#86EFAC", paddingLeft: 22 }}>
                  ✅ FIX: {h.fix}
                </div>
              </div>
            ))}

            <div style={{
              background: "#0A1A0A",
              border: "1px solid #166534",
              borderRadius: 10,
              padding: "14px 16px",
              marginTop: 8,
            }}>
              <div style={{ fontSize: 11, color: "#4ADE80", marginBottom: 8, letterSpacing: "0.06em", fontWeight: 700 }}>
                ▶ RUN THE COMBINED SYSTEM
              </div>
              <div style={{ fontSize: 11, color: "#6B7280", lineHeight: 2 }}>
                <div><span style={{color:"#4ADE80"}}>python kevin_0dte_system.py</span> — analysis only</div>
                <div><span style={{color:"#FFB800"}}>python kevin_0dte_system.py --trade</span> — dry run</div>
                <div><span style={{color:"#EF4444"}}>python kevin_0dte_system.py --live</span> — real orders</div>
                <div style={{marginTop:6}}><span style={{color:"#4ADE80"}}>python scheduler.py --trade</span> — auto every 5min</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
