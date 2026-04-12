#!/usr/bin/env python3
"""
Taos Build Daily Digest v4.0 — Full integration
Clean, scannable, action-first with:
- Claude jargon removal (strip_claude_preamble)
- GitHub issue tracking for each digest  
- Learning resource fallback library
- Priority-aware email formatting
"""

import json
import logging
import os
import re
import smtplib
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic

# v4.0 improvements
sys.path.insert(0, str(Path(__file__).parent.parent))
from digest_tracker import DigestTracker, build_tracking_footer
from improved_email_formatter import strip_claude_preamble
from table_and_fallback_fixes import format_learning_resources, get_learning_resources_for_day

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
RECIPIENT = os.environ.get("RECIPIENT_EMAIL", "")
SENDER = os.environ.get("SENDER_EMAIL", "")
PASSWORD = os.environ.get("SENDER_PASSWORD", "")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = 2048
DELAY = int(os.environ.get("INTER_CALL_DELAY", "5"))
REPO_OWNER = os.environ.get("REPO_OWNER", "chris-billante")
REPO_NAME = os.environ.get("REPO_NAME", "taos-daily-digest")
FEEDBACK_BASE_URL = os.environ.get(
    "FEEDBACK_BASE_URL",
    f"https://{REPO_OWNER}.github.io/{REPO_NAME}/feedback"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("taos")

def load_json(p: Path) -> dict | list:
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def save_json(p: Path, d: dict | list) -> None:
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)

# Populated in main() to avoid import-time I/O
CONSTRAINTS: dict = {}
LISTING_CACHE: dict = {}
LEARNING_HIST: list = []
NOTES: dict = {"completions": []}
RESEARCH: dict = {"sections": {}}


def now_mt() -> datetime:
    return datetime.now(timezone(timedelta(hours=-7)))

def today() -> str:
    return now_mt().strftime("%B %d, %Y")

def today_long() -> str:
    return now_mt().strftime("%A, %B %d, %Y")

def recent_completions(days: int = 7) -> list[dict]:
    """Return completions from the last N days, newest first."""
    cutoff = (now_mt().date() - timedelta(days=days)).isoformat()
    return [c for c in NOTES.get("completions", [])
            if c.get("date", "") >= cutoff]

def recent_context_block(days: int = 7) -> str:
    """Build a context string of recent completions for AI prompt injection."""
    completions = recent_completions(days)
    if not completions:
        return ""
    lines = []
    for c in completions:
        status = c.get("status", "done").upper()
        line = f"- {c['date']}: [{status}] '{c.get('task_summary', 'a task')}'"
        if c.get("notes"):
            line += f"\n  Angela's notes: {c['notes']}"
        if c.get("follow_up"):
            line += f"\n  Follow-up needed: {c['follow_up']}"
        lines.append(line)
    return "RECENT ACTIONS — HARD CONSTRAINT: do NOT repeat DONE tasks. IN_PROGRESS/WAITING items may need follow-up. Use notes as context:\n" + "\n".join(lines)

