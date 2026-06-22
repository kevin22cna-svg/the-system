import { useState } from "react";

const WATCHLIST = {
  tier1: {
    label: "Tier 1 — Mid-Range ($10–$90)",
    color: "#00C896",
    emoji: "🚀",
    description: "Stronger liquidity, options available, cleanest entries. Includes airlines, pharma, pipeline.",
    stocks: [
      { sym: "SPCX",  sector: "Space",      why: "SpaceX IPO proxy, massive retail momentum" },
      { sym: "LUNR",  sector: "Space",      why: "NASA contracts, launches on SpaceX rockets" },
      { sym: "ASTS",  sector: "Space",      why: "Satellite broadband, high beta space play" },
      { sym: "RKLB",  sector: "Space",      why: "Direct SpaceX competitor, growing launch cadence" },
      { sym: "AAL",   sector: "Airlines",   why: "Low float airline, macro/oil catalyst sensitive" },
      { sym: "DAL",   sector: "Airlines",   why: "Delta — premium airline, earnings & travel demand catalyst" },
      { sym: "CCL",   sector: "Cruise",     why: "Carnival Cruise — travel demand, oil price sensitive, high volume" },
      { sym: "BMY",   sector: "Pharma",     why: "Bristol-Myers — pipeline catalysts, dividend + momentum play" },
      { sym: "KMI",   sector: "Pipeline",   why: "Kinder Morgan — nat gas infrastructure, rate/energy catalyst" },
      { sym: "SOFI",  sector: "Fintech",    why: "High volume daily mover, earnings catalyst" },
      { sym: "NU",    sector: "Fintech",    why: "Latam fintech growth, vol surge patterns" },
      { sym: "HOOD",  sector: "Fintech",    why: "Robinhood itself — crypto/retail sentiment play" },
      { sym: "RIVN",  sector: "EV",         why: "EV delivery numbers, high retail interest" },
      { sym: "PLTR",  sector: "AI/Tech",    why: "Gov contracts + AI — confirmed momentum name" },
      { sym: "SOUN",  sector: "AI/Tech",    why: "Voice AI, low float, explosive on news" },
      { sym: "BBAI",  sector: "AI/Tech",    why: "Defense AI contracts, small cap breakouts" },
      { sym: "PLUG",  sector: "Clean Energy", why: "Hydrogen fuel cells, sector sentiment mover" },
      { sym: "TELL",  sector: "LNG",        why: "LNG export catalyst, energy macro play" },
      { sym: "JOBY",  sector: "Air Taxi",   why: "FAA approvals = explosive moves" },
      { sym: "OPEN",  sector: "PropTech",   why: "Housing market sentiment, low price breakouts" },
      { sym: "RKT",   sector: "Mortgage",   why: "Rate-sensitive, big moves on Fed news" },
    ]
  },
  tier2: {
    label: "Tier 2 — Penny Stocks ($0.50–$10)",
    color: "#FFB800",
    emoji: "⚡",
    description: "Low float = violent moves. Need strong catalyst + 3x+ volume",
    stocks: [
      { sym: "MDAI",  sector: "Biotech",    why: "AI diagnostics, strong buy signals noted" },
      { sym: "CMPS",  sector: "Biotech",    why: "Psilocybin therapy, FDA catalyst watch" },
      { sym: "MARA",  sector: "Crypto",     why: "Bitcoin miner, moves with BTC price" },
      { sym: "RIOT",  sector: "Crypto",     why: "BTC mining, high volume on crypto rallies" },
      { sym: "CLSK",  sector: "Crypto",     why: "Clean BTC mining, energy efficiency angle" },
      { sym: "WULF",  sector: "Crypto",     why: "Nuclear-powered mining, unique catalyst" },
      { sym: "CIFR",  sector: "Crypto",     why: "Low float crypto miner, explosive on BTC pumps" },
      { sym: "HIMS",  sector: "Health",     why: "Telehealth + GLP-1, strong revenue growth" },
      { sym: "AGEN",  sector: "Biotech",    why: "Immuno-oncology, FDA catalyst pending" },
      { sym: "SIGA",  sector: "Biotech",    why: "Gov stockpile contracts, defensive biotech" },
      { sym: "GCTS",  sector: "AI/Tech",    why: "AI analytics, breakout signals flagged" },
      { sym: "ITRM",  sector: "Biotech",    why: "Antibiotic pipeline, binary FDA events" },
      { sym: "NKLA",  sector: "EV",         why: "Hydrogen trucks, high short interest" },
      { sym: "HIVE",  sector: "Crypto",     why: "Green BTC/ETH miner, sector momentum" },
      { sym: "UWMC",  sector: "Mortgage",   why: "Rate-cut beneficiary, vol spikes on Fed days" },
    ]
  },
  tier3: {
    label: "Tier 3 — Micro Caps (<$1)",
    color: "#FF4757",
    emoji: "🎯",
    description: "Ultra high risk. Tiny position sizes only. News-driven explosions",
    stocks: [
      { sym: "QBTS",  sector: "Quantum",    why: "Quantum computing, extremely low float" },
      { sym: "IONQ",  sector: "Quantum",    why: "Quantum leader, Google/AWS partnerships" },
      { sym: "KULR",  sector: "CleanTech",  why: "Thermal mgmt tech, NASA contracts" },
      { sym: "ATOS",  sector: "Biotech",    why: "Breast cancer treatment, binary events" },
      { sym: "CANF",  sector: "Biotech",    why: "Kidney disease treatment, low float" },
      { sym: "STSS",  sector: "AI/Tech",    why: "Streaming tech, high short squeeze potential" },
    ]
  }
};

