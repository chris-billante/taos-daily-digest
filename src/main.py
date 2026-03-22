#!/usr/bin/env python3
"""
Taos Build Daily Digest — Main Orchestrator
Calls Claude API with web search for each intelligence stream,
formats results into HTML email, sends via Gmail SMTP.
"""

import json
import os
import sys
import smtplib
import hashlib
import logging
import time
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import anthropic
from jinja2 import Template

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"

RECIPIENT = os.environ.get("RECIPIENT_EMAIL", "RECIPIENT_EMAIL_SECRET")
SENDER = os.environ.get("SENDER_EMAIL", "")
PASSWORD = os.environ.get("SENDER_PASSWORD", "")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2048

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("taos-digest")

# ---------------------------------------------------------------------------
# Load project data
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)

def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

CONSTRAINTS = load_json(DATA / "constraints.json")
CACHE = load_json(DATA / "listing_cache.json")
LEARNING_HISTORY = load_json(DATA / "learning_history.json")

# ---------------------------------------------------------------------------
# Claude API caller with web search
# ---------------------------------------------------------------------------

def ask_claude(prompt: str, max_tokens: int = MAX_TOKENS) -> str:
    """Call Claude API with web search tool enabled. Returns text response."""
    client = anthropic.Anthropic(api_key=API_KEY)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract all text blocks from response
        texts = []
        for block in response.content:
            if block.type == "text":
                texts.append(block.text)
        return "\n".join(texts).strip()
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return f"⚠️ Search unavailable: {e}"

# ---------------------------------------------------------------------------
# Intelligence Stream Functions
# ---------------------------------------------------------------------------

def get_todays_date():
    mt = timezone(timedelta(hours=-7))
    return datetime.now(mt)

def search_land() -> str:
    """Search for new land listings matching project criteria."""
    areas = ", ".join(CONSTRAINTS["land"]["target_areas"])
    prompt = f"""Search for land for sale in Taos County, New Mexico. I need parcels that match ALL of these:
- Located in or near: {areas}
- Minimum 3 acres
- Under ${CONSTRAINTS['land']['max_price']:,}
- Must have legal road access
- Off-grid is fine (no utilities needed)
- Zoned for residential use

Search LandWatch, Zillow, and Realtor.com for current listings. For each listing found, provide:
- Price
- Acreage
- Location/area
- Water situation if mentioned (well, cistern, water rights)
- Road access notes
- Direct URL to the listing

If a listing has verified water access AND is under $50,000, mark it as HIGH PRIORITY.
Format as a clean list. If no listings match, say so clearly. Today's date: {get_todays_date().strftime('%B %d, %Y')}"""
    return ask_claude(prompt)

def search_builders() -> str:
    """Rotating builder intelligence."""
    builders = CONSTRAINTS["builders"]["active"]
    day_of_year = get_todays_date().timetuple().tm_yday
    builder = builders[day_of_year % len(builders)]
    prompt = f"""Search for the latest news, reviews, pricing updates, or project completions for {builder['name']}.
They build {builder['type']} homes. Their website is {builder['website']}.
Models I'm tracking: {', '.join(builder['models'])}.

I'm building an off-grid home in Taos County, New Mexico at 7,000 ft elevation.
My all-in budget is $350,000 including land, off-grid systems, and the structure.

Find:
1. Any pricing changes or new models announced recently
2. Recent customer reviews or completed project photos
3. Any news about their NM delivery or compliance
4. Any comparable builder I should also be evaluating

Keep it concise — bullet points with links. Today's date: {get_todays_date().strftime('%B %d, %Y')}"""
    return ask_claude(prompt)

def search_offgrid_nm() -> str:
    """Off-grid and NM regulatory news."""
    prompt = f"""Search for recent news relevant to off-grid homebuilding in northern New Mexico. Topics to cover:
1. New Mexico solar incentives or legislation changes (2025-2026)
2. Taos County building code or zoning updates
3. NM water rights news or well drilling regulations
4. Off-grid living articles specific to high desert / northern NM
5. NM Construction Industries Division (CID) updates affecting modular or kit homes

Only include items from the last 30 days if possible. Provide brief summaries with links.
Skip anything not directly relevant to building an off-grid primary residence in Taos County.
Today's date: {get_todays_date().strftime('%B %d, %Y')}"""
    return ask_claude(prompt)

