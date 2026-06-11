# Győr Menü — Cronok és automatikák

_Last updated: 2026-06-11_

## Source of truth
- **Operational source of truth:** actual cron configuration + local runtime config
- **Human-readable tracking:** TickTick task `Győr Menü – Cronok és automatikák`
- **Publication rule:** preview / local change first → short changelog to Peter → explicit approval required before commit/push or live publication

---

## 1. Gateway cron jobs (active)

These are the main scheduled automations managed by OpenClaw Gateway.
All Győr Menü jobs use timezone:
- `Europe/Budapest`

### A. Weekly menu build — Monday 09:00
- **Name:** `Győr Menü weekly build — Monday 09:00`
- **Job ID:** `f3be779e-62ef-4e0a-9275-e4b144304b74`
- **Schedule:** `0 9 * * 1`
- **Status:** active
- **Purpose:** first Monday refresh for most weekly menu sources
- **What it does:**
  1. scans screenshot inboxes
  2. runs build pipeline from the Review Workspace sheet
  3. rebuilds `public/data/feed.json`
  4. runs automated feed quality review
  5. sends a short Telegram summary with counts for:
     - updated / acceptable menus
     - suspicious menus
     - unavailable menus
     - screenshot-needed restaurants with source links where possible
- **Does it publish live automatically?** No — rebuild/report only

### B. Weekly menu build — Monday 11:00
- **Name:** `Győr Menü weekly build — Monday 11:00`
- **Job ID:** `3658f3e8-a811-429a-8bcd-d114bdbf5280`
- **Schedule:** `0 11 * * 1`
- **Status:** active
- **Purpose:** second Monday pass for restaurants that publish later
- **Includes:** the same automated quality review and summary format as the 09:00 run
- **Does it publish live automatically?** No

### C. Radó refresh — Tuesday 09:00
- **Name:** `Győr Menü Radó refresh — Tuesday 09:00`
- **Job ID:** `d7251e21-1c9a-418a-8782-b61e38c27d58`
- **Schedule:** `0 9 * * 2`
- **Status:** active
- **Purpose:** catch Radó by Westy’s Tuesday publication pattern
- **Includes:** feed quality review after rebuild
- **Does it publish live automatically?** No

### D. Radó refresh — Tuesday 11:00
- **Name:** `Győr Menü Radó refresh — Tuesday 11:00`
- **Job ID:** `2ebf067a-6183-4528-84cc-c45c95a4e52c`
- **Schedule:** `0 11 * * 2`
- **Status:** active
- **Purpose:** second Tuesday retry pass
- **Includes:** feed quality review after rebuild
- **Does it publish live automatically?** No

### E. Daily random restaurant audit — 09:30
- **Name:** `Győr Menü daily random audit — 09:30`
- **Job ID:** `eea0d04c-e083-4f39-a666-ec6c6682c287`
- **Schedule:** `30 9 * * *`
- **Status:** active
- **Purpose:** run the random daily QA spotlight process and send Peter a short audit summary
- **What it does:**
  1. runs `python3 scripts/daily_random_restaurant_audit.py`
  2. uses the audit output as the summary base
  3. highlights whether detected issues look isolated or broader across the feed
- **Does it publish live automatically?** No — QA report only

---

## 2. Feedback cron

### Daily feedback digest — 12:00
- **Type:** OpenClaw Gateway cron
- **Schedule:** `0 12 * * *`
- **Time zone:** `Europe/Budapest`
- **Status:** active
- **Purpose:** check whether new Google Form feedback arrived in the last 24 hours and send Peter a short summary + suggested actions
- **Behavior:**
  - reads the linked Google Form response sheet
  - checks the last 24 hours of entries
  - summarizes the feedback types and affected restaurants
  - proposes likely next steps
  - does **not** publish anything live

---

## 3. Current feedback automation

### Google Form
- **Title:** `Győr Menü – Visszajelzés és javaslat`
- **Form ID:** `1E44kxzf1Ryhdam9VYpDvkKaLSi97dygONOTtk06sbEA`
- **Public responder URL:**
  - `https://docs.google.com/forms/d/e/1FAIpQLSf6AunOQ15BUC4FcisN_DqhRKsKrr3oMdyyCxClZATe3Hasyg/viewform`
- **Status:** live
- **Used for:**
  - menu inaccuracy reports
  - restaurant suggestions
  - feature suggestions

### Linked response sheet
- **Spreadsheet:** `Győr Menü – Hibajelzések`
- **Sheet ID:** `1fNro-xh51Ca3GO0wY8-EbIcKhmK6DSFkVIRyRdvuSNs`
- **Status:** live
- **Location:** Győr Menü Drive project folder

---

## 4. Build / publish workflow

### Current flow
1. source data arrives from website parsers / OCR / sheet review / screenshot flow
2. build pipeline generates `public/data/feed.json`
3. preview can be checked at:
   - `http://89.167.67.46:8787`
4. only after explicit Peter approval:
   - commit
   - push to GitHub
   - Vercel deploys live

### Important rule
- **Never treat cron rebuild as automatic approval to publish**
- Crons may rebuild and report, but **live publication still requires explicit Peter approval**

---

## 5. Current automation coverage summary

### Automated / structured
- several website / PDF / HTML sources are automated
- weekly rebuild cron windows are in place

### Semi-automated / OCR / image-based
- some restaurants still rely on image/OCR or manual review assistance
- future priority: reduce recurring screenshot dependency for Facebook/image-only sources

---

## 6. Recommended maintenance practice

When cron/automation changes are made:
1. update actual cron config
2. update this file
3. update TickTick task `Győr Menü – Cronok és automatikák`
4. if publish behavior changes, explicitly re-check the approval-before-push rule
