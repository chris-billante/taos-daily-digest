#!/usr/bin/env python3
"""
Taos Build Daily Digest v4.0 — With all improvements
- Claude jargon removed
- Search parameters shown
- Priority color coding
- GitHub tracking
- Email-safe HTML
- Learning resource fallback
"""

import json, os, sys, smtplib, logging, time, re
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import anthropic

# v4.0 improvements
sys.path.insert(0, str(Path(__file__).parent.parent))
from improved_email_formatter import strip_claude_preamble
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