def search_vehicles() -> str:
    """Van market tracking + Tacoma search."""
    vs = CONSTRAINTS["vehicle_search"]
    regions = ", ".join(vs["search_regions"])
    prompt = f"""Two vehicle searches:

SEARCH 1 — SPRINTER VAN MARKET:
Search for Mercedes Sprinter 4x4 camper van sale prices to track market value.
Current balance sheet value: ${CONSTRAINTS['van_sale']['balance_sheet_value']:,}.
Target sale range: ${CONSTRAINTS['van_sale']['target_sale_range_low']:,}–${CONSTRAINTS['van_sale']['target_sale_range_high']:,}.
Are Sprinter van prices trending up or down? Any recent comparable sales?

SEARCH 2 — TOYOTA TACOMA:
Search CarGurus and Cars.com for: {vs['make']} {vs['model']} {vs['config']}
Years: {vs['years']}, Trims: {', '.join(vs['trims'])}, Engine: {vs['engine']}
Max price: ${vs['max_price']:,}, Max miles: {vs['max_miles']:,} miles
Regions: {regions}

For each Tacoma found: year, trim, miles, price, city/state, and link.
Flag any "Great Deal" rated listings. Today's date: {get_todays_date().strftime('%B %d, %Y')}"""
    return ask_claude(prompt)

def search_bridge_housing() -> str:
    """Yurt, RV, rental options."""
    prompt = f"""Search for bridge housing options near Taos, New Mexico:

1. YURTS: Check Colorado Yurt Company and Pacific Yurts for current pricing on 20-24 ft insulated models. Any sales or lead time changes?

2. USED RV/5TH WHEEL: Search for used RVs or 5th wheels for sale in New Mexico or southern Colorado, under $45,000, suitable for year-round living at 7,000 ft elevation.

3. SHORT-TERM RENTALS: What's the current monthly rental market in Taos, NM? Any furnished month-to-month options under $2,500/month?

Concise bullets with links. Skip if nothing new. Today's date: {get_todays_date().strftime('%B %d, %Y')}"""
    return ask_claude(prompt)

def search_learning() -> str:
    """Curated daily learning resource."""
    history_str = ", ".join(LEARNING_HISTORY[-20:]) if LEARNING_HISTORY else "none yet"
    topics = [
        "off-grid solar installation tutorial for beginners",
        "SIP panel construction walkthrough video",
        "New Mexico building code guide for owner-builders",
        "cistern water system sizing and installation",
        "Blaze King wood stove setup and maintenance",
        "construction-to-permanent loan explainer",
        "New Mexico water rights for rural property buyers",
        "off-grid septic system options and costs",
        "EG4 inverter setup and configuration guide",
        "Taos County off-grid community life",
        "IronRidge solar ground mount installation",
        "propane system design for off-grid homes",
        "modular home foundation types for mountain sites",
        "snow load engineering for high elevation homes",
        "off-grid internet options Starlink rural setup",
    ]
    day_idx = get_todays_date().timetuple().tm_yday % len(topics)
    topic = topics[day_idx]
    prompt = f"""Find ONE high-quality learning resource about: {topic}

Prefer: YouTube videos from established channels (Will Prowse, etc.), detailed blog posts from
practitioners, government guides, or well-researched articles. Must be free to access.

Previously shared resources (avoid repeats): {history_str}

Provide: Title, source/author, URL, and a 2-sentence summary of why it's worth watching/reading.
Today's date: {get_todays_date().strftime('%B %d, %Y')}"""
    result = ask_claude(prompt, max_tokens=512)
    # Track what we shared
    LEARNING_HISTORY.append(topic)
    if len(LEARNING_HISTORY) > 60:
        LEARNING_HISTORY[:] = LEARNING_HISTORY[-60:]
    save_json(DATA / "learning_history.json", LEARNING_HISTORY)
    return result

