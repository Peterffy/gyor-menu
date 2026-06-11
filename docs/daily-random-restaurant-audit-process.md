# Daily random restaurant audit process

## Purpose
Each day, select one restaurant automatically and audit the quality of:
- the restaurant information we show
- the menu we show for that day
- whether the same issue also exists elsewhere in the feed

This is designed as a lightweight daily QA loop for Győr Menü.

---

## What the daily audit checks

For the selected restaurant, the audit checks:

1. **Registry metadata completeness / quality**
   - address present
   - address not just a generic city-only placeholder
   - area present
   - source URL present

2. **Today-level menu presence**
   - does the restaurant have a menu for today?

3. **Menu text quality**
   - suspicious OCR noise
   - empty rows
   - obviously broken short fragments
   - special same-day closure / outage notice

4. **Menu completeness sanity**
   - unusually short menu compared to that restaurant's own typical item count
   - but do not double-report this if the menu is intentionally replaced by a same-day closure notice

5. **Source / trust consistency**
   - if the source is a structured weekly website/PDF source, is certainty still `exact`?

6. **Price completeness for structured sources**
   - no prices at all on a structured menu
   - only partial prices on a structured menu

---

## If an issue is found
The process must then scan all other restaurants for the **same issue code**.

Example:
- selected restaurant issue = `partial_prices_on_structured_menu`
- then the process checks the rest of the feed for the same issue
- report should say whether this is:
  - isolated
  - shared by several restaurants
  - systemic across many restaurants

This helps distinguish:
- one bad restaurant row
- one weak source family
- one product-wide QA problem

---

## Daily execution command

Run:

```bash
cd /root/.openclaw/workspace/projects/gyor-menu
python3 scripts/daily_random_restaurant_audit.py
```

The script:
- uses `public/data/feed.json`
- uses `data/restaurants.json`
- picks a **deterministic daily random** restaurant based on the date
- only selects from restaurants that currently have a menu for today when possible
- prints a ready-to-send text report

---

## Useful manual overrides

Audit a specific restaurant:

```bash
python3 scripts/daily_random_restaurant_audit.py --slug carmen-etterem
```

Force a seed for testing:

```bash
python3 scripts/daily_random_restaurant_audit.py --seed demo
```

---

## Recommended operator workflow

### Daily loop
1. Rebuild feed if needed.
2. Run the daily random audit script.
3. Read the report.
4. If the report shows a real issue:
   - inspect the selected restaurant on preview/live
   - inspect the source page if needed
   - decide whether this is:
     - restaurant-specific
     - source-family-specific
     - system-wide
5. If correction is needed:
   - fix in collector / Review sheet / content layer
   - rebuild
   - re-run the audit script on the same restaurant with `--slug`

---

## Suggested daily report format

The script already outputs this structure:
- selected restaurant
- source type
- today's certainty
- item count
- price count
- issue list
- cross-check of the same issue across the rest of the feed

This is suitable for a daily Telegram summary.

---

## Good use as a cron
Recommended after the regular build/review flow, not before.

Example logic:
1. normal build/update
2. automated feed review
3. random daily restaurant audit
4. short summary to Peter

This makes the audit a QA spotlight, not a replacement for the broader feed checks.

---

## Important limitation
This process is primarily a **feed-quality audit**, not a full human source-verification replacement.

It is best used to catch:
- broken rows
- suspicious text
- missing prices
- trust/certainty drift
- metadata gaps
- same-day closure / outage signals
- patterns that affect multiple restaurants

For high-risk cases, human source comparison is still recommended.
