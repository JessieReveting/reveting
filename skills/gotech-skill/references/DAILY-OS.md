# GoTech Daily Operating System
# Your Morning Command Center — Start Here Every Day
# Last Updated: June 24, 2026

---

## ⏰ FIRST 5 MINUTES: OPEN THESE

  1. Open Revenue Dashboard:     open ~/Documents/GoTechSolutions/startup/revenue-dashboard.html
  2. Open Command Center:        open ~/Documents/GoTechSolutions/startup/command-center.html
  3. Run daily workflow:         cd ~/Documents/GoTechSolutions/startup && python3 workflow.py --mode daily

---

## 📊 CHECK THESE NUMBERS (2 minutes)

  Cash Balance:     python3 workflow.py --mode cash-status
  Pipeline:         python3 scripts/deal-pipeline.py --mode status
  Revenue Forecast: python3 scripts/revenue-forecast.py --months 3

  Write today's numbers here:
  ┌──────────────────────────────────────────┐
  │ Date: ___________                        │
  │ Cash: $___________                       │
  │ MRR:  $___________                       │
  │ Leads: __________  Clients: __________   │
  │ Pipeline Value: $___________             │
  │ Days to $1M: ___________                 │
  └──────────────────────────────────────────┘

---

## 🔥 PRIORITY ACTIONS (DO THESE EVERY DAY)

### MORNING BLOCK (30 min) — REVENUE GENERATION

  [ ] Send 20 outreach emails (pick from campaign templates)
      Use: python3 scripts/email-outreach.js --template prospecting --dry-run
      Then send via: python3 scripts/email-sender.py --to [email] --template prospecting
  
  [ ] Send 10 LinkedIn connection requests
      Use: python3 scripts/linkedin-autoconnect.py --limit 10 --dry-run
  
  [ ] Follow up with 5 leads (stage: contacted or qualified)
      Use: python3 workflow.py --mode lead-list --stage contacted
      Then: python3 workflow.py --mode lead-advance --name [id] --stage qualified

### MIDDAY BLOCK (30 min) — CONTENT + PIPELINE

  [ ] Check content calendar for today's episode/short
      Use: python3 workflow.py --mode content-plan
  
  [ ] Review stuck deals (>7 days in same stage)
      Use: python3 scripts/deal-pipeline.py --mode stuck
  
  [ ] Log any new leads or conversions
      Use: python3 workflow.py --mode lead-add --name "X" --email "X" --source "X" --value X
      Use: python3 workflow.py --mode cash-update --amount X --note "Client payment"

### AFTERNOON BLOCK (60 min) — CALLS + CLOSES

  [ ] Take 2-3 discovery/qualification calls
      Script: templates/deal-followup.md (Qualified stage)
  
  [ ] Send 1-2 proposals
      Use: python3 workflow.py --mode lead-advance --name [id] --stage proposal
  
  [ ] Follow up on open proposals
      Use: python3 scripts/deal-pipeline.py --mode remind

### EVENING BLOCK (15 min) — LOG + PLAN

  [ ] Log today's revenue activity
      Use: python3 scripts/revenue-accelerator.py --mode track --outreach 20 --replies 2 --calls 2 --closed 0 --revenue 0
  
  [ ] Update cash if any new money came in
      Use: python3 workflow.py --mode cash-update --amount X --note "Source"
  
  [ ] Check weekly progress vs plan
      Use: python3 scripts/weekly-accountability.py --week 1
  
  [ ] Write tomorrow's top 3 priorities:
      1. _________________________________
      2. _________________________________
      3. _________________________________

---

## 📋 WEEKLY RITUALS (DO ONCE PER WEEK)

### MONDAY MORNING
  [ ] Run weekly report: python3 workflow.py --mode weekly
  [ ] Review 60-day plan progress: open 60-day-revenue-plan.md
  [ ] Set this week's targets (write below):
      Week ____ Target: $____ MRR, ____ new clients, ____ outreach touches

### WEDNESDAY MIDDAY
  [ ] Check pipeline health: python3 scripts/deal-pipeline.py --mode report
  [ ] Review content performance: python3 scripts/content-revenue.py --mode analyze
  [ ] Adjust strategy if behind plan

### FRIDAY AFTERNOON
  [ ] Run accountability report: python3 scripts/weekly-accountability.py --week [N]
  [ ] Celebrate wins (write 3):
      1. _________________________________
      2. _________________________________
      3. _________________________________
  [ ] Identify lessons learned (write 3):
      1. _________________________________
      2. _________________________________
      3. _________________________________

---

## 🎯 THIS WEEK'S TARGETS (FILL IN EACH MONDAY)

  Week 1 (June 24-30): FOUNDATION PHASE
  ┌──────────────────────────────────────────────┐
  │ New Clients Target:     10                   │
  │ MRR Target:             $5,000               │
  │ Outreach Target:        1,400 (200/day)      │
  │ Calls Target:           14 (2/day)           │
  │ Proposals Target:       5                    │
  │ Revenue Target:         $5,000               │
  │ Actual:                 _____ / _____ / _____│
  └──────────────────────────────────────────────┘

  Week 2 (July 1-7):
  ┌──────────────────────────────────────────────┐
  │ New Clients Target:     15                   │
  │ MRR Target:             $10,000              │
  │ Outreach Target:        2,800 (400/day)      │
  │ Calls Target:           21 (3/day)           │
  │ Proposals Target:       8                    │
  │ Revenue Target:         $10,000              │
  │ Actual:                 _____ / _____ / _____│
  └──────────────────────────────────────────────┘

  Week 3 (July 8-14):
  ┌──────────────────────────────────────────────┐
  │ New Clients Target:     15                   │
  │ MRR Target:             $15,000              │
  │ Outreach Target:        2,800 (400/day)      │
  │ Calls Target:           28 (4/day)           │
  │ Proposals Target:       10                   │
  │ Revenue Target:         $15,000              │
  │ Actual:                 _____ / _____ / _____│
  └──────────────────────────────────────────────┘

  (Continue for Weeks 4-10 following the 60-day plan)

