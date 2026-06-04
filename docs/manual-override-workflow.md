# Manual override workflow

## Goal
Handle restaurants whose menus are not reliably machine-readable yet, especially:
- Facebook-only posts
- image-only menus
- temporary parser failures
- one-off corrections

## Chosen workflow
Use a **Google Sheet as the operator input surface**, then sync it into `manual_overrides.json`.

## Why this is the best option
Compared with editing JSON manually, a Sheet is:
- faster on mobile
- easier to share
- safer for non-technical editing
- easier to expand later into a restaurant submission flow

## Created sheet
**Győr Menü - Manual Overrides**
- Sheet ID: `1ePqHpVbQpj1PChjKKWw3XaqPRqs1u7JxZgy8oqVTHb4`
- Tab: `Overrides`

## Required columns
- `active`
- `slug`
- `date`
- `certainty`
- `source_url`
- `notes`
- `label`
- `text`
- `price_huf`

Each row = one visible menu item.
Rows are grouped by `(slug, date)` during sync.

## Example use case
John Bull Pub uploads a menu image to Facebook.
Operator reads the image and fills rows like:
- slug = `john-bull-pub`
- date = `2026-06-01`
- label = `Leves`
- text = `Paradicsomleves`
- price_huf = empty

Another row:
- slug = `john-bull-pub`
- date = `2026-06-01`
- label = `A`
- text = `Rántott sajt hasábburgonyával`
- price_huf = `2990`

## Sync command
```bash
cd /root/.openclaw/workspace/projects/gyor-menu
python3 scripts/sync_sheet_overrides.py \
  --sheet-id 1ePqHpVbQpj1PChjKKWw3XaqPRqs1u7JxZgy8oqVTHb4 \
  --out data/manual_overrides.json
```

## Full pipeline command
```bash
cd /root/.openclaw/workspace/projects/gyor-menu
python3 scripts/run_build_pipeline.py \
  --sheet-id 1ePqHpVbQpj1PChjKKWw3XaqPRqs1u7JxZgy8oqVTHb4 \
  --out public/data/feed.json
```

## Recommendation
This should be the default fallback path for hard sources until OCR or direct submission forms become good enough.