def extract_action_line(content: str) -> str:
    """Pull just the Action: line from the full AI action-item response."""
    # Try **Action:** markdown format first
    match = re.search(r'\*\*Action:\*\*\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:160]
    # Fallback: first meaningful non-label line, strip markdown/HTML
    for line in content.split('\n'):
        line = re.sub(r'<[^>]+>', '', line)       # strip HTML
        line = re.sub(r'\*{1,2}[^*]+\*{1,2}', '', line)  # strip **bold**
        line = line.strip()
        if line and len(line) > 15 and not line.startswith('**'):
            return line[:160]
    return "Today's action item"

def research_block(section: str) -> str:
    """Return pre-researched findings for a section, if available."""
    data = RESEARCH.get("sections", {}).get(section, "")
    if not data:
        return ""
    return (
        f"\n\nPRE-RESEARCHED FINDINGS (incorporate relevant items, "
        f"verify links are current):\n{data}"
    )


def latest_follow_up() -> str:
    """Return the most recent follow_up from Angela's completions, if any."""
    for c in recent_completions(days=3):
        fu = c.get("follow_up", "").strip()
        if fu:
            return fu
    return ""

def builder_notes_block() -> str:
    """Extract notes from completions that mention known builders."""
    builder_names = [b["name"].lower() for b in CONSTRAINTS.get("builders", {}).get("active", [])]
    relevant = []
    for c in recent_completions(days=14):
        task_lower = c.get("task_summary", "").lower()
        notes_lower = c.get("notes", "").lower()
        if any(b in task_lower or b in notes_lower for b in builder_names):
            relevant.append(c)
    if not relevant:
        return ""
    lines = ["ANGELA'S RECENT BUILDER CALLS — incorporate these findings:"]
    for c in relevant:
        lines.append(f"- {c['date']}: {c.get('task_summary', '')}")
        if c.get("notes"):
            lines.append(f"  What she learned: {c['notes']}")
    return "\n".join(lines)

# --- API ---
def ask(prompt: str, max_tok: int = MAX_TOKENS) -> str:
    client = anthropic.Anthropic(api_key=API_KEY, timeout=120.0)
    for i in range(5):
        try:
            r = client.messages.create(model=MODEL, max_tokens=max_tok,
                tools=[{"type":"web_search_20250305","name":"web_search"}],
                messages=[{"role":"user","content":prompt}])
            response = "\n".join(b.text for b in r.content if b.type == "text").strip()
            return strip_claude_preamble(response)
        except anthropic.RateLimitError:
            wait = min(30 * (2 ** i), 300)
            if i < 4:
                log.warning(f"Rate limit ({i+1}/5), wait {wait}s")
                time.sleep(wait)
            else:
                log.error("Rate limit exceeded after 5 retries")
                return ""
        except anthropic.APIError as e:
            log.error(f"Anthropic API error: {e}", exc_info=True)
            return ""

# --- Clean + Format ---
SKIP = [
    r"^I('ll| will| need to) (search|look)\b.*",
    r"^Let me (search|find|check)\b.*",
    r"^Based on (my |the )?(search|research)\b.*",
    r"^Perfect\.?\s*\b.*",
    r"^Great\.?\s*\b.*",
    r"^Here('s| is| are) what I\b.*",
    r"^Searching\b.*",
    r"^I found\b.*",
    r"^Unfortunately\b.*",
    r"^I was unable\b.*",
    r"^I could not\b.*",
    r"^However,? I (notice|should|want)\b.*",
    r"^I notice\b.*",
    r"^I'll provide\b.*",
    r"^I have enough information\b.*",
    r"^MATCHING YOUR CRITERIA:?$",
    r"^Here are\b.*",
    r"^Below (is|are)\b.*",
    r"^For today\b.*I('ll| will)\b.*",
    r"^Based on (available|current|the)\b.*",
    r"^After (searching|reviewing|checking)\b.*",
]

def clean_response(txt: str) -> str:
    if not txt: return ""
    out, prev_blank = [], False
    for line in txt.split("\n"):
        s = line.strip()
        if re.match(r'^-{3,}$', s) or re.match(r'^\*{3,}$', s): continue
        if any(re.match(p, s, re.I) for p in SKIP): continue
        if not s:
            if not prev_blank: out.append("")
            prev_blank = True
        else: out.append(line); prev_blank = False
    return "\n".join(out).strip()

def markdown_to_html(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)',
        r'<a href="\2" style="color:#2563EB;text-decoration:underline">\1</a>', text)
    text = re.sub(r"(?<![\"'>])(https?://\S+)",
        r'<a href="\1" style="color:#2563EB;text-decoration:underline">\1</a>', text)
    return text

def content_to_html(content: str) -> str:
    """Convert markdown-ish AI response content to email-safe HTML."""
    content = clean_response(content)
    if not content:
        return ""
    lines = content.split("\n")
    html: list[str] = []
    ltag: str | None = None
    def cl():
        nonlocal ltag
        if ltag:
            html.append(f"</{ltag}>")
            ltag = None
    for raw in lines:
        s = raw.strip()
        if not s:
            cl()
            continue
        if s in ("-", "*", "•"):
            continue
        s = markdown_to_html(s)
        if "HIGH PRIORITY" in s.upper() or s.startswith("🔴"):
            cl()
            html.append(
                f'<div style="color:#dc2626;font-weight:600;background:#FEF2F2;'
                f'padding:8px 12px;border-left:3px solid #dc2626;border-radius:4px;'
                f'margin:8px 0;font-size:14px">{s}</div>')
        elif s.startswith("### "):
            cl()
            html.append(
                f'<div style="color:#2D6A4F;font-size:13px;font-weight:700;'
                f'margin:12px 0 4px;text-transform:uppercase;letter-spacing:0.03em">'
                f'{s[4:]}</div>')
        elif s.startswith("## "):
            cl()
            html.append(
                f'<div style="color:#1B3A5C;font-size:15px;font-weight:700;'
                f'margin:14px 0 6px;padding-bottom:4px;'
                f'border-bottom:2px solid #E2E8F0">{s[3:]}</div>')
        elif re.match(r'^\d+\.\s', s):
            if ltag != "ol":
                cl()
                html.append('<ol style="margin:6px 0;padding-left:24px">')
                ltag = "ol"
            itxt = re.sub(r'^[0-9]+[.]\s*', '', s)
            html.append(f'<li style="margin-bottom:4px;line-height:1.5">{itxt}</li>')
        elif s.startswith("- ") or s.startswith("* "):
            if ltag != "ul":
                cl()
                html.append('<ul style="margin:6px 0;padding-left:24px">')
                ltag = "ul"
            html.append(f'<li style="margin-bottom:4px;line-height:1.5">{s[2:]}</li>')
        elif s.lower().startswith("📞") or "caller script" in s.lower():
            cl()
            html.append(
                f'<div style="background:#EFF6FF;border-left:3px solid #3B82F6;'
                f'padding:10px 14px;margin:10px 0;border-radius:4px;'
                f'font-style:italic;font-size:14px;line-height:1.5">{s}</div>')
        else:
            cl()
            html.append(f'<p style="margin:4px 0;line-height:1.6;font-size:14px">{s}</p>')
    cl()
    return "\n".join(html)


