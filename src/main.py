#!/usr/bin/env python3
"""
Taos Build Daily Digest v3.0 — Morning Brew style
Clean, scannable, action-first with anchor index + caller scripts.
"""

import json, os, sys, smtplib, logging, time, re
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import anthropic

# v4.0 improvements
sys.path.insert(0, str(Path(__file__).parent.parent))
from improved_email_formatter import strip_claude_preamble, extract_search_params
from digest_tracker import DigestTracker, build_tracking_footer
from table_and_fallback_fixes import get_learning_resources_for_day, format_learning_resources

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
RECIPIENT = os.environ.get("RECIPIENT_EMAIL", "RECIPIENT_EMAIL_SECRET")
SENDER = os.environ.get("SENDER_EMAIL", "")
PASSWORD = os.environ.get("SENDER_PASSWORD", "")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = 2048
DELAY = int(os.environ.get("INTER_CALL_DELAY", "30"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("taos")

def load_json(p):
    with open(p) as f: return json.load(f)
def save_json(p, d):
    with open(p, "w") as f: json.dump(d, f, indent=2)

C = load_json(DATA / "constraints.json")
CACHE = load_json(DATA / "listing_cache.json")
HIST = load_json(DATA / "learning_history.json")
def now_mt(): return datetime.now(timezone(timedelta(hours=-7)))
def today(): return now_mt().strftime("%B %d, %Y")
def today_long(): return now_mt().strftime("%A, %B %d, %Y")

# --- API ---
def ask(prompt, max_tok=MAX_TOKENS):
    client = anthropic.Anthropic(api_key=API_KEY)
    for i in range(5):
        try:
            r = client.messages.create(model=MODEL, max_tokens=max_tok,
                tools=[{"type":"web_search_20250305","name":"web_search"}],
                messages=[{"role":"user","content":prompt}])
            response = "\n".join(b.text for b in r.content if b.type=="text").strip()
            # v4.0: Apply jargon removal
            return strip_claude_preamble(response)
        except anthropic.RateLimitError:
            w = 30*(i+1)
            if i < 4: log.warning(f"Rate limit ({i+1}/5), wait {w}s"); time.sleep(w)
            else: return ""
        except Exception as e: log.error(f"API: {e}"); return ""

# --- Clean + Format ---
SKIP = [r"^I('ll| will| need to) (search|look)\b.*", r"^Let me (search|find|check)\b.*",
    r"^Based on my search\b.*", r"^Perfect\.?\s*\b.*", r"^Great\.?\s*\b.*",
    r"^Here('s| is| are) what I\b.*", r"^Searching\b.*", r"^I found\b.*",
    r"^Unfortunately\b.*", r"^I was unable\b.*", r"^I could not\b.*"]

def clean(txt):
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

def md(t):
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)',
        r'<a href="\2" style="color:#2563EB">\1</a>', t)
    t = re.sub(r"(?<![\"'>])(https?://\S+)",
        r'<a href="\1" style="color:#2563EB">\1</a>', t)
    return t

def section(anchor, emoji, title, content, border_color="#1B3A5C"):
    content = clean(content)
    if not content: return ""
    lines = content.split("\n")
    html, ltag = [], None
    def cl():
        nonlocal ltag
        if ltag: html.append(f"</{ltag}>"); ltag = None
    for raw in lines:
        s = raw.strip()
        if not s: cl(); continue
        if s in ("-","*","•"): continue
        s = md(s)
        if "HIGH PRIORITY" in s.upper() or s.startswith("🔴"):
            cl(); html.append(f'<div style="color:#dc2626;font-weight:600;background:#FEF2F2;padding:6px 10px;border-left:3px solid #dc2626;border-radius:3px;margin:6px 0">{s}</div>')
        elif s.startswith("### "):
            cl(); html.append(f'<div style="color:#2D6A4F;font-size:13px;font-weight:600;margin:10px 0 3px">{s[4:]}</div>')
        elif s.startswith("## "):
            cl(); html.append(f'<div style="color:#1B3A5C;font-size:14px;font-weight:600;margin:12px 0 4px;padding-bottom:2px;border-bottom:1px solid #E2E8F0">{s[3:]}</div>')
        elif re.match(r'^\d+\.\s', s):
            if ltag != "ol": cl(); html.append('<ol style="margin:4px 0;padding-left:22px">'); ltag = "ol"
            itxt = re.sub(r'^[0-9]+[.]\s*', '', s)
            html.append(f'<li style="margin-bottom:3px">{itxt}</li>')
        elif s.startswith("- ") or s.startswith("* "):
            if ltag != "ul": cl(); html.append('<ul style="margin:4px 0;padding-left:22px">'); ltag = "ul"
            html.append(f'<li style="margin-bottom:3px">{s[2:]}</li>')
        elif s.lower().startswith("📞") or "caller script" in s.lower():
            cl(); html.append(f'<div style="background:#EFF6FF;border-left:3px solid #3B82F6;padding:8px 12px;margin:8px 0;border-radius:3px;font-style:italic;font-size:13px">{s}</div>')
        else:
            cl(); html.append(f'<p style="margin:3px 0;line-height:1.4">{s}</p>')
    cl()
    body = "\n".join(html)
    return f'''<div id="{anchor}" style="margin-bottom:20px;border-left:3px solid {border_color};padding-left:14px">
  <div style="font-size:15px;font-weight:600;color:{border_color};margin-bottom:6px">{emoji} {title}</div>
  <div style="font-size:13px;color:#334155;line-height:1.45">{body}</div>
</div>'''

