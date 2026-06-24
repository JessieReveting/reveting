# GoTech Skill — Full Revenue Stack for Go Livestream / Reveting

This skill contains the complete revenue acceleration stack for GoTech Solutions,
including all scripts, templates, dashboards, and workflows needed to operate
the Go Livestream show and Reveting GTM services.

## North Star
$1,000,000 cash in bank ASAP
Starting: $500 (June 24, 2026)
Target: September 1, 2026 (69 days)

## What's Included

### Revenue Stack Scripts (34 scripts)
- **workflow.py** — Master orchestrator (cash, leads, clients, metrics, reports)
- **revenue-accelerator.py** — Campaign execution + daily tracking
- **deal-pipeline.py** — Full deal lifecycle (prospect → close)
- **content-revenue.py** — Content → revenue attribution
- **weekly-accountability.py** — Weekly scorecard + variance analysis
- **revenue-forecast.py** — Growth projections + Monte Carlo simulation
- **content-planner.py** — Auto-generate episode topics + guest matches
- **email-sender.py** — Gmail SMTP + OAuth2 sender
- **email-outreach.js** — Email templates + sending
- **linkedin-autoconnect.py** — LinkedIn automation
- **linkedin-prospect-finder.js** — Prospect scoring + GHL sync
- **lead-capture.js** — Webhook server (port 3456)
- **client-onboarding.js** — SOW + welcome generator
- **ghl-sync.js** — GoHighLevel CRM integration
- **youtube-seo-pusher.py** — Push SEO to YouTube via API
- **youtube-thumbnails.js** — Thumbnail generator (1280x720)
- **stripe-links.py** — Payment link generator
- **canva-quote-cards.js** — Quote card generator (4 styles)
- **cash-alert.py** — macOS cash notifications
- **notify.py** — Reusable notification helper
- **daily-digest.py** — Weekly digest email generator
- **podcast-submit.py** — Podcast RSS + platform submission
- **podcast-rss.js** — RSS feed generator
- **podcast-workflow.sh** — StreamYard → YouTube → Shorts pipeline
- **go-live.sh** — One-click livestream startup
- **cron-manager.py** — Automated job scheduler (9 jobs)
- **data-taxi-sync.js** — DATA TAXI bi-directional sync
- **recent-files.js** — Drive scanner + cloud storage status
- **gdrive-import.js** — Google Drive file import
- **ai-conversation-readers.js** — Claude/ChatGPT/Perplexity/Gemini aggregator
- **calendar-connector.js** — Google Calendar + Outlook integration
- **pipeline-test.sh** — 15-section end-to-end test suite
- **tdss-export-csv.py** — Google Sheets export utility
- **startup.py** — Legacy orchestrator v1

### Campaign Templates (6 files)
- **ai-ops.md** — AI Operations ($500/mo) outreach campaign
- **communications.md** — Communications ($300/mo) campaign
- **cro.md** — Technical CRO ($750/mo) campaign
- **golive.md** — Go Live Stream ($400/mo) campaign
- **bundle.md** — Full Bundle ($1,750/mo) campaign
- **founding-member.md** — 50% off first 3 months special

### Reference Templates
- **deal-followup.md** — Stage-specific follow-up scripts
- **content-to-sales-guide.md** — CTA + conversion playbook
- **accountability-template.md** — Weekly report structure
- **sow-template.md** — Statement of Work template

### HTML Dashboards (9 files)
- **revenue-dashboard.html** — Daily revenue tracker with targets
- **command-center.html** — Single pane of glass
- **analytics-dashboard.html** — Full analytics across all platforms
- **crm-dashboard.html** — CRM pipeline management
- **youtube-dashboard.html** — YouTube analytics
- **cash-tracker.html** — Daily cash tracker
- **funding-faith-future.html** — Funding landing page
- **gotech-pricing.html** — Pricing page
- **lead-form.html** — Lead capture form

### Data Files
- **cash.json** — Transaction history
- **leads.json** — Lead pipeline
- **clients.json** — Active clients
- **metrics.json** — Historical snapshots
- **content_calendar.json** — Content schedule

### Cron Jobs (9 automated)
- Metrics Update (every 60 min)
- Daily Report (daily 9am)
- Weekly Report (Monday 8am)
- Data Backup (daily 2am)
- Content Plan (Sunday 6pm)
- Lead Follow-up (every 4 hours)
- Cash Alert (daily 10am)
- YouTube Check (every 6 hours)
- Orphan Check (daily 3am)

## Quick Start

```bash
# Daily workflow
python3 workflow.py --mode daily

# Check cash
python3 workflow.py --mode cash-status

# Revenue forecast
python3 scripts/revenue-forecast.py --chart --simulate

# Open dashboards
open revenue-dashboard.html
open command-center.html
```

## API Keys Needed

1. GMAIL_APP_PASSWORD — myaccount.google.com/apppasswords
2. YOUTUBE_API_KEY — console.cloud.google.com
3. GHL_API_KEY — GHL → Settings → Developer
4. PROXYCURL_API_KEY — nubela.co/proxycurl
5. STRIPE_SECRET_KEY — stripe.com/developers
6. CANVA_API_KEY — canva.com/developers
7. VERCEL_TOKEN — vercel token

## 60-Day Revenue Plan

Phase 1: Foundation    June 24-30   → $5K MRR, 10 clients
Phase 2: Launch        July 1-14    → $15K MRR, 30 clients
Phase 3: Scale         July 15-31   → $35K MRR, 70 clients
Phase 4: Accelerate    Aug 1-15     → $65K MRR, 130 clients
Phase 5: Sprint        Aug 16-31    → $85K MRR, 170 clients
Phase 6: Launch Day    Sept 1      → $100K MRR = $1M ARR

## Service Pricing

- AI Operations:     $500/mo ($6,000/yr)
- Communications:   $300/mo ($3,600/yr)
- Technical CRO:     $750/mo ($9,000/yr)
- Go Live Stream:    $400/mo ($4,800/yr)
- Full Bundle:       $1,750/mo ($21,000/yr)

## Attribution

Built by David Goecke / GoTech Solutions
Part of the sitedesigner/golivestream repository