const PENNY_FILTERS = [
  { label: "Price",        value: "$0.50 – $10.00 (penny range)" },
  { label: "Market Cap",   value: "Under $300M (micro/small cap)" },
  { label: "Float",        value: "Under 20M shares (supernova: <10M)" },
  { label: "Avg Volume",   value: "> 500K daily (must be tradeable)" },
  { label: "Rel. Volume",  value: "> 2x average (RVOL — fresh catalyst)" },
  { label: "Day Change",   value: "Up 2%+ minimum (momentum filter)" },
];

const SCORING = [
  { pts: "+2", crit: "Relative volume > 2x avg (RVOL confirmed — real demand)" },
  { pts: "+2", crit: "Float under 20M shares (low float = explosive moves)" },
  { pts: "+2", crit: "Up 5%+ today OR gapped up pre-market (momentum)" },
  { pts: "+2", crit: "Real catalyst: FDA, earnings, contract, PR, short squeeze" },
  { pts: "+1", crit: "Price above short-term moving average (uptrend structure)" },
  { pts: "+1", crit: "Breaking key resistance level on volume" },
];

export default function ExplosionScanner() {
  const [activeTab, setActiveTab] = useState("tier1");
  const [search, setSearch] = useState("");
  const [showScoring, setShowScoring] = useState(false);

  const tier = WATCHLIST[activeTab];

  const filtered = tier.stocks.filter(s =>
    s.sym.toLowerCase().includes(search.toLowerCase()) ||
    s.sector.toLowerCase().includes(search.toLowerCase()) ||
    s.why.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{
      background: "#0A0E1A",
      minHeight: "100vh",
      fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      color: "#E8EAF0",
      padding: "24px 16px"
    }}>
      {/* Header */}
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
            <span style={{ fontSize: 28 }}>🔥</span>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: "0.05em", color: "#FFFFFF" }}>
              EXPLOSION SCANNER
            </h1>
          </div>
          <p style={{ margin: 0, fontSize: 12, color: "#6B7280", letterSpacing: "0.08em" }}>
            FINANCIAL + TECHNICAL CONFLUENCE · {Object.values(WATCHLIST).reduce((a, t) => a + t.stocks.length, 0)} TICKERS TRACKED
          </p>
        </div>

        {/* Scoring Toggle */}
        <button
          onClick={() => setShowScoring(!showScoring)}
          style={{
            background: showScoring ? "#1A1F2E" : "transparent",
            border: "1px solid #2A3040",
            borderRadius: 8,
            color: "#9CA3AF",
            fontSize: 11,
            padding: "6px 14px",
            cursor: "pointer",
            marginBottom: 16,
            letterSpacing: "0.06em"
          }}
        >
          {showScoring ? "▲ HIDE" : "▼ SHOW"} SCORING SYSTEM
        </button>

        {showScoring && (
          <div style={{
            background: "#111827",
            border: "1px solid #2A3040",
            borderRadius: 10,
            padding: "16px 20px",
            marginBottom: 20
          }}>
            <p style={{ margin: "0 0 10px", fontSize: 11, color: "#FFB800", letterSpacing: "0.08em", fontWeight: 700 }}>
              ⚡ PENNY STOCK SCREENER FILTERS
            </p>
            {PENNY_FILTERS.map((f, i) => (
              <div key={i} style={{ display: "flex", gap: 10, marginBottom: 5, alignItems: "flex-start" }}>
                <span style={{ fontSize: 11, color: "#FFB800", minWidth: 90, fontWeight: 600 }}>{f.label}</span>
                <span style={{ fontSize: 11, color: "#9CA3AF" }}>{f.value}</span>
              </div>
            ))}
            <div style={{ borderTop: "1px solid #2A3040", margin: "12px 0" }} />
            <p style={{ margin: "0 0 10px", fontSize: 11, color: "#00C896", letterSpacing: "0.08em", fontWeight: 700 }}>
              🔥 CONFLUENCE SCORE (0–10) — NEED 7+ TO TRADE
            </p>
            {SCORING.map((s, i) => (
              <div key={i} style={{ display: "flex", gap: 12, marginBottom: 6, alignItems: "flex-start" }}>
                <span style={{
                  background: "#00C896",
                  color: "#000",
                  borderRadius: 4,
                  padding: "1px 6px",
                  fontSize: 11,
                  fontWeight: 700,
                  minWidth: 28,
                  textAlign: "center"
                }}>{s.pts}</span>
                <span style={{ fontSize: 12, color: "#D1D5DB", lineHeight: 1.5 }}>{s.crit}</span>
              </div>
            ))}
            <div style={{ borderTop: "1px solid #2A3040", margin: "12px 0" }} />
            <p style={{ margin: "0 0 6px", fontSize: 11, color: "#6B7280", letterSpacing: "0.06em" }}>CONVICTION LEVELS</p>
            <div style={{ fontSize: 11, color: "#D1D5DB", lineHeight: 2 }}>
              <span style={{color:"#FF4757"}}>🔥 SUPERNOVA</span> — Score 8–10 · Float &lt;10M + RVOL &gt;5x + catalyst · Potential 50–200% move<br/>
              <span style={{color:"#00C896"}}>✅ HIGH</span> — Score 7 · Good setup · Auto-trade $15 position<br/>
              <span style={{color:"#FFB800"}}>⚡ WATCH</span> — Score 5–6 · Building momentum · Monitor next scan<br/>
              <span style={{color:"#6B7280"}}>🔎 RADAR</span> — Score &lt;5 · Not ready yet
            </div>
          </div>
        )}

        {/* Tier Tabs */}
        <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          {Object.entries(WATCHLIST).map(([key, t]) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              style={{
                flex: 1,
                background: activeTab === key ? t.color + "22" : "transparent",
                border: `1px solid ${activeTab === key ? t.color : "#2A3040"}`,
                borderRadius: 8,
                color: activeTab === key ? t.color : "#6B7280",
                fontSize: 11,
                padding: "8px 4px",
                cursor: "pointer",
                fontFamily: "inherit",
                fontWeight: activeTab === key ? 700 : 400,
                letterSpacing: "0.04em",
                transition: "all 0.15s"
              }}
            >
              {t.emoji} T{key.slice(-1)}
              <div style={{ fontSize: 10, marginTop: 2, opacity: 0.7 }}>{t.stocks.length} stocks</div>
            </button>
          ))}
        </div>

        {/* Tier Header */}
        <div style={{
          background: tier.color + "11",
          border: `1px solid ${tier.color}44`,
          borderRadius: 10,
          padding: "12px 16px",
          marginBottom: 16
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: tier.color, marginBottom: 2 }}>
            {tier.label}
          </div>
          <div style={{ fontSize: 11, color: "#9CA3AF" }}>{tier.description}</div>
        </div>

        {/* Search */}
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search ticker, sector, keyword..."
          style={{
            width: "100%",
            background: "#111827",
            border: "1px solid #2A3040",
            borderRadius: 8,
            color: "#E8EAF0",
            fontSize: 12,
            padding: "10px 14px",
            marginBottom: 16,
            fontFamily: "inherit",
            boxSizing: "border-box",
            outline: "none"
          }}
        />

        {/* Stock Cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {filtered.map((s, i) => (
            <div
              key={s.sym}
              style={{
                background: "#111827",
                border: "1px solid #1E2A3A",
                borderRadius: 10,
                padding: "12px 16px",
                display: "flex",
                alignItems: "flex-start",
                gap: 14,
                transition: "border-color 0.15s"
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = tier.color + "66"}
              onMouseLeave={e => e.currentTarget.style.borderColor = "#1E2A3A"}
            >
              <div style={{
                background: tier.color + "22",
                border: `1px solid ${tier.color}44`,
                borderRadius: 6,
                padding: "6px 10px",
                minWidth: 56,
                textAlign: "center"
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: tier.color }}>{s.sym}</div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{
                  display: "inline-block",
                  background: "#1E2A3A",
                  borderRadius: 4,
                  padding: "1px 8px",
                  fontSize: 10,
                  color: "#9CA3AF",
                  letterSpacing: "0.06em",
                  marginBottom: 4
                }}>
                  {s.sector}
                </div>
                <div style={{ fontSize: 12, color: "#D1D5DB", lineHeight: 1.5 }}>{s.why}</div>
              </div>
            </div>
          ))}
        </div>

        {filtered.length === 0 && (
          <div style={{ textAlign: "center", color: "#4B5563", padding: "32px 0", fontSize: 13 }}>
            No matches for "{search}"
          </div>
        )}

        {/* Footer */}
        <div style={{
          marginTop: 28,
          padding: "14px 0",
          borderTop: "1px solid #1E2A3A",
          fontSize: 10,
          color: "#4B5563",
          lineHeight: 1.8,
          letterSpacing: "0.04em"
        }}>
          <div>📡 Run <code style={{color:"#6B7280"}}>python explosion_scanner.py</code> to score all tickers live</div>
          <div>🎯 Run <code style={{color:"#6B7280"}}>python explosion_scanner.py --trade</code> to auto-buy best mover (dry run)</div>
          <div>⚠️  Run <code style={{color:"#6B7280"}}>python explosion_scanner.py --live</code> for real money execution</div>
        </div>
      </div>
    </div>
  );
}
