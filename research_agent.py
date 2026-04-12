#!/usr/bin/env python3
"""
Pre-digest research agent.

Runs before main.py in the daily workflow. Uses Claude web search to gather
fresh data for each digest section. Writes findings to data/research_cache.json.

Output is factual and impersonal — no first-person, no filler, no preamble.
main.py injects relevant findings into its prompts for higher-quality content.
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CACHE_FILE = DATA / "research_cache.json"
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
DELAY = int(os.environ.get("RESEARCH_DELAY", "8"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("research")

# Patterns to strip from responses — keeps output factual and impersonal
STRIP_PATTERNS = [
    r"^I('ll| will| need to| found| searched| discovered)\b.*",
    r"^Let me\b.*",
    r"^Based on (my |the )?(search|research|findings)\b.*",
    r"^Here('s| is| are) what\b.*",
    r"^Here are\b.*",
    r"^Below (is|are)\b.*",
    r"^After (searching|reviewing|checking)\b.*",
    r"^Unfortunately\b.*",
    r"^I was unable\b.*",
    r"^I could not\b.*",
    r"^Searching\b.*",
    r"^Perfect\.?\s*.*",
    r"^Great\.?\s*.*",
    r"^For today\b.*",
    r"^I notice\b.*",
    r"^I have enough\b.*",
    r"^I'll provide\b.*",
    r"^In summary\b.*",
    r"^To summarize\b.*",
    r"^Overall\b.*",
    r"^In conclusion\b.*",
]


def now_mt() -> datetime:
    """Current time in Mountain Time."""
    return datetime.now(timezone(timedelta(hours=-7)))


def clean(text: str) -> str:
    """Strip AI preamble, filler, and first-person language."""
    if not text:
        return ""
    lines: list[str] = []
    prev_blank = False
    for line in text.split("\n"):
        s = line.strip()
        if re.match(r"^-{3,}$", s) or re.match(r"^\*{3,}$", s):
            continue
        if any(re.match(p, s, re.I) for p in STRIP_PATTERNS):
            continue
        if not s:
            if not prev_blank:
                lines.append("")
            prev_blank = True
        else:
            lines.append(line)
            prev_blank = False
    return "\n".join(lines).strip()


def search(prompt: str, max_tokens: int = 1024) -> str:
    """Run a Claude web-search query. Returns cleaned text."""
    client = anthropic.Anthropic(api_key=API_KEY, timeout=120.0)
    for attempt in range(3):
        try:
            r = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            )
            raw = "\n".join(
                b.text for b in r.content if b.type == "text"
            ).strip()
            return clean(raw)
        except anthropic.RateLimitError:
            wait = min(60 * (2 ** attempt), 180)
            if attempt < 2:
                log.warning("Rate limit (%d/3), wait %ds", attempt + 1, wait)
                time.sleep(wait)
            else:
                log.error("Rate limit exceeded after 3 retries")
                return ""
        except anthropic.APIError as e:
            log.error("API error: %s", e)
            return ""


def load_constraints() -> dict:
    """Load project constraints."""
    with open(DATA / "constraints.json", encoding="utf-8") as f:
        return json.load(f)


# --- Research queries ---

TONE = (
    "Write in third-person factual tone. No first-person (no 'I found', "
    "'I searched', 'my research'). No filler or preamble. "
    "Start directly with findings. Bullet points preferred."
)


def research_land(cfg: dict) -> str:
    """Fresh land listings, market data, and top-rated land agents."""
    areas = ", ".join(cfg["land"]["target_areas"])
    return search(f"""Current vacant land for sale in Taos County NM.
Target areas: {areas}.
Minimum {cfg['land']['min_acres']} acres, under ${cfg['land']['max_price']:,}.
Off-grid parcels are acceptable — lack of utilities is NOT a disqualifier.

Search LandWatch, Land.com, Zillow, Realtor.com for current listings.
For each listing found:
- $PRICE | ACRES acres | LOCATION | Water: [status] | Road: [type] | Source: [site] | URL

Also note any market trends: price changes, new subdivisions, seasonal patterns.

Also list top-rated real estate agents specializing in vacant land sales in
Taos County NM. Focus on agents with active land listings covering
{areas}. For each agent: Name, brokerage, phone, website, specializations.

{TONE}
Today: {now_mt().strftime('%B %d, %Y')}.""")


def research_builders(cfg: dict) -> str:
    """Latest builder pricing, reviews, and news."""
    builders = cfg["builders"]["active"]
    builder_lines = "\n".join(
        f"- {b['name']} ({b['type']}): {b['website']} — models: {', '.join(b['models'])}"
        for b in builders
    )
    return search(f"""Latest pricing, reviews, and news for these small home builders:
{builder_lines}

Context: off-grid tiny home build in Taos County NM, 7000ft elevation, $350K all-in budget.

For each builder, report:
- Current base pricing and any 2025-2026 price changes
- Recent customer reviews (positive and negative)
- Delivery availability to New Mexico
- Any new models or discontinued models
- Comparable alternatives worth considering

{TONE}
Today: {now_mt().strftime('%B %d, %Y')}.""")


def research_offgrid() -> str:
    """Off-grid and alternative housing news for NM."""
    return search(f"""Recent off-grid and alternative housing news for northern New Mexico.
Topics (report only items with real news — skip if nothing current):
- NM solar incentives or legislation 2025-2026
- Taos County building or zoning changes
- Alternative housing: earthships, container homes, A-frames, park models
- NM Construction Industries Division (CID) updates on modular/kit homes
- Taos-area off-grid community events
- NM water rights or well drilling updates

Each item: **Topic** — 1-2 sentence summary with source URL.

{TONE}
Today: {now_mt().strftime('%B %d, %Y')}.""", 768)


def research_bridge() -> str:
    """Bridge housing: yurts, RVs, rentals near Taos."""
    return search(f"""Bridge/temporary housing options near Taos NM.

1. Yurts: Colorado Yurt Company and Pacific Yurts — current pricing for 20-24ft insulated models, lead times, any sales.
2. RV / 5th Wheel: For sale in NM or southern CO, under $45K, suitable for year-round at 7000ft.
3. Furnished month-to-month rentals in Taos area under $2500/mo.

For listings: Price, description, location, source URL.

{TONE}
Today: {now_mt().strftime('%B %d, %Y')}.""", 768)


def main() -> None:
    """Run all research queries sequentially and write cache."""
    if not API_KEY:
        log.error("No ANTHROPIC_API_KEY set")
        sys.exit(1)

    cfg = load_constraints()
    cache: dict = {
        "generated": now_mt().isoformat(),
        "date": now_mt().strftime("%Y-%m-%d"),
        "sections": {},
    }

    queries = [
        ("land", "Land + agents", lambda: research_land(cfg)),
        ("builders", "Builder intel", lambda: research_builders(cfg)),
        ("offgrid", "Off-grid news", research_offgrid),
        ("bridge", "Bridge housing", research_bridge),
    ]

    for key, label, fn in queries:
        log.info("Researching: %s", label)
        try:
            result = fn()
            cache["sections"][key] = result
            log.info("  %s: %d chars", label, len(result))
        except Exception as e:
            log.error("  %s FAILED: %s", label, e, exc_info=True)
            cache["sections"][key] = ""
        time.sleep(DELAY)

    # Write cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    log.info("Research cache written to %s", CACHE_FILE)


if __name__ == "__main__":
    main()