# --- Prompts ---
SCRIPT = '''Include a "📞 CALLER SCRIPT" section — a 3-sentence phone script my wife Angela can read:
"Hi, my name is Angela. My husband and I are planning a small off-grid home in Taos County, NM — [specific ask]. Could you help with [question]?"'''

def p_action():
    return ask(f"""One task for today. Off-grid tiny home, Taos County NM. $350K ALL-IN.
Builders: Zook Cabins, Mighty Small Homes, DC Structures.
Land: 2+ acres under $60K, Tres Piedras to Arroyo Hondo. Off-grid OK, water hookup not needed.

Format exactly:
**Action:** [what to do]
**Contact:** [name, phone/URL]
**Why:** [one sentence]
{SCRIPT}
Rotate: land, builders, lenders, off-grid learning, outreach. Today: {today_long()}
Output ONLY the task.""", 512)

def p_land():
    areas = ", ".join(C["land"]["target_areas"])
    return ask(f"""Land for sale in Taos County NM: {areas}. Min {C['land']['min_acres']} acres, under ${C['land']['max_price']:,}.
Legal road access. Off-grid OK — NO water/sewer/electric needed. Do NOT dismiss parcels lacking utilities.
For each: Price | Acres | Location | Water if known | Road | URL.
Under $50K with water = HIGH PRIORITY. Today: {today()}. Output ONLY listings.""")

def p_builders():
    bs = C["builders"]["active"]
    b = bs[now_mt().timetuple().tm_yday % len(bs)]
    return ask(f"""Latest on {b['name']} ({b['type']}). Site: {b['website']}. Models: {', '.join(b['models'])}.
Context: off-grid tiny home, Taos County NM, 7000ft, $350K all-in.
(1) Pricing/new models (2) Reviews (3) NM delivery (4) Comparable builders.
Bullets with links. {SCRIPT}
Today: {today()}. Output ONLY findings.""")

def p_offgrid():
    return ask(f"""Off-grid + alternative housing news for northern New Mexico:
1. NM solar incentives/legislation 2025-2026
2. Taos County building/zoning changes
3. Alternative housing that could work in Taos County — earthships, container homes, A-frames,
   dome homes, yurts as permanent structures, park models, converted buses/vans on foundation,
   or any creative small housing that is IRC/CID approvable in NM
4. NM CID updates on modular/kit homes
5. Taos-area off-grid community news, events, meetups
6. NM water rights or well drilling updates
Brief summaries with links. Today: {today()}. Output ONLY items.""")

def p_vehicles():
    vs = C["vehicle_search"]
    return ask(f"""Two searches:
SPRINTER: Recent 4x4 camper van sale prices. My value: ${C['van_sale']['balance_sheet_value']:,}. Trend?
TACOMA: {vs['make']} {vs['model']} {vs['config']}, {vs['years']}, {', '.join(vs['trims'])}, V6,
under ${vs['max_price']:,}, under {vs['max_miles']:,} mi. Regions: {', '.join(vs['search_regions'])}
Each: year, trim, miles, price, location, link. Flag Great Deals.
Today: {today()}. Output ONLY data.""")

