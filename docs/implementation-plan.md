# Győr Menü — implementation plan

## Product goal
Build a mobile-first webpage that helps people in Győr compare lunch menus quickly before lunch.

## Chosen technical direction
### Best option now
A **static site + generated JSON feed**.

Why:
- current sources are heterogeneous: Wolt, HTML, PDF, Facebook
- the main engineering problem is **collection + normalization**, not complex app state
- a static site is cheap to host, fast on mobile, and easy to automate
- this is a better MVP than starting with a heavy backend or native app

## Architecture
### 1) Source registry
A structured restaurant registry stores:
- name
- slug
- address
- area
- source type
- source URL
- map link
- automation status
- notes

### 2) Collector layer
One parser per source type:
- `wolt_current`
- `website_weekly_html`
- `website_weekly_pdf`
- later: `facebook_image_ocr`
- later: `manual_override`

### 3) Normalized feed
All sources are converted into one JSON shape:
- restaurant metadata
- date
- certainty level
- items
- source links
- warnings / notes

### 4) Static frontend
The frontend reads one `feed.json` file and renders:
- Today
- Tomorrow
- Week
- search
- source confidence badges
- source links and map links

## Automation model
### Near-term
- schedule feed build every weekday morning
- publish automatically if sources parse cleanly
- if a parser fails, keep last good content and flag the restaurant

### Required manual fallback
Especially for:
- Facebook-only sources
- image-only menu uploads
- broken PDFs
- restaurants that change format often

## Confidence policy
### Exact
Use when date is explicit in the source:
- Kristály
- Nádor

### Snapshot
Use when the source shows a live current menu without an explicit date:
- Sziget via Wolt

### Unsupported
Use when a source exists but is not reliably extractable yet:
- John Bull Pub

## Recommended next milestones
### Phase 1 — working public MVP
- 20–30 restaurants total
- clean mobile page
- exact / snapshot labels
- shareable links
- analytics

### Phase 2 — operator tooling
- manual override JSON or admin sheet
- source health checks
- alerts on failed parsers

### Phase 3 — restaurant participation
- submission form
- photo/PDF upload
- structured menu form

### Phase 4 — monetization experiments
- featured menus
- coupons
- promoted cafés
- paid highlighted listings

## Why this is the best path
This structure lets you:
- launch quickly
- learn which sources are stable
- avoid backend complexity too early
- expand from Győr to more cities later
- expand from lunch menus to café offers and coupons without renaming the architecture
