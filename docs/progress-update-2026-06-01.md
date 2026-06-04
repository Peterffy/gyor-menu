# Progress update — 2026-06-01 / 2026-06-02

## What is already done
- Read and distilled the project dummy
- Chose a concrete MVP architecture: **static site + generated JSON feed**
- Created a restaurant source registry with metadata
- Built a normalized feed generator for:
  - Sziget Bisztró (Wolt snapshot)
  - Kristály Étterem (weekly HTML parser)
  - Nádor Vendéglő (weekly PDF parser)
- Built a **Google Sheet based manual override workflow**
- Extended that into a broader **Google Sheet-backed review workspace** with:
  - `Restaurants` tab
  - `Review` tab
- Connected the workspace to feed generation
- Created a mobile-friendly static MVP webpage with:
  - Today / Tomorrow views
  - Search
  - Exact-only filter
  - Favorites-first UX
  - Sorting
  - Shareable view state
  - Restaurant detail pages
  - Source and map links
  - Cleaner user-facing copy
- Generated a working sample `feed.json`
- Put up a working cloud preview

## What this means now
This is no longer just a technical prototype. It is now a workable operating model for:
- exact sources
- snapshot sources
- manual fallback sources
- non-technical review/editing via Google Sheets

## Biggest remaining blocker
- full automation of Facebook-only menus without manual review is still fragile
- OCR can be added later, but it should not replace the review workspace yet

## Next highest-value steps
1. Add 10–20 more restaurants into the registry sheet
2. Add analytics
3. Add scheduled pipeline runs
4. Add lightweight source health checks
5. Decide when to move from temporary preview to stable deployment

## Recommendation
Launch testing with a mix of:
- exact sources
- current snapshots
- review-sheet corrections

That is already good enough to test the behavior milestone: do people in Győr actually open this before lunch?