def p_builders():
    bs = C["builders"]["active"]
    b = bs[now_mt().timetuple().tm_yday % len(bs)]
    return ask(f"""Latest on {b['name']} ({b['type']}). Site: {b['website']}. Models: {', '.join(b['models'])}.
Context: off-grid tiny home, Taos County NM, 7000ft, $350K all-in.
(1) Pricing/new models (2) Reviews (3) NM delivery (4) Comparable builders.
Bullets with links.
{SCRIPT}
Today: {today()}. Output ONLY findings.""")

def p_offgrid():
    return ask(f"""Off-grid and alternative housing news for northern New Mexico:
1. NM solar incentives or legislation 2025-2026
2. Taos County building or zoning changes
3. Alternative housing ideas for Taos County - earthships, container homes, A-frames, dome homes, yurts as permanent structures, park models, or any creative small housing that is IRC or CID approvable in NM
4. NM CID updates on modular or kit homes
5. Taos-area off-grid community news or events
6. NM water rights or well drilling updates
Brief summaries with links. Today: {today()}. Output ONLY items.""")

def p_vehicles():
    vs = C["vehicle_search"]
    rgn = ", ".join(vs["search_regions"])
    return ask(f"""Two searches:
SPRINTER: Recent 4x4 camper van sale prices. My value: ${C['van_sale']['balance_sheet_value']:,}. Trend?
TACOMA: {vs['make']} {vs['model']} {vs['config']}, {vs['years']}, {', '.join(vs['trims'])}, V6, under ${vs['max_price']:,}, under {vs['max_miles']:,} mi. Regions: {rgn}.
Each: year, trim, miles, price, location, link. Flag Great Deals.
Today: {today()}. Output ONLY data.""")

def p_bridge():
    return ask(f"""Bridge housing near Taos NM:
YURTS: Colorado Yurt Company + Pacific Yurts pricing for 20-24ft insulated. Sales? Lead times?
{SCRIPT}
RV/5TH WHEEL: For sale in NM or southern CO, under $45K, year-round at 7000ft. Specific listings with price, year, model, location, link.
FURNISHED RENTALS: Taos month-to-month furnished under $2500. Specific listings from Furnished Finder, Airbnb monthly, Craigslist. Price, location, link.
Bullets with links. Skip empty sections. Today: {today()}. Output ONLY options.""")

def p_learn():
    h = ", ".join(HIST[-20:]) if HIST else "none"
    topics = ["off-grid solar tutorial", "SIP panel construction", "NM building code owner-builders",
        "cistern water sizing", "Blaze King setup", "construction-to-perm loan", "NM water rights",
        "off-grid septic", "EG4 inverter guide", "Taos off-grid community",
        "IronRidge ground mount", "propane off-grid", "modular foundation mountain",
        "snow load engineering", "Starlink rural setup"]
    t = topics[now_mt().timetuple().tm_yday % len(topics)]
    r = ask(f"""ONE free resource about: {t}. YouTube, blogs, govt guides.
Avoid: {h}. Format: Title | Source | URL | 2-sentence summary.
Today: {today()}. Output ONLY the resource.""", 512)
    HIST.append(t)
    if len(HIST) > 60: HIST[:] = HIST[-60:]
    save_json(DATA / "learning_history.json", HIST)
    return r

# --- Email ---
def dashboard():
    d = (datetime(2028,6,1,tzinfo=timezone(timedelta(hours=-7))) - now_mt()).days
    bs = " | ".join(f"{b['name']}: {b['status'].replace('_',' ')}" for b in C["builders"]["active"])
    return f'''<table style="width:100%;border-collapse:collapse;font-size:12px;background:#F8FAFC;border-radius:4px">
<tr><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0;width:110px;font-weight:600">Budget</td><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0">$350K all-in</td></tr>
<tr><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0;font-weight:600">Committed</td><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0">${C["project"]["committed_spend"]:,}</td></tr>
<tr><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0;font-weight:600">Phase</td><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0">{C["project"]["phase"].replace("_"," ").title()}</td></tr>
<tr><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0;font-weight:600">Days Left</td><td style="padding:4px 10px;border-bottom:1px solid #e2e8f0">{d}</td></tr>
<tr><td style="padding:4px 10px;font-weight:600">Builders</td><td style="padding:4px 10px">{bs}</td></tr>
</table>'''