def section(anchor: str, emoji: str, title: str, content: str,
            border_color: str = "#1B3A5C", raw_html: bool = False,
            action_url: str = "") -> str:
    """Render an email section as a styled card."""
    if not content:
        return ""
    body = content.strip() if raw_html else content_to_html(content)
    if not body:
        return ""
    btn_html = ""
    if action_url:
        btn_html = (
            f'\n  <div style="margin-top:12px">'
            f'<a href="{action_url}" style="display:inline-block;'
            f'background:#16a34a;color:#fff;padding:10px 20px;'
            f'border-radius:6px;text-decoration:none;font-size:13px;'
            f'font-weight:600">Save Progress &amp; Notes</a></div>'
        )
    return f'''<table id="{anchor}" width="100%" cellpadding="0" cellspacing="0" border="0"
  style="margin-bottom:16px;border-collapse:collapse">
<tr><td style="background:{border_color};height:4px;border-radius:6px 6px 0 0" colspan="2"></td></tr>
<tr><td style="background:#fff;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 6px 6px;padding:16px 18px">
  <div style="font-size:17px;font-weight:700;color:{border_color};margin-bottom:10px">
    {emoji} {title}
  </div>
  <div style="color:#334155;line-height:1.6">{body}</div>{btn_html}
</td></tr>
</table>'''

# --- Prompts ---
SCRIPT = '''Include a "📞 CALLER SCRIPT" section — a 3-sentence phone script my wife Angela can read:
"Hi, my name is Angela. My husband and I are planning a small off-grid home in Taos County, NM — [specific ask]. Could you help with [question]?"'''

def p_action() -> str:
    ctx = recent_context_block()
    ctx_section = f"\n\n{ctx}" if ctx else ""
    fu = latest_follow_up()
    fu_section = f"\n\nANGELA'S PRIORITY FOLLOW-UP (suggest this first if still relevant): {fu}" if fu else ""
    bs = CONSTRAINTS["builders"]["active"]
    b = bs[now_mt().timetuple().tm_yday % len(bs)]
    builder_ctx = builder_notes_block()
    builder_section = f"\n\n{builder_ctx}" if builder_ctx else ""
    return ask(f"""Generate TWO action items for today. Off-grid tiny home, Taos County NM. $350K ALL-IN.

PRIMARY ACTION (rotate: land, lenders, off-grid learning, outreach):
Builders: Zook Cabins (https://zookcabins.com), Mighty Small Homes (https://mightysm.com), DC Structures (https://dcstructures.com — Deschutes: https://dcstructures.com/kits/deschutes/, Rogue: https://dcstructures.com/kits/rogue/).
Land: 2+ acres under $60K, Tres Piedras to Arroyo Hondo. Off-grid OK.
Recommended agents for land: Crystal Martinez, NM Real Estate Group (575) 779-6482; Lisa Cancro, Taos Properties (taosproperties.com); Luisa Guercini, Berkshire Hathaway Taos.

BUILDER CHECK-IN: Today's builder: {b['name']} ({b['type']}). Site: {b['website']}. Models: {', '.join(b['models'])}.
Get latest pricing, delivery to NM, reviews, or comparable alternatives.{builder_section}{research_block("builders")}
{ctx_section}{fu_section}

Format EXACTLY (no intro text, no explanation, jump straight into the format):
**Action:** [what to do]
**Contact:** [name, phone/URL with clickable link]
**Why:** [one sentence — factual, not marketing fluff]
{SCRIPT}

---

**Action:** [what to do for builder check-in]
**Contact:** [name, phone/URL with clickable link]
**Why:** [one sentence]
{SCRIPT}

Today: {today_long()}. Output ONLY the two actions separated by ---. No preamble. No titles like "Action 1". Start directly with **Action:**.""", 1024)

