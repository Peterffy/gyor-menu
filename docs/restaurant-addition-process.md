# Győr Menü — Restaurant Addition Process

_Last updated: 2026-06-08_

## Goal
When Peter says: **"add this restaurant to Győr Menü"**, follow a consistent quality-first process that:
- finds the **best available source**
- chooses the **right ingestion path**
- builds the restaurant into the feed
- reviews the result against the current Győr Menü quality bar
- only then proposes it for preview / live publication

This is the default SOP for new restaurant onboarding.

---

## Quality principle
We are **not** trying to add restaurants at any cost.
We are trying to add them in a way that is:
- accurate
- understandable for users
- sustainable to update again next week
- honest about certainty

If a restaurant can only be added with weak or noisy data, that is acceptable **only if**:
- the certainty is labeled correctly
- the source path is documented
- the result is still readable and useful

If quality is below the current site standard, do **not** publish it live yet.

---

## Source preference order
Prefer sources in this order:

### 1. Official structured weekly source
Best cases:
- official restaurant website
- weekly HTML menu
- weekly PDF menu
- stable restaurant-owned menu page

Why:
- usually easiest to verify
- best repeatability
- best quality for users

### 2. Official semi-structured source
Examples:
- website image menu
- embedded weekly card/image on official site
- stable image-based menu page

Why:
- still first-party
- often usable with OCR/manual review fallback

### 3. Official social source
Examples:
- official Facebook page
- weekly Facebook post
- Facebook image album/post

Why:
- often the real source of truth for some restaurants
- harder operationally, but still better than third-party guessing

### 4. Reliable third-party fallback
Examples:
- Wolt current snapshot
- another restaurant platform page that clearly shows today's offer

Use only if:
- first-party source is absent or unusable
- the data is still understandable and useful
- the certainty is marked honestly (for example snapshot/current)

If the restaurant is a likely long-term Wolt fallback candidate, prefer the hybrid operating rule:
- screenshot/manual path when available
- Wolt current for same-day fallback only
- no fake extrapolation into a full week

See also:
- `docs/wolt-hybrid-source-rule.md`

### 5. Human screenshot/manual path
Use when:
- no reliable machine-readable source exists
- Facebook/image-only source is too brittle
- initial onboarding needs manual bridging before automation

---

## Acceptance bar for a new restaurant
A restaurant is good enough to add to Győr Menü when all of these are true:

### Required
- restaurant name is correct
- slug is stable and clean
- address / area are good enough for users
- source URL is stored
- menu date is correct
- menu text is readable
- certainty matches reality (`exact`, `manual`, `current_snapshot`, etc.)
- preview looks consistent with the rest of the site

### Strongly preferred
- source is restaurant-owned
- menu can be reproduced next week with the same workflow
- at least one reliable fallback path exists if automation fails
- menu labels are structured clearly (`Leves`, `A`, `B`, `C`, etc.)

### Not acceptable for live publication
- wrong date
- truncated / broken menu text
- obvious OCR garbage
- source ambiguity
- a source path that only works once and cannot be repeated
- menu visibility that is worse than the existing site norm

---

## Step-by-step onboarding process

## 1. Identify the restaurant and collect base metadata
Collect:
- official restaurant name
- website URL
- Facebook page URL (if relevant)
- address
- area/neighborhood in Győr
- map URL
- likely menu source URL

Create or confirm:
- proposed slug
- source type hypothesis
- automation status hypothesis

### Slug rule
Use a short, stable, lowercase slug with hyphens.
Example:
- `john-bull-pub`
- `kristaly-etterem`

---

## 2. Discover and rank all possible sources
Check, in order:
1. official website
2. official menu page
3. PDF links
4. embedded images
5. official Facebook page/posts
6. fallback third-party sources

For each candidate source, quickly score:
- **accuracy** — is this clearly the real menu?
- **repeatability** — can we use it again next week?
- **structure** — can it be parsed or cleanly transcribed?
- **freshness** — is it updated on time?
- **operational cost** — how painful will this be every week?

Choose:
- **primary source**
- **fallback source** (if available)

---

## 3. Choose the ingestion path
Pick one of these paths:

### Path A — Structured automated source
Use when source is:
- weekly HTML
- weekly PDF
- stable official page

Target result:
- restaurant can be built repeatedly from its source with minimal human touch

### Path B — Semi-structured / OCR-assisted source
Use when source is:
- image menu on website
- menu card image
- messy but recoverable page

Target result:
- automation if feasible
- manual cleanup allowed

### Path C — Screenshot inbox + manual review
Use when source is:
- Facebook image/post
- unstable source
- hard-to-scrape menu

