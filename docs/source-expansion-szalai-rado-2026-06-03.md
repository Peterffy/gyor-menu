# Source expansion — Szalai Vendéglő and Radó by Westy (2026-06-03)

## What was added
Two newly added restaurants from the `Restaurants` sheet were wired into the system:

### 1. Szalai Vendéglő
- slug: `szalai-vendeglo`
- source type: `website_weekly_pdf_listing`
- automation status: `exact`
- source: weekly PDF listing page on the restaurant website

Result:
- parsed successfully from the current week PDF
- shows exact day-based menus on the page

### 2. Radó by Westy
- slug: `rado-by-westy`
- source type: `website_menu_image_snapshot`
- automation status: `snapshot`
- source: menu image on the restaurant website weekly menu section

Result:
- no stable weekday-specific structured source found yet
- current image was extracted and added through the review/override layer as a live snapshot for the current day

## Technical change
`build_feed.py` was extended with a new source type:
- `website_weekly_pdf_listing`

This allows weekly PDFs to be discovered from a listing page rather than only hardcoded direct PDF URLs.

## Operational note
Radó by Westy currently works best as:
- website image snapshot
- optionally review-sheet assisted

Szalai Vendéglő is now properly automated as an exact weekly PDF source.