def p_land() -> str:
    areas = ", ".join(CONSTRAINTS["land"]["target_areas"])
    return ask(f"""Land for sale in Taos County NM: {areas}. Min {CONSTRAINTS['land']['min_acres']} acres, under ${CONSTRAINTS['land']['max_price']:,}.
Legal road access. Off-grid OK — NO water/sewer/electric needed. Do NOT dismiss parcels lacking utilities.
For each listing use this format:
- $PRICE | ACRES acres | LOCATION | Water: [yes/none/unknown] | Road: [paved/dirt/unknown] | [Link text](URL)
Under $50K with water = mark as 🔴 HIGH PRIORITY.
No headers like "MATCHING YOUR CRITERIA" — jump straight into the listings.

After listings, add:
---
**Recommended Land Agents:**
- Crystal Martinez, NM Real Estate Group — (575) 779-6482 · [crystalmartinez.realtor](https://www.crystalmartinez.realtor/) — 7 active Taos County land listings, covers Tres Piedras to Arroyo Hondo
- Lisa Cancro, Taos Properties — [taosproperties.com](https://taosproperties.com/) — 2024 Realtor of the Year, 30+ years land/commercial experience
- Luisa Guercini, Berkshire Hathaway Taos — #1 brokerage in Taos Valley since 1987, land sale specialist

Today: {today()}. Output listings first, then agent section.{research_block("land")}""")

def p_builders() -> str:
    bs = CONSTRAINTS["builders"]["active"]
    b = bs[now_mt().timetuple().tm_yday % len(bs)]
    ctx = builder_notes_block()
    ctx_section = f"\n\n{ctx}" if ctx else ""
    return ask(f"""Latest on {b['name']} ({b['type']}). Site: {b['website']}. Models: {', '.join(b['models'])}.
Context: off-grid tiny home, Taos County NM, 7000ft, $350K all-in.
(1) Pricing/new models (2) Reviews (3) NM delivery (4) Comparable builders.
Bullets with links.
{SCRIPT}{ctx_section}
Today: {today()}. Output ONLY findings.""")

def p_offgrid() -> str:
    og = CONSTRAINTS.get("offgrid_systems", {})
    return ask(f"""Off-grid and alternative housing news for northern New Mexico. Output as bullet list — no intro paragraph.
Our planned systems: Solar: {og.get('solar', 'TBD')}. Heating: {og.get('heating', 'TBD')}. Hot water: {og.get('hot_water', 'TBD')}. Water: {og.get('water', 'TBD')}.
Topics to cover (pick 3-4 with real news or updates):
- NM solar incentives or legislation 2025-2026 (especially relevant to our EG4/IronRidge setup)
- Taos County building or zoning changes
- Alternative housing: earthships, container homes, A-frames, dome homes, park models, or creative small housing IRC/CID approvable in NM
- NM CID updates on modular or kit homes
- Taos-area off-grid community news or events
- NM water rights or well drilling updates
Each bullet: **Topic** — 1-2 sentence summary with [link](URL).
No preamble. No "Based on my research." Start with the first bullet.
Today: {today()}. Output ONLY items.{research_block("offgrid")}""")

def format_tacoma_results(new_listings: list, all_listings: list, fb_urls: list) -> str:
    """Format scraped Tacoma listings as section-compatible markdown."""
    parts = []
    if new_listings:
        parts.append(f"## 🆕 {len(new_listings)} New Listing{'s' if len(new_listings)!=1 else ''} Since Last Scan")
        for lst in new_listings[:10]:
            price = f"${lst['price_num']:,}" if lst.get("price_num") else lst.get("price","N/A")
            miles = f"{lst['miles_num']:,} mi" if lst.get("miles_num") else lst.get("miles","N/A")
            loc = lst.get("location","?")
            bed = lst.get("bed","")
            link = f" · [View]({lst['url']})" if lst.get("url") else ""
            note = " ⚠️ Verify 4WD" if lst.get("note") else ""
            parts.append(f"- **{lst.get('title','Unknown')}** | {price} | {miles} | {loc}{link} {bed}{note}")
    else:
        parts.append("## No New Listings Today")
        parts.append("No new matches since the last scan. Existing listings below are still active.")

    if all_listings:
        parts.append(f"## 📋 All Active Matches ({len(all_listings)})")
        for lst in all_listings[:12]:
            price = f"${lst['price_num']:,}" if lst.get("price_num") else lst.get("price","N/A")
            miles = f"{lst['miles_num']:,} mi" if lst.get("miles_num") else lst.get("miles","N/A")
            link = f" · [View]({lst['url']})" if lst.get("url") else ""
            parts.append(f"- {lst.get('title','?')} | {price} | {miles} | {lst.get('location','?')} · {lst.get('source','')}{link}")
        if len(all_listings) > 12:
            parts.append(f"  _(+{len(all_listings)-12} more — see manual links below)_")

    parts.append("## 🔍 Manual Check Links")
    for fb in fb_urls:
        parts.append(f"- [{fb['title']}]({fb['url']})")
    parts.append("- [CarGurus: TRD Off-Road LB 4WD](https://www.cargurus.com/Cars/t-Used-Toyota-Tacoma-TRD-Off-Road-Double-Cab-LB-4WD-t88828)")
    parts.append("- [Carvana: Tacoma Double Cab](https://www.carvana.com/cars/toyota-tacoma-double-cab)")
    parts.append("- [CarMax: Tacoma TRD Off-Road](https://www.carmax.com/cars/toyota/tacoma/trd-off-road)")
    parts.append("_VIN tip: \"DZ\" in positions 4-5 = Double Cab Long Bed ✅ (vs \"CZ\" = short bed ❌)_")
    return "\n".join(parts)


