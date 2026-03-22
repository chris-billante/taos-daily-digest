# 🏔️ Taos Build Daily Digest

Automated daily intelligence agent for the Taos County off-grid homestead project. Runs via GitHub Actions, searches the web using Claude API, and emails a formatted digest every morning at 7:00 AM Mountain Time.

## What It Does

Every morning, this agent searches 7 intelligence streams and emails you a formatted digest:

| Stream | What It Searches |
|---|---|
| 🔑 Action Item | One specific task for today (rotates through phases) |
| 🏜️ Land Listings | LandWatch, Zillow, Realtor.com — Taos County, 3+ acres, <$55K |
| 🏠 Builder Intel | Rotating: Zook Cabins, Mighty Small Homes, DC Structures |
| ⚡ Off-Grid & NM News | Solar incentives, water rights, CID updates, Taos County regs |
| 🚐 Van & Vehicle Market | Sprinter values + Tacoma Double Cab LB 4WD listings |
| 🏕️ Bridge Housing | Yurt pricing, used RVs, Taos rental market |
| 📚 Learning Resource | One curated off-grid tutorial, guide, or video per day |

Plus a **Project Dashboard** showing budget, phase, days to target, and builder status.

## Cost

- **GitHub Actions**: Free (uses ~7 min/day of 2,000 free monthly minutes)
- **Claude API**: ~$3–8/month (7 web searches per day × ~$0.02–0.04 each)
- **Total**: Under $10/month

## Setup (15 minutes)

### 1. Get an Anthropic API Key

Go to [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key.
Add a few dollars of credit ($10 will last 1-2 months).

### 2. Get a Gmail App Password

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Enable 2FA if not already on
3. Create app password for "Mail" → save the 16 characters

### 3. Create GitHub Repo

```bash
# Create a private repo called taos-daily-digest
# Unzip the download, then:
cd taos-daily-digest
git init && git add . && git commit -m "🏔️ init"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/taos-daily-digest.git
git push -u origin main
```

### 4. Add Secrets

In your repo → **Settings** → **Secrets and variables** → **Actions**, add:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (sk-ant-...) |
| `SENDER_EMAIL` | Your Gmail address |
| `SENDER_PASSWORD` | The 16-char Gmail app password (no spaces) |

### 5. Test It

Go to **Actions** tab → **Taos Build Daily Digest** → **Run workflow**

Check your email in 2-3 minutes. If it works, it runs automatically every morning.

## Customization

### Advancing Phases

Edit `data/constraints.json` and change `"phase"`:
- `"pre-land"` — Searching for land, contacting realtors
- `"land-closing"` — Found land, closing, filing permits
- `"construction"` — Active build
- `"move-in"` — Moved in, Phase 2-4 upgrades

### Updating Budget or Targets

All project parameters live in `data/constraints.json`. Edit directly on GitHub:
- Budget ceiling, land target areas, builder list
- Vehicle search criteria
- Van sale targets

### Changing the Schedule

Edit `.github/workflows/daily-digest.yml`:
```yaml
- cron: '0 14 * * *'    # 7 AM MT (MST, UTC-7)
- cron: '0 13 * * *'    # 7 AM MT (MDT, UTC-6, summer)
- cron: '0 14 * * 1-5'  # Weekdays only
```

### Adding a Builder

Add to the `"active"` array in `data/constraints.json`:
```json
{
  "name": "New Builder",
  "models": ["Model A"],
  "type": "modular",
  "all_in_low": 200000,
  "all_in_high": 350000,
  "website": "newbuilder.com",
  "status": "research"
}
```

## Troubleshooting

- **Email not arriving?** Check spam. Verify secrets in GitHub Settings.
- **Workflow disabled?** GitHub disables crons on inactive repos. Push a small commit to reactivate.
- **API errors?** Check your Anthropic credit balance at console.anthropic.com.
- **Wrong time?** Cron is UTC. MST = UTC-7. MDT = UTC-6.

## Project Constraints

| Parameter | Value |
|---|---|
| Budget | $350,000 all-in ceiling |
| Land | $35K–$60K, Tres Piedras–Carson corridor |
| Builders | Zook Cabins, Mighty Small Homes, DC Structures |
| Off-grid | EG4 solar, Blaze King, Rinnai, cistern/well, septic |
| Timeline | Land acquisition ~2028 |
| Financing | Cash land → construction loan → refi to perm |