def build_email(S):
    dt = now_mt()
    top = "Daily Briefing"
    if "HIGH PRIORITY" in S.get("land","").upper(): top = "High-Priority Land"
    elif S.get("land","").strip(): top = "Land Listings"
    subj = f"Taos Build Intel - {dt.strftime('%a %b %d')} | {top}"

    # Build sections
    sec = ""
    sec += section("action", "🔑", "TODAY'S ACTION ITEM", S.get("action",""), "#2563EB")
    sec += section("land", "🏜️", "LAND LISTINGS", S.get("land",""), "#D97706")
    sec += section("builders", "🏠", "BUILDER INTEL", S.get("builders",""), "#059669")
    sec += section("offgrid", "⚡", "OFF-GRID NEWS & HOUSING IDEAS", S.get("offgrid",""), "#7C3AED")
    sec += section("dash", "📊", "PROJECT DASHBOARD", dashboard(), "#1B3A5C")
    sec += section("tacoma", "🚐", "TACOMA HUNTER & VAN MARKET", S.get("vehicles",""), "#64748B")
    sec += section("bridge", "🏕️", "BRIDGE HOUSING & RENTALS", S.get("bridge",""), "#64748B")
    sec += section("learn", "📚", "LEARNING RESOURCE", S.get("learning",""), "#64748B")

    # Anchor index
    idx_items = [
        ("action", "🔑 Action"), ("land", "🏜️ Land"), ("builders", "🏠 Builders"),
        ("offgrid", "⚡ Off-Grid"), ("dash", "📊 Dashboard"),
        ("tacoma", "🚐 Tacoma"), ("bridge", "🏕️ Housing"), ("learn", "📚 Learn")]
    idx = " &nbsp;·&nbsp; ".join(
        f'<a href="#{a}" style="color:#fff;text-decoration:none;font-size:11px">{l}</a>'
        for a, l in idx_items)

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:620px;margin:0 auto;padding:12px;background:#fff">
<div style="background:linear-gradient(135deg,#1B3A5C,#2D6A4F);color:#fff;padding:14px 18px;border-radius:6px 6px 0 0">
  <div style="font-size:18px;font-weight:700">🏔️ Taos Build Intel</div>
  <div style="font-size:12px;opacity:0.8;margin:2px 0 8px">{dt.strftime("%A, %B %d, %Y")} | $350K All-In | Pre-Land Phase</div>
  <div style="border-top:1px solid rgba(255,255,255,0.3);padding-top:6px">{idx}</div>
</div>
<div style="border:1px solid #e2e8f0;border-top:none;border-radius:0 0 6px 6px;padding:16px">
  {sec}
  <div style="margin-top:14px;padding:8px;background:#f8fafc;border-radius:4px;font-size:10px;color:#94a3b8;text-align:center">
    Taos Off-Grid Homestead | GitHub Actions + Claude API
  </div>
</div></body></html>'''
    return subj, html

# --- Send ---
def send(subj, html):
    if not SENDER or not PASSWORD:
        (ROOT/"data"/"last_digest.html").write_text(html); return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj; msg["From"] = SENDER; msg["To"] = RECIPIENT
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls(); s.login(SENDER, PASSWORD)
            s.sendmail(SENDER, RECIPIENT, msg.as_string())
        log.info(f"Sent to {RECIPIENT}")
    except Exception as e:
        log.error(f"Send failed: {e}")
        (ROOT/"data"/"last_digest.html").write_text(html)

# --- Main ---
def main():
    log.info("v3.0 Starting")
    if not API_KEY: log.error("No API key"); sys.exit(1)
    S = {}
    streams = [
        ("action",   "Action",    p_action),
        ("land",     "Land",      p_land),
        ("builders", "Builders",  p_builders),
        ("offgrid",  "Off-Grid",  p_offgrid),
        ("vehicles", "Vehicles",  p_vehicles),
        ("bridge",   "Bridge",    p_bridge),
        ("learning", "Learning",  p_learn)]
    for k, label, fn in streams:
        log.info(f"{label}...")
        try:
            S[k] = fn()
            log.info(f"  OK {label} ({len(S[k])}ch)")
        except Exception as e:
            log.error(f"  FAIL {label}: {e}"); S[k] = ""
        time.sleep(DELAY)
    subj, html = build_email(S)
    log.info(f"Subject: {subj}")
    send(subj, html)
    # Always save a local copy for review
    (ROOT / "data" / "last_digest.html").write_text(html)
    log.info("Saved local copy to data/last_digest.html")
    CACHE["last_updated"] = now_mt().isoformat()
    save_json(DATA / "listing_cache.json", CACHE)
    log.info("Done")

if __name__ == "__main__":
    main()