def p_vehicles() -> str:
    vs = CONSTRAINTS["vehicle_search"]
    rgn = ", ".join(vs["search_regions"])

    # Sprinter van market check
    sprinter = ask(f"""SPRINTER VAN MARKET: Recent 4x4 Sprinter camper van sale prices. My current value: ${CONSTRAINTS['van_sale']['balance_sheet_value']:,}. Market trend? 2-3 sentences max with relevant pricing links.
Today: {today()}. Output ONLY the market assessment.""", 512)

    # Tacoma: try direct scraping first, fall back to Claude search
    tacoma_txt = ""
    try:
        from vehicle_tracker import run_tacoma_search
        new_l, all_l, fb_urls = run_tacoma_search(DATA)
        tacoma_txt = format_tacoma_results(new_l, all_l, fb_urls)
        log.info(f"Vehicle tracker: {len(new_l)} new / {len(all_l)} total listings")
    except Exception as e:
        log.warning(f"Vehicle tracker failed, using Claude search: {e}", exc_info=True)
        tacoma_txt = ask(f"""TACOMA SEARCH: {vs['make']} {vs['model']} {vs['config']}, years {vs['years']}, {', '.join(vs['trims'])}, V6, under ${vs['max_price']:,}, under {vs['max_miles']:,} mi. Regions: {rgn}.
Each listing: year, trim, miles, price, location, link. Flag great deals.
Today: {today()}. Output ONLY listings.""")

    parts = []
    if sprinter:
        parts.append(f"## 🚐 Sprinter Van Market\n{sprinter}")
    if tacoma_txt:
        parts.append(f"## 🛻 Tacoma Tracker\n{tacoma_txt}")
    return "\n\n".join(parts) if parts else ""

def p_bridge() -> str:
    bh = CONSTRAINTS.get("bridge_housing", {})
    suppliers = ", ".join(bh.get("yurt_suppliers", ["Colorado Yurt Company", "Pacific Yurts"]))
    rv_max = bh.get("rv_budget_max", 45000)
    return ask(f"""Bridge/temporary housing options near Taos NM. Jump straight into listings — no intro paragraph.

## Yurts
{suppliers}: pricing for 20-24ft insulated. Current sales? Lead times?
{SCRIPT}

## RV / 5th Wheel
For sale in NM or southern CO, under ${rv_max:,}, year-round capable at 7000ft.
Each: Year, Model, Price, Location, [Link](URL)

## Furnished Rentals
Taos month-to-month furnished under $2500.
Each: $Price/mo, Location, Source, [Link](URL)

No preamble. No "Based on my research" or "I found limited." If a section has no results, write "No current listings found" and move on. Start with ## Yurts.
Today: {today()}. Output ONLY the sections.{research_block("bridge")}""")

def p_learn() -> str:
    # v4.0: Try web search first, fall back to curated library
    try:
        h = ", ".join(LEARNING_HIST[-20:]) if LEARNING_HIST else "none"
        topics = ["off-grid solar tutorial", "SIP panel construction", "NM building code owner-builders",
            "cistern water sizing", "Blaze King setup", "construction-to-perm loan", "NM water rights",
            "off-grid septic", "EG4 inverter guide", "Taos off-grid community",
            "IronRidge ground mount", "propane off-grid", "modular foundation mountain",
            "snow load engineering", "Starlink rural setup"]
        t = topics[now_mt().timetuple().tm_yday % len(topics)]
        r = ask(f"""ONE free resource about: {t}. YouTube, blogs, govt guides.
Avoid: {h}. Format: Title | Source | URL | 2-sentence summary.
Today: {today()}. Output ONLY the resource.""", 512)

        # If result is empty or very short, use fallback
        if not r or len(r) < 50:
            log.info("Using fallback learning resources")
            day_of_week = now_mt().strftime('%A').lower()
            resources_data = get_learning_resources_for_day(day_of_week)
            return "**[From our library]**\n\n" + format_learning_resources(resources_data)

        LEARNING_HIST.append(t)
        if len(LEARNING_HIST) > 60: LEARNING_HIST[:] = LEARNING_HIST[-60:]
        save_json(DATA / "learning_history.json", LEARNING_HIST)
        return "**[Found today]**\n\n" + r
    except Exception as e:
        log.warning(f"Learning resource search failed: {e}, using fallback")
        day_of_week = now_mt().strftime('%A').lower()
        resources_data = get_learning_resources_for_day(day_of_week)
        return "**[From our library]**\n\n" + format_learning_resources(resources_data)

