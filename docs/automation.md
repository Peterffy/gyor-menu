# Győr Menü — Cronok és automatikák

_Last updated: 2026-06-12_

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
- **Model:** `Flash`
- **Status:** active
- **Purpose:** run the random daily QA spotlight process and send Peter a short audit summary
- **What it does:**
  1. runs `python3 scripts/daily_random_restaurant_audit.py`
  2. uses the audit output as the summary base
  3. highlights whether detected issues look isolated or broader across the feed
- **Does it publish live automatically?** No — QA report only

### F. Sunday next-week publish — 17:00
- **Name:** `Győr Menü Sunday next-week publish — 17:00`
- **Schedule:** `0 17 * * 0`
- **Status:** active
- **Purpose:** switch the public site to next-week dating early on Sunday evening when enough Monday/weekly menus are already available
- **What it does:**
  1. computes the next Monday date
  2. runs the full build pipeline with `--today-override <next-monday>`
  3. reviews the output briefly
  4. publishes if the result is sane and relevant
  5. sends Peter a short Hungarian summary
- **Does it publish live automatically?** Yes — if the build result is sane and relevant

### G. Sunday next-week publish retry — 21:00
- **Name:** `Győr Menü Sunday next-week publish retry — 21:00`
- **Schedule:** `0 21 * * 0`
- **Status:** active
- **Purpose:** catch restaurants that publish later on Sunday and improve Monday completeness before the workweek starts
- **What it does:**
  1. computes the next Monday date
  2. runs the full build pipeline with `--today-override <next-monday>`
  3. reviews the output briefly
  4. publishes if new sane/relevant changes appeared since the earlier pass
  5. sends Peter a short Hungarian summary about what changed vs the 17:00 pass
- **Does it publish live automatically?** Yes — if new sane/relevant changes appeared

---

## 2. Feedback cron

### Feedback watch — every 2 hours between 08:00 and 20:00
- **Type:** OpenClaw Gateway cron
- **Name:** `Győr Menü feedback watch — every 2h (08-20)`
- **Schedule:** `0 8,10,14,16,18,20 * * *`
- **Time zone:** `Europe/Budapest`
- **Model:** `Flash`
- **Status:** active
- **Purpose:** check the feedback tracker during the day and message Peter only when genuinely new feedback arrived
- **Behavior:**
  - reads the linked Google Form response sheet through `scripts/feedback_monitor.py watch`
  - keeps local seen-state in workspace memory so old rows are not re-announced
  - sends **no message** when there is nothing new
  - does **not** publish anything live

### Daily feedback digest — 12:00
- **Type:** OpenClaw Gateway cron
- **Name:** `Győr Menü feedback digest — daily 12:00`
- **Schedule:** `0 12 * * *`
- **Time zone:** `Europe/Budapest`
- **Model:** `Flash`
- **Status:** active
- **Purpose:** send a noon summary of feedback from the last 24 hours plus suggested next steps
- **Behavior:**
  - reads the linked Google Form response sheet through `scripts/feedback_monitor.py daily`
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
- **Default rule:** never treat a cron rebuild as automatic approval to publish.
- **Exception:** the two Sunday next-week publication jobs (`17:00` and `21:00`) are intentionally allowed to publish live when their result is sane/relevant, because that is their explicit purpose.
- Outside that Sunday next-week exception, cron runs may rebuild and report, but **live publication still requires explicit Peter approval**.

---

## 5. Sunday evening 20-second verification checklist

Use this right after the Sunday `17:00` publish, and optionally again after the `21:00` retry.

1. Open `https://ebedmenuk.hu/`
2. Confirm the selected/default day is **Hétfő**
3. Confirm the Monday tab shows **`Hétfő` + date**, and **does not** show `Ma · Hétfő` on Sunday
4. Confirm the visible weekday dates are the **coming Monday–Friday**, not the ending week
5. Open one restaurant detail page and confirm the same Monday-first behavior is present there too
6. If checking on real Monday, confirm the Monday tab now **does** show `Ma · Hétfő`

Quick fail signals:
- Sunday evening still shows the old week
- Sunday evening defaults to Friday or another stale day
- Sunday evening shows `Ma · Hétfő`
- homepage and restaurant detail page disagree about the selected/default day

## 6. Model routing notes

- Menu-checker / publication-sensitive jobs stay on the default oauth `gpt-5.4` path:
  - Sunday `17:00`
  - Sunday `21:00`
  - Monday `09:00`
  - Monday `11:00`
  - Tuesday `09:00`
  - Tuesday `11:00`
- Lower-risk recurring summary jobs are intentionally routed to `Flash` to reduce oauth quota burn:
  - daily random audit `09:30`
  - feedback watch `08:00, 10:00, 14:00, 16:00, 18:00, 20:00`
  - daily feedback digest `12:00`

## 7. Feedback monitor implementation note

- Script: `scripts/feedback_monitor.py`
- State file: `/root/.openclaw/workspace/memory/state/gyor-menu-feedback-monitor.json`
- Modes:
  - `watch` = only announce genuinely new rows
  - `daily` = noon digest for the last 24 hours

## 8. Current automation coverage summary

### Automated / structured
- several website / PDF / HTML sources are automated
- weekly rebuild cron windows are in place

### Semi-automated / OCR / image-based
- some restaurants still rely on image/OCR or manual review assistance
- future priority: reduce recurring screenshot dependency for Facebook/image-only sources

---

## 9. Recommended maintenance practice

When cron/automation changes are made:
1. update actual cron config
2. update this file
3. update TickTick task `Győr Menü – Cronok és automatikák`
4. if publish behavior changes, explicitly re-check the approval-before-push rule