Target result:
- reliable operator workflow first
- automation later if worth it

### Path D — Snapshot fallback
Use only when:
- no better source exists yet
- snapshot is still useful for users
- certainty is clearly lower than exact/manual weekly source

---

## 4. Register the restaurant in the Review Workspace
Primary human operating surface:
- **Győr Menü - Review Workspace**
- Sheet ID: `1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms`

Add a new row to the `Restaurants` tab with at least:
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

### Recommended rule during onboarding
While source quality is still being proven:
- keep the row operationally documented first
- if needed, keep it **inactive** until the first successful preview-quality build is ready

Then switch it to active when the preview result is acceptable.

---

## 5. Set up the source workflow
Depending on path:

### If structured/automated
- implement or reuse the collector/parsing path
- confirm the source can provide current week/day menu content

### If screenshot/manual
- create a screenshot inbox folder if needed
- document the folder in the inbox config/workflow
- use the screenshot workflow for weekly intake

Relevant docs:
- `docs/google-sheet-review-workflow.md`
- `docs/screenshot-inbox-workflow.md`
- `docs/manual-override-workflow.md`
- `docs/screenshot-processing-checklist.md`

---

## 6. Ingest a first real sample
Obtain actual menu data for a real day/week.

### Preferred approach
- use current week's real menu
- do not test with dummy content
- preserve original menu structure where useful

### If the source is weak
Use the `Review` tab to manually create clean menu rows.
Each row = one visible menu item.

Fields typically needed:
- `active`
- `slug`
- `date`
- `certainty`
- `source_url`
- `notes`
- `label`
- `text`
- `price_huf`

---

## 7. Build the feed
Standard build path:

```bash
cd /root/.openclaw/workspace/projects/gyor-menu
python3 scripts/run_build_pipeline.py \
  --workspace-sheet-id 1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms \
  --out public/data/feed.json
```

If screenshot workflow is involved, scan/update screenshot inputs as needed before or around the build.

---

## 8. Run quality review
Run automated quality review after the build:

```bash
python3 scripts/review_feed_quality.py \
  --feed public/data/feed.json \
  --registry data/restaurants.json \
  --manifest data/screenshot_inbox_manifest.json
```

Use the output to detect:
- suspicious OCR
- empty rows
- missing menus
- source-path issues

This is not enough by itself — human review is still required.

---

## 9. Manual preview review
Check the preview at:
- `http://89.167.67.46:8787`

Review the new restaurant on both:
- main list page
- restaurant detail page

### Main list review
Check:
- restaurant appears in expected position
- name is correct
- area is correct
- trust state is correct
- menu looks readable at a glance
- nothing obviously broken or noisy

### Detail page review
Check:
- day switching works if relevant
- source link works
- menu items are complete
- notes / certainty are appropriate
- no broken layout or odd truncation

### Content review questions
Ask:
- would a real Győr user trust this?
- would they understand what the restaurant offers today?
- is this at least as clean/useful as our existing good restaurants?
- if I compare it to Carmen / Kristály / Marcal-level entries, is it acceptable?

---

## 10. Decide the outcome
There are only 3 valid outcomes:

### A. Ready for preview sign-off
Use when:
- source path is clear
- menu quality is acceptable
- preview looks good

Then report to Peter with:
- restaurant added
- source type used
- certainty level
- any known caveats

### B. Keep in system, but not ready for live publication
Use when:
- restaurant can be built
- but quality is still below site bar
- or workflow is too fragile

Then:
- keep it as draft/inactive or preview-only
- document what still needs fixing

### C. Do not onboard yet
Use when:
- source is too weak
- menu cannot be verified reliably
- output is not good enough for users

Then:
- document the blocker
- choose a next-step path (for example screenshot inbox, source wait, parser later)

---

## 11. Publication rule
Even if the restaurant is ready:
- **preview first**
- **short changelog to Peter**
- **explicit approval required**
- only then:
  - commit
  - push
  - let Vercel publish live

Never skip this rule.

---

## 12. Default message format back to Peter
When asked to add a restaurant, the update back should usually say:

1. what source was found
2. what ingestion path was chosen
3. whether the first result is exact / manual / snapshot
4. whether it passed preview review
5. whether it is ready for approval-to-publish
6. if not ready, what is blocking quality

---

## Practical default behavior for Brenda
When Peter says:
> "Add restaurant X to Győr Menü"

Brenda should now default to this sequence:
1. source discovery
2. source ranking
3. ingestion-path choice
4. restaurant registry entry
5. first sample ingestion
6. build
7. automated review
8. manual preview review
9. short report to Peter
10. wait for approval before publishing live

That is the standard onboarding behavior from now on.