# --- Email ---
def dashboard() -> str:
    target_year = CONSTRAINTS.get("project", {}).get("target_year", 2028)
    target_date = datetime(target_year, 6, 1, tzinfo=timezone(timedelta(hours=-7)))
    days_left = (target_date - now_mt()).days
    bs = " | ".join(f"{b['name']}: {b['status'].replace('_',' ')}" for b in CONSTRAINTS["builders"]["active"])

    # 7-day activity log with date grouping
    recent = recent_completions(days=7)
    completions_html = ""
    if recent:
        rows = []
        current_date = ""
        for c in recent:
            c_date = c.get("date", "")
            if c_date != current_date:
                current_date = c_date
                try:
                    dt_label = datetime.fromisoformat(c_date).strftime("%a %b %d")
                except ValueError:
                    dt_label = c_date
                rows.append(f'<tr><td colspan="2" style="padding:6px 10px 2px;font-weight:700;'
                            f'font-size:11px;color:#475569;text-transform:uppercase;letter-spacing:0.04em;'
                            f'border-top:1px solid #e2e8f0">{dt_label}</td></tr>')
            summary = c.get("task_summary", "Task")[:80]
            notes   = c.get("notes", "")
            note_td = f'<br><span style="color:#64748b;font-size:11px">{notes[:120]}</span>' if notes else ""
            status = c.get("status", "done")
            status_map = {
                "done":        ("✅", "#16a34a", "Done"),
                "in_progress": ("🔄", "#2563eb", "In Progress"),
                "waiting":     ("⏳", "#d97706", "Waiting"),
                "blocked":     ("🚫", "#dc2626", "Blocked"),
            }
            icon, color, label = status_map.get(status, ("✅", "#16a34a", "Done"))
            rows.append(f'<tr><td style="padding:4px 10px;font-weight:600;color:{color}">{icon} {label}</td>'
                        f'<td style="padding:4px 10px">{summary}{note_td}</td></tr>')
        completions_html = "\n".join(rows) + "\n"

    # Friday-only weekly accomplishment summary
    weekly_html = ""
    if now_mt().weekday() == 4 and recent:
        done_count = sum(1 for c in recent if c.get("status", "done") == "done")
        active_count = len(recent) - done_count
        parts = []
        if done_count:
            parts.append(f"{done_count} done")
        if active_count:
            parts.append(f"{active_count} in progress")
        recap = " · ".join(parts) if parts else f"{len(recent)} items"
        weekly_html = (f'<tr><td colspan="2" style="padding:8px 10px;background:#F0FDF4;'
                       f'font-size:12px;color:#166534;font-weight:600;border-top:1px solid #bbf7d0">'
                       f'Weekly recap: {recap}'
                       f'</td></tr>\n')

    return f'''<table style="width:100%;border-collapse:collapse;font-size:13px;background:#F8FAFC;border-radius:4px">
<tr><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0;width:110px;font-weight:600">Budget</td><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0">$350K all-in</td></tr>
<tr><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0;font-weight:600">Committed</td><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0">${CONSTRAINTS["project"]["committed_spend"]:,}</td></tr>
<tr><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0;font-weight:600">Phase</td><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0">{CONSTRAINTS["project"]["phase"].replace("_"," ").title()}</td></tr>
<tr><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0;font-weight:600">Days Left</td><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0">{days_left}</td></tr>
<tr><td style="padding:4px 10px;{"border-bottom:1px solid #e2e8f0;" if recent or weekly_html else ""}font-weight:600">Builders</td><td style="padding:4px 10px;{"border-bottom:1px solid #e2e8f0;" if recent or weekly_html else ""}">{bs}</td></tr>
{completions_html}{weekly_html}</table>'''