---

## 📁 QUICK REFERENCE — ALL FILES

  STARTUP/
  ├── workflow.py                    ← Master engine (cash, leads, clients, metrics)
  ├── 60-day-revenue-plan.md         ← Full revenue plan with math
  ├── SUMMARY-UPDATE.md              ← This file's companion
  │
  ├── revenue-dashboard.html         ← Open daily — revenue focus
  ├── command-center.html            ← Open daily — full overview
  ├── analytics-dashboard.html       ← Weekly — deep analytics
  ├── crm-dashboard.html             ← Pipeline management
  ├── youtube-dashboard.html         ← YouTube metrics
  ├── cash-tracker.html              ← Cash tracking
  ├── funding-faith-future.html      ← FFF landing page
  ├── gotech-pricing.html            ← Pricing page
  │
  ├── scripts/
  │   ├── revenue-accelerator.py     ← Campaign execution + tracking
  │   ├── deal-pipeline.py           ← Deal lifecycle management
  │   ├── content-revenue.py         ← Content → revenue attribution
  │   ├── weekly-accountability.py   ← Weekly scorecard
  │   ├── revenue-forecast.py        ← Growth projections
  │   ├── content-planner.py         ← Auto topic/guest suggestions
  │   ├── email-sender.py            ← Send real emails (NEEDS KEY)
  │   ├── email-outreach.js          ← Email templates + sending
  │   ├── linkedin-autoconnect.py    ← LinkedIn automation (NEEDS KEY)
  │   ├── linkedin-prospect-finder.js← Prospect scoring
  │   ├── lead-capture.js            ← Webhook server (port 3456)
  │   ├── client-onboarding.js       ← SOW + welcome generator
  │   ├── ghl-sync.js               ← GHL CRM sync (NEEDS KEY)
  │   ├── youtube-seo-pusher.py      ← Push SEO to YT (NEEDS KEY)
  │   ├── youtube-thumbnails.js      ← Thumbnail generator
  │   ├── stripe-links.py            ← Payment links (NEEDS KEY)
  │   ├── canva-quote-cards.js       ← Quote cards (NEEDS KEY)
  │   ├── cash-alert.py              ← macOS cash notifications
  │   ├── notify.py                 ← Notification helper
  │   ├── daily-digest.py            ← Weekly digest email
  │   ├── podcast-submit.py          ← RSS + platform submission
  │   ├── podcast-rss.js             ← RSS feed generator
  │   ├── podcast-workflow.sh        ← StreamYard pipeline
  │   ├── go-live.sh                 ← One-click livestream
  │   ├── cron-manager.py            ← Automated job scheduler
  │   ├── data-taxi-sync.js          ← DATA TAXI bi-di sync
  │   ├── recent-files.js            ← Drive scanner
  │   ├── gdrive-import.js           ← Google Drive import
  │   ├── ai-conversation-readers.js ← AI tool aggregator
  │   ├── calendar-connector.js      ← Calendar integration
  │   ├── pipeline-test.sh           ← 15-section test suite
  │   └── tdss-export-csv.py         ← Google Sheets export
  │
  ├── templates/
  │   ├── campaigns/                 ← 6 service campaigns + founding member
  │   ├── email/                     ← prospecting, followup, welcome
  │   ├── sow-template.md            ← Statement of Work
  │   ├── deal-followup.md           ← Stage-specific follow-ups
  │   ├── content-to-sales-guide.md  ← CTA + conversion playbook
  │   └── accountability-template.md ← Report structure
  │
  ├── cron/jobs.json                 ← 9 automated jobs
  ├── data/                          ← cash, leads, clients, metrics
  └── assets/billion-dollar-skill/   ← 39 downloaded files (48GB)

---

## 🚀 GETTING YOUR FIRST API KEY (TODAY'S PRIORITY)

  Easiest win right now — Gmail App Password:
  1. Go to myaccount.google.com/apppasswords
  2. Generate password for bizrunner@gmail.com
  3. Run: export GMAIL_APP_PASSWORD=your_password_here
  4. Test: python3 scripts/email-sender.py --to bizrunner@gmail.com --subject "Test" --body "It works" --test

  This unlocks:
    - Email sender (cold outreach)
    - Daily digest emails
    - Weekly accountability reports
    - Proposal sending

---

## 📊 PHASE PROGRESS TRACKER

  Phase 1: Foundation    [ ] Started  → Target: $5K MRR by June 30
  Phase 2: Launch        [ ] Started  → Target: $15K MRR by July 14
  Phase 3: Scale         [ ] Started  → Target: $35K MRR by July 31
  Phase 4: Accelerate    [ ] Started  → Target: $65K MRR by Aug 15
  Phase 5: Sprint        [ ] Started  → Target: $85K MRR by Aug 31
  Phase 6: $1M ARR DAY   [ ] SEPT 1  → $100K MRR = $1,000,000 ARR 🚀

---

## 💡 RULES

  1. Start with revenue activities FIRST (before anything else)
  2. Every outreach touch gets logged (even in dry-run)
  3. Cash updates happen the moment money comes in
  4. Weekly accountability happens every Friday (no exceptions)
  5. Content serves revenue (every post has a CTA)
  6. No tool-building without a revenue use case first

---

*This is your daily bible. Open it every morning. Follow the flow. Hit the targets.*
*69 days to $1M. Let's go.*
