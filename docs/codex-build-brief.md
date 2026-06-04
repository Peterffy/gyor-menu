# Codex build brief — Győr Menü

## Mission
Build a production-lean MVP for **Győr Menü**, a mobile-first lunch menu aggregator for Győr.

## Constraints
- Prefer a **static site + generated JSON feed** over a heavy full-stack app
- Source heterogeneity matters more than frontend complexity
- Source trustworthiness must be visible in UI
- Manual correction must remain possible

## Existing inputs
- project dummy in Google Doc
- working menu extraction experiments for:
  - Wolt / Sziget
  - Kristály HTML weekly menu
  - Nádor PDF weekly menu
- unstable / unresolved source:
  - John Bull Pub Facebook-only workflow

## Deliverables
### Required
1. Source registry
2. Python feed builder
3. Static mobile UI
4. Confidence labels
5. Search/filter basics
6. Documentation

### Nice to have
1. health-check report
2. per-source warnings
3. manual override ingestion
4. deploy script

## Data model
Use a feed model roughly like:
```json
{
  "generatedAt": "...",
  "city": "Győr",
  "restaurants": [
    {
      "slug": "kristaly-etterem",
      "name": "Kristály Étterem",
      "address": "...",
      "sourceType": "website_weekly_html",
      "automationStatus": "exact",
      "menus": [
        {
          "date": "2026-06-01",
          "dayNameHu": "Hétfő",
          "certainty": "exact",
          "items": [
            {"label": "Leves", "text": "..."},
            {"label": "A", "text": "..."}
          ],
          "sourceUrl": "...",
          "notes": []
        }
      ]
    }
  ]
}
```

## Frontend requirements
- mobile-first
- fast load
- Today / Tomorrow / Week views
- search by restaurant or menu text
- confidence badge
- source link
- map link
- note when a source is only a snapshot

## Backend recommendation
No backend required for V1 beyond the feed generator.

## Operational recommendation
- run feed build on schedule
- if exact source fails, preserve last good feed and flag warning
- don’t auto-publish OCR/Facebook output without a manual review path

## Most important engineering principle
Treat **source normalization and trust scoring** as first-class product features, not implementation details.
