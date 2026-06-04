# Google Sheet-backed review workflow

## Goal
Make the project easier to operate without editing code or raw JSON files.

## Chosen setup
A single Google spreadsheet acts as the human control layer:

**Győr Menü - Review Workspace**
- Sheet ID: `1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms`
- URL: <https://docs.google.com/spreadsheets/d/1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms/edit?usp=drivesdk>

Tabs:
1. `Restaurants` — stable restaurant registry
2. `Review` — manual corrections / missing menus / Facebook-only entries

## What each tab is for
### Restaurants
Use this tab to manage which restaurants exist in the system and how they are sourced.

Columns:
- `active`
- `slug`
- `name`
- `address`
- `area`
- `source_type`
- `automation_status`
- `source_url`
- `map_url`
- `notes`

Typical use:
- add a new restaurant
- disable a restaurant temporarily
- fix source URL
- change the source type later

### Review
Use this tab when:
- a menu is missing
- a Facebook image needs manual entry
- an automated result needs correction
- a restaurant should appear even though parsing failed

Columns:
- `active`
- `slug`
- `date`
- `certainty`
- `source_url`
- `notes`
- `label`
- `text`
- `price_huf`

Each row = one menu item.
Rows are grouped by `(slug, date)` during sync.

## How the workflow works
1. Edit restaurants in `Restaurants`
2. Add or fix menu rows in `Review`
3. Run the pipeline
4. Pipeline syncs the sheet into local JSON
5. Feed is rebuilt
6. The webpage shows the updated data

## Commands
### Full workspace sync + build
```bash
cd /root/.openclaw/workspace/projects/gyor-menu
python3 scripts/run_build_pipeline.py \
  --workspace-sheet-id 1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms \
  --out public/data/feed.json
```

### Sync only the restaurant registry
```bash
python3 scripts/sync_restaurant_registry_sheet.py \
  --sheet-id 1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms \
  --sheet-name Restaurants \
  --out data/restaurants.json
```

### Sync only review overrides
```bash
python3 scripts/sync_sheet_overrides.py \
  --sheet-id 1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms \
  --sheet-name Review \
  --out data/manual_overrides.json
```

## Why this setup is good
- easy to inspect
- easy to correct
- non-technical friendly
- preserves automation where possible
- works well with Facebook/image-only edge cases

## Recommendation
Use this as the primary human-facing operating surface from now on.
The JSON files should be treated as synced machine-readable outputs, not your main editing surface.