def build_email(sections: dict) -> tuple[str, str]:
    dt = now_mt()
    top = "Daily Briefing"
    if "HIGH PRIORITY" in sections.get("land","").upper(): top = "High-Priority Land"
    elif sections.get("land","").strip(): top = "Land Listings"
    subj = f"Taos Build Intel - {dt.strftime('%a %b %d')} | {top}"

    # v4.0: Create GitHub tracking issue
    tracker = None
    issue_number = None
    try:
        if os.environ.get("GITHUB_TOKEN"):
            tracker = DigestTracker(
                repo_owner=REPO_OWNER,
                repo_name=REPO_NAME,
                github_token=os.environ["GITHUB_TOKEN"]
            )
            section_names = ["Action Item", "Land Listings", "Off-Grid News",
                           "Dashboard", "Tacoma & Van", "Bridge Housing", "Learning Resource"]
            issue_number = tracker.create_digest_issue(dt.strftime("%A, %B %d, %Y"), section_names)
            log.info(f"Created tracking issue #{issue_number}")
    except Exception as e:
        log.warning(f"Tracking issue skipped: {e}")

    # Build sections
    action_content = sections.get("action", "")

    # Feedback button URL
    action_line = extract_action_line(action_content) if action_content else "Today's task"
    task_enc    = urllib.parse.quote(action_line)
    date_str    = now_mt().strftime("%Y-%m-%d")
    issue_param = f"&issue={issue_number}" if issue_number else ""
    feedback_url = f"{FEEDBACK_BASE_URL}?date={date_str}&task={task_enc}{issue_param}"
    dashboard_url = f"https://{REPO_OWNER}.github.io/{REPO_NAME}/feedback/"

    # Hero action card — prominent, separate from other sections
    action_body = content_to_html(action_content) if action_content else "<p>No action item today.</p>"
    hero = f'''<table id="action" width="100%" cellpadding="0" cellspacing="0" border="0"
  style="margin-bottom:16px;border-collapse:collapse">
<tr><td style="background:linear-gradient(135deg,#1e40af,#2563eb);border-radius:8px;padding:20px 22px">
  <div style="font-size:12px;font-weight:700;color:rgba(255,255,255,0.8);text-transform:uppercase;
    letter-spacing:0.08em;margin-bottom:6px">TODAY'S ACTION ITEM</div>
  <div style="color:#fff;font-size:15px;line-height:1.6;margin-bottom:16px">{action_body}</div>
  <div>
    <a href="{feedback_url}"
       style="display:inline-block;background:#16a34a;color:#fff;padding:12px 28px;border-radius:6px;
              text-decoration:none;font-size:15px;font-weight:700;min-height:44px">
      Save Progress &amp; Notes
    </a>
  </div>
</td></tr></table>'''

    # Section-specific feedback URLs
    def section_fb(task_label: str) -> str:
        enc = urllib.parse.quote(task_label)
        return f"{FEEDBACK_BASE_URL}?date={date_str}&task={enc}{issue_param}"

    # Research sections
    sec = ""
    sec += section("land", "🏜️", "LAND LISTINGS", sections.get("land",""), "#b45309",
                   action_url=section_fb("Review land listings"))
    sec += section("offgrid", "⚡", "IN THE NEWS: OFF-GRID HOUSING", sections.get("offgrid",""), "#7C3AED")
    sec += section("tacoma", "🚐", "TACOMA & VAN MARKET", sections.get("vehicles",""), "#475569")
    sec += section("bridge", "🏕️", "BRIDGE HOUSING", sections.get("bridge",""), "#0e7490",
                   action_url=section_fb("Research bridge housing options"))
    sec += section("learn", "📚", "LEARNING RESOURCE", sections.get("learning",""), "#6d28d9")
    sec += section("dash", "📊", "PROJECT DASHBOARD", dashboard(), "#1B3A5C", raw_html=True)

    # TOC — visual only (Gmail/Outlook strip id attrs, breaking anchor links)
    toc_labels = [
        "🔑 Action", "🏜️ Land", "⚡ Off-Grid",
        "🚐 Tacoma", "🏕️ Housing", "📚 Learn", "📊 Dashboard"]
    toc = " &nbsp;&middot;&nbsp; ".join(
        f'<span style="color:#fff;font-size:12px;font-weight:500;'
        f'opacity:0.9">{lbl}</span>' for lbl in toc_labels)

    html = f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  max-width:640px;margin:0 auto;padding:0;background:#f0f4f8">

<!-- Header -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">
<tr><td style="background:linear-gradient(135deg,#1B3A5C,#2D6A4F);color:#fff;
  padding:20px 24px 14px;border-radius:8px 8px 0 0">
  <div style="font-size:22px;font-weight:800;letter-spacing:-0.02em">🏔️ Taos Build Intel</div>
  <div style="font-size:13px;opacity:0.8;margin:4px 0 12px">
    {dt.strftime("%A, %B %d, %Y")} &nbsp;|&nbsp; $350K All-In &nbsp;|&nbsp; Pre-Land Phase
  </div>
  <div style="border-top:1px solid rgba(255,255,255,0.25);padding-top:8px;line-height:1.8">
    {toc}
  </div>