def get_action_item() -> str:
    """Generate today's actionable task based on project phase and day rotation."""
    phase = CONSTRAINTS["project"]["phase"]
    prompt = f"""You are a project manager for an off-grid home build in Taos County, NM.
The project is in the "{phase}" phase. Budget: $350K all-in.

Active builders: Zook Cabins, Mighty Small Homes, DC Structures.
Land target: 3-5 acres, under $55K, Tres Piedras-Carson corridor.
Financing: Cash land purchase → construction loan → refi to perm.
Key risk: Water verification before any land commitment.

Generate ONE specific, actionable task for today. Include:
- What to do (specific action)
- Who to contact (name + phone/email/URL if applicable)
- Why it matters (one sentence)

Keep it to 3-4 lines max. Make it something that can be done in 30 minutes or less.
Today's date: {get_todays_date().strftime('%A, %B %d, %Y')}
Vary the task — rotate between land search, builder quotes, lender research, off-grid learning, and professional outreach."""
    return ask_claude(prompt, max_tokens=512)

# ---------------------------------------------------------------------------
# Email formatting
# ---------------------------------------------------------------------------

def build_dashboard() -> str:
    """Static project dashboard."""
    now = get_todays_date()
    target = datetime(2028, 6, 1, tzinfo=timezone(timedelta(hours=-7)))
    days_left = (target - now).days
    builders_status = []
    for b in CONSTRAINTS["builders"]["active"]:
        builders_status.append(f"{b['name']}: {b['status'].replace('_', ' ')}")
    return f"""<table style="width:100%;border-collapse:collapse;font-size:14px;">
<tr><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;"><strong>Budget</strong></td><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;">$350K ceiling</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;"><strong>Committed</strong></td><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;">${CONSTRAINTS['project']['committed_spend']:,}</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;"><strong>Phase</strong></td><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;">{CONSTRAINTS['project']['phase'].replace('_', ' ').title()}</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;"><strong>Days to 2028 target</strong></td><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;">{days_left}</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;"><strong>Builders</strong></td><td style="padding:4px 8px;border-bottom:1px solid #e2e8f0;">{'<br>'.join(builders_status)}</td></tr>
</table>"""

def format_section(emoji: str, title: str, content: str) -> str:
    """Format a digest section as HTML."""
    if not content or content.strip() == "" or "unavailable" in content.lower():
        return ""
    # Convert markdown-ish content to basic HTML
    lines = content.strip().split("\n")
    html_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            html_lines.append("<br>")
        elif line.startswith("- ") or line.startswith("* "):
            html_lines.append(f"<li style='margin-bottom:4px;'>{line[2:]}</li>")
        elif line.startswith("🔴") or line.startswith("HIGH PRIORITY"):
            html_lines.append(f"<p style='color:#dc2626;font-weight:bold;'>{line}</p>")
        else:
            html_lines.append(f"<p style='margin:4px 0;'>{line}</p>")
    body = "\n".join(html_lines)
    if any("<li" in l for l in html_lines):
        body = f"<ul style='margin:8px 0;padding-left:20px;'>{body}</ul>"
    return f"""
    <div style="margin-bottom:24px;">
      <h2 style="color:#1B3A5C;font-size:18px;margin-bottom:8px;border-bottom:2px solid #e2e8f0;padding-bottom:4px;">
        {emoji} {title}
      </h2>
      <div style="font-size:14px;color:#334155;line-height:1.6;">
        {body}
      </div>
    </div>"""

