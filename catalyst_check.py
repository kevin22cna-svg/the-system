"""
catalyst_check.py  --  Step 0 of the Wiley Strat premarket routine.

Runs BEFORE regime_gate.py. Decides whether a known high-impact event
(econ release or voting-member Fed speech) lands before the cash session's
risk window closes. If so, it sets bearish_catalyst_pending = True, which
forces regime_gate.determine_regime() to output NO_TRADE.

Design note (read this):
    There is no clean free API for the Fed *speaker* schedule, and the
    econ-calendar feeds (the same data ForexFactory shows) only cover
    releases, not speeches. So this module does NOT scrape anything.
    Instead, Claude populates today's events during the "good morning
    let's get started" pull (web search of the econ calendar + Fed
    speaker schedule) and passes them in here. This file owns the
    *rules* -- impact classification, timing, the 2pm cutoff, and the
    post-event settle window. That logic is deterministic and testable;
    the data fetch stays with Claude, who can read the live roster.

    The flag is named "bearish_catalyst_pending" to match the existing
    regime_gate.py signature, but a catalyst is BIDIRECTIONAL risk -- it
    vetoes the session in either direction. Don't trade into a binary.

Usage in the morning routine:
    events = [
        Event("CPI", time_et=time(8, 30)),
        Event("Fed Chair speech", time_et=time(12, 30), is_fed_speaker=True,
              speaker_is_voter=True),
    ]
    result = evaluate_catalysts(events)
    # -> feed result.bearish_catalyst_pending into determine_regime(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# Config -- tune these after watching it run a few sessions.
# ---------------------------------------------------------------------------

# Risk window closes at 2:00pm ET by default. Any flagged event landing
# at/before this time gates the session. (FOMC decisions hit at 2pm; this
# is also when 0DTE EMA fans tend to flip on Fed days.)
CUTOFF_HOUR_ET = 14
CUTOFF_MINUTE_ET = 0

# After an event prints, how long to keep the veto on before the tape is
# considered "settled" and you can trade the reaction.
SETTLE_MINUTES = 15

# Substrings that mark a release as high-impact (case-insensitive match on
# the event name). Keep this list tight -- only genuine market-movers.
HIGH_IMPACT_KEYWORDS = (
    "cpi", "core cpi",
    "ppi", "core ppi",
    "pce", "core pce",
    "nfp", "nonfarm", "non-farm", "jobs report", "employment situation",
    "unemployment rate",
    "fomc", "rate decision", "interest rate decision",
    "gdp",
    "retail sales",
    "ism manufacturing", "ism services", "ism non-manufacturing",
    "jolts",
)

# Fallback roster of FOMC voting seats. The primary path is to pass
# speaker_is_voter explicitly (Claude reads the live roster during the
# morning pull). This set is only a backstop and MUST be verified at the
# start of each calendar year -- the four rotating Reserve Bank seats
# change every January.
#
#   VERIFY ANNUALLY against the current FOMC roster before relying on it.
#
FOMC_VOTER_SEATS = {
    "fed chair",
    "chair",
    "fed vice chair",
    "vice chair",
    "vice chair for supervision",
    "new york fed",  # NY Fed president holds a permanent vote
    "ny fed",
}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """A single scheduled item for today.

    name:             free text, e.g. "CPI" or "Fed Chair speech".
    time_et:          datetime.time in ET, or None if all-day / unknown.
    is_fed_speaker:   True if this is a Fed official speaking.
    speaker_is_voter: True if that speaker currently holds an FOMC vote.
                      Leave as None to fall back to FOMC_VOTER_SEATS matching
                      on the name.
    """
    name: str
    time_et: time | None = None
    is_fed_speaker: bool = False
    speaker_is_voter: bool | None = None


@dataclass
class CatalystResult:
    bearish_catalyst_pending: bool          # feed straight into determine_regime
    veto: bool                              # alias, reads naturally in logs
    reasons: list[str] = field(default_factory=list)
    triggering_events: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.veto:
            return "CATALYST CHECK: clear -> no veto, regime gate runs normally"
        lines = ["CATALYST CHECK: VETO -> regime gate will output NO_TRADE"]
        for r in self.reasons:
            lines.append(f"  - {r}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------

def is_high_impact(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in HIGH_IMPACT_KEYWORDS)


def _speaker_votes(ev: Event) -> bool:
    if ev.speaker_is_voter is not None:
        return ev.speaker_is_voter
    n = ev.name.lower()
    return any(seat in n for seat in FOMC_VOTER_SEATS)


def evaluate_catalysts(
    events: list[Event],
    now_et: datetime | None = None,
    cutoff_hour: int = CUTOFF_HOUR_ET,
    cutoff_minute: int = CUTOFF_MINUTE_ET,
    settle_minutes: int = SETTLE_MINUTES,
) -> CatalystResult:
    """Return whether today's schedule should veto the session.

    An event vetoes if BOTH:
      1. It matters -- a high-impact release, or a voting-member Fed speech.
      2. It is still "live" relative to now -- it hasn't already printed and
         settled, and it lands at/before the cutoff (default 2pm ET).
    """
    if now_et is None:
        now_et = datetime.now(ET)

    cutoff = now_et.replace(hour=cutoff_hour, minute=cutoff_minute,
                            second=0, microsecond=0)

    reasons: list[str] = []
    triggers: list[str] = []

    for ev in events:
        # 1. Does it matter?
        if is_high_impact(ev.name):
            kind = "high-impact release"
        elif ev.is_fed_speaker and _speaker_votes(ev):
            kind = "voting-member Fed speech"
        else:
            continue  # low-impact data or non-voting speaker -> ignore

        # 2. Is it still live?
        if ev.time_et is None:
            # Unknown/all-day time -> treat as pending to be safe.
            reasons.append(f"{ev.name} ({kind}, time TBD -> veto to be safe)")
            triggers.append(ev.name)
            continue

        ev_dt = now_et.replace(hour=ev.time_et.hour, minute=ev.time_et.minute,
                               second=0, microsecond=0)

        # Already printed and settled -> trade the reaction, no veto.
        if now_et >= ev_dt + timedelta(minutes=settle_minutes):
            continue

        # Lands after the risk window closes -> doesn't gate the open.
        if ev_dt > cutoff:
            continue

        when = ev_dt.strftime("%-I:%M%p ET") if hasattr(ev_dt, "strftime") else str(ev_dt)
        reasons.append(f"{ev.name} ({kind}) at {when} -> before {cutoff.strftime('%-I:%M%p ET')} cutoff")
        triggers.append(ev.name)

    veto = len(triggers) > 0
    return CatalystResult(
        bearish_catalyst_pending=veto,
        veto=veto,
        reasons=reasons,
        triggering_events=triggers,
    )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Pretend it's 7:45am ET premarket.
    now = datetime.now(ET).replace(hour=7, minute=45, second=0, microsecond=0)

    print("Scenario A -- CPI at 8:30am + non-voter speaking at noon:")
    res = evaluate_catalysts([
        Event("CPI", time_et=time(8, 30)),
        Event("Atlanta Fed (non-voter) remarks", time_et=time(12, 0),
              is_fed_speaker=True, speaker_is_voter=False),
    ], now_et=now)
    print(res, "\n")

    print("Scenario B -- quiet calendar, one regional non-voter:")
    res = evaluate_catalysts([
        Event("Fed regional president (non-voter) speech", time_et=time(11, 0),
              is_fed_speaker=True, speaker_is_voter=False),
    ], now_et=now)
    print(res, "\n")

    print("Scenario C -- FOMC decision day:")
    res = evaluate_catalysts([
        Event("FOMC rate decision", time_et=time(14, 0)),
    ], now_et=now)
    print(res, "\n")

    print("Scenario D -- it's now 9:00am, CPI already printed at 8:30 and settled:")
    res = evaluate_catalysts(
        [Event("CPI", time_et=time(8, 30))],
        now_et=now.replace(hour=9, minute=0),
    )
    print(res)