</td></tr></table>

<!-- Body -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">
<tr><td style="background:#f0f4f8;padding:16px 12px 8px">

  {hero}
  {sec}

  <!-- Quick links -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
    style="margin:8px 0 12px;border-collapse:collapse">
  <tr>
    <td style="text-align:center;padding:12px">
      <a href="{dashboard_url}"
         style="display:inline-block;background:#7c3aed;color:#fff;padding:10px 22px;
                border-radius:6px;text-decoration:none;font-size:13px;font-weight:600;
                margin:0 4px">My Dashboard</a>
      <a href="{feedback_url}"
         style="display:inline-block;background:#16a34a;color:#fff;padding:10px 22px;
                border-radius:6px;text-decoration:none;font-size:13px;font-weight:600;
                margin:0 4px">Save Progress & Notes</a>
    </td>
  </tr></table>

  <!-- Footer -->
  <div style="text-align:center;padding:10px;font-size:11px;color:#94a3b8">
    Taos Off-Grid Homestead &nbsp;|&nbsp; Daily Briefing v5.1
  </div>

</td></tr></table>
</body></html>'''

    # v4.0: Add tracking footer if issue was created
    if issue_number and tracker:
        try:
            tracking_footer = build_tracking_footer(issue_number, REPO_OWNER, REPO_NAME)
            html = html.replace('</body>', tracking_footer + '</body>')
        except Exception as e:
            log.warning(f"Tracking footer skipped: {e}")

    return subj, html

# --- Send ---
def send(subj: str, html: str) -> None:
    if not SENDER or not PASSWORD:
        (ROOT/"data"/"last_digest.html").write_text(html, encoding="utf-8"); return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj; msg["From"] = SENDER; msg["To"] = RECIPIENT
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
            s.starttls(); s.login(SENDER, PASSWORD)
            s.sendmail(SENDER, RECIPIENT, msg.as_string())
        log.info("Digest email sent successfully")
    except Exception as e:
        log.error(f"Send failed: {e}")
        (ROOT/"data"/"last_digest.html").write_text(html, encoding="utf-8")

# --- Main ---
def main() -> None:
    global CONSTRAINTS, LISTING_CACHE, LEARNING_HIST, NOTES, RESEARCH

    log.info("v5.1 Starting - Full integration active")
    if not API_KEY:
        log.error("No API key")
        sys.exit(1)

    # Load data files at runtime, not import time
    CONSTRAINTS = load_json(DATA / "constraints.json")
    LISTING_CACHE = load_json(DATA / "listing_cache.json")
    LEARNING_HIST = load_json(DATA / "learning_history.json")
    research_file = DATA / "research_cache.json"
    if research_file.exists():
        RESEARCH = load_json(research_file)
        log.info("Research cache loaded (%d sections)",
                 len(RESEARCH.get("sections", {})))
    else:
        log.info("No research cache — prompts will use live search only")
    notes_file = DATA / "context_notes.json"
    NOTES = load_json(notes_file) if notes_file.exists() else {"completions": []}

    sections = {}
    streams = [
        ("action",   "Action",    p_action),
        ("land",     "Land",      p_land),
        ("offgrid",  "Off-Grid",  p_offgrid),
        ("vehicles", "Vehicles",  p_vehicles),
        ("bridge",   "Bridge",    p_bridge),
        ("learning", "Learning",  p_learn),
    ]

    def _run_stream(
        key: str, label: str, fn: object,
    ) -> tuple[str, str, str]:
        log.info(f"{label}...")
        try:
            result = fn()
            log.info(f"  OK {label} ({len(result)}ch)")
            return key, label, result
        except Exception as e:
            log.error(f"  FAIL {label}: {e}", exc_info=True)
            return key, label, ""

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(_run_stream, k, lbl, fn): k
            for k, lbl, fn in streams
        }
        for future in as_completed(futures):
            key, label, result = future.result()
            sections[key] = result

    subj, html = build_email(sections)
    log.info(f"Subject: {subj}")
    send(subj, html)
    (ROOT / "data" / "last_digest.html").write_text(html, encoding="utf-8")
    log.info("Saved local copy to data/last_digest.html")
    LISTING_CACHE["last_updated"] = now_mt().isoformat()
    save_json(DATA / "listing_cache.json", LISTING_CACHE)
    log.info("Done")

if __name__ == "__main__":
    main()