def build_email(sections: dict) -> str:
    """Assemble full HTML email from sections."""
    now = get_todays_date()
    date_str = now.strftime("%A, %B %d, %Y")

    # Determine top story for subject line
    top_category = "Daily Briefing"
    if "HIGH PRIORITY" in sections.get("land", "").upper():
        top_category = "🔴 High-Priority Land Listing"
    elif sections.get("land", "").strip():
        top_category = "Land Listings"
    elif sections.get("builders", "").strip():
        top_category = "Builder Intel"

    subject = f"🏔️ Taos Build Intel — {now.strftime('%a %b %d')} | {top_category}"

    body_sections = ""
    body_sections += format_section("🔑", "TODAY'S ACTION ITEM", sections.get("action", ""))
    body_sections += format_section("🏜️", "LAND LISTINGS", sections.get("land", ""))
    body_sections += format_section("🏠", "BUILDER INTEL", sections.get("builders", ""))
    body_sections += format_section("⚡", "OFF-GRID & NM NEWS", sections.get("offgrid", ""))
    body_sections += format_section("🚐", "VAN & VEHICLE MARKET", sections.get("vehicles", ""))
    body_sections += format_section("🏕️", "BRIDGE HOUSING", sections.get("bridge", ""))
    body_sections += format_section("📚", "LEARNING RESOURCE", sections.get("learning", ""))

    dashboard = build_dashboard()

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:680px;margin:0 auto;padding:20px;background:#ffffff;">
  <div style="background:linear-gradient(135deg,#1B3A5C,#2D6A4F);color:white;padding:20px 24px;border-radius:8px 8px 0 0;">
    <h1 style="margin:0;font-size:22px;">🏔️ Taos Build Intel</h1>
    <p style="margin:4px 0 0;opacity:0.85;font-size:14px;">{date_str}</p>
  </div>
  <div style="border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;padding:24px;">
    {body_sections}
    <div style="margin-top:24px;padding-top:16px;border-top:2px solid #1B3A5C;">
      <h2 style="color:#1B3A5C;font-size:18px;margin-bottom:8px;">📊 PROJECT DASHBOARD</h2>
      {dashboard}
    </div>
    <div style="margin-top:24px;padding:12px;background:#f8fafc;border-radius:6px;font-size:12px;color:#64748b;text-align:center;">
      Taos Off-Grid Homestead Project | Budget: $350K | Phase: {CONSTRAINTS['project']['phase'].replace('_',' ').title()}<br>
      Generated by your daily intel agent — GitHub Actions + Claude API
    </div>
  </div>
</body>
</html>"""
    return subject, html

# ---------------------------------------------------------------------------
# Email sender
# ---------------------------------------------------------------------------

def send_email(subject: str, html: str):
    """Send HTML email via Gmail SMTP."""
    if not SENDER or not PASSWORD:
        log.warning("No email credentials — writing to file instead")
        out = ROOT / "data" / "last_digest.html"
        with open(out, "w") as f:
            f.write(html)
        log.info(f"Saved digest to {out}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER, PASSWORD)
            server.sendmail(SENDER, RECIPIENT, msg.as_string())
        log.info(f"✅ Email sent to {RECIPIENT}")
    except Exception as e:
        log.error(f"❌ Email failed: {e}")
        # Save locally as fallback
        out = ROOT / "data" / "last_digest.html"
        with open(out, "w") as f:
            f.write(html)
        log.info(f"Saved digest to {out}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("🏔️ Starting Taos Build Daily Digest")

    if not API_KEY:
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    sections = {}

    # Run each intelligence stream with delays to respect rate limits
    streams = [
        ("action", "Action Item", get_action_item),
        ("land", "Land Search", search_land),
        ("builders", "Builder Intel", search_builders),
        ("offgrid", "Off-Grid & NM News", search_offgrid_nm),
        ("vehicles", "Vehicle Market", search_vehicles),
        ("bridge", "Bridge Housing", search_bridge_housing),
        ("learning", "Learning Resource", search_learning),
    ]

    for key, label, fn in streams:
        log.info(f"🔍 Searching: {label}...")
        try:
            sections[key] = fn()
            log.info(f"  ✅ {label} complete ({len(sections[key])} chars)")
        except Exception as e:
            log.error(f"  ❌ {label} failed: {e}")
            sections[key] = f"⚠️ Search error: {e}"
        time.sleep(2)  # Rate limit buffer

    # Build and send email
    subject, html = build_email(sections)
    log.info(f"📧 Subject: {subject}")
    send_email(subject, html)

    # Update cache timestamp
    CACHE["last_updated"] = get_todays_date().isoformat()
    save_json(DATA / "listing_cache.json", CACHE)

    log.info("🏔️ Daily digest complete")

if __name__ == "__main__":
    main()
