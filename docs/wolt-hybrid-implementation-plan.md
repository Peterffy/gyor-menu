# Wolt-hybrid implementation plan

## Goal
Implement the documented operating rule for Wolt-hybrid restaurants in a way that is:
- operationally clear
- feed-safe
- explicit about certainty
- compatible with the existing screenshot inbox + Review Workspace flow

This plan is primarily about **behavioral consistency** between:
- registry metadata
- build logic
- quality review output
- daily audit output

---

## Problem being solved
Some restaurants (current main example: **Sziget Bisztró**) have a usable but noisy `wolt_current` fallback.

Current problem shape:
- Wolt current can often provide a **same-day menu** and prices
- but screenshot/manual entries are often **cleaner and more trustworthy**
- the system currently does not fully express the intended precedence model in code/ops language
- QA can misinterpret a restaurant running in valid same-day fallback mode as if it were simply broken or missing

---

## Desired target behavior

### For Wolt-hybrid restaurants
1. **If a fresh screenshot/manual path exists for the relevant period, use it first**
2. **If no fresh screenshot/manual path exists, allow Wolt current for today**
3. **Do not let Wolt current pretend to be a full weekly source**
4. **Make the source mode understandable in QA and operator workflows**

---

## Scope

### In scope
- `Sziget Bisztró`
- any future restaurant that ends up in a screenshot-first + Wolt-fallback pattern

### Out of scope for this phase
- auto-OCR of Wolt screenshots
- generalized image extraction redesign
- automatic screenshot freshness scoring from file contents
- auto-publishing any hybrid-source result

---

## Phase 1 — metadata / source-governance changes

### 1. Registry note update for hybrid restaurants
For Wolt-hybrid restaurants, update the registry notes to something like:

> `Screenshot-first source path; Wolt current fallback may be used for same-day coverage when no fresh screenshot is available.`

#### Why
This makes the intended source behavior visible in the source-of-truth layer, not just in docs.

#### Where
- `Restaurants` sheet
- synced into `data/restaurants.json`

---

### 2. Optional future registry distinction
If this pattern expands, introduce one of these later:
- a dedicated `source_type` like `wolt_hybrid`
- or a lightweight note/flag column such as `fallback_mode`

#### Recommendation
**Do not do this in phase 1 yet.**
Keep the schema stable unless multiple restaurants need the same behavior.

---

## Phase 2 — build/feed behavior clarification

### 3. Keep Wolt current as today-only by design
Current `collect_wolt_current()` behavior already only emits a menu for `ctx.today`.

#### Recommendation
Keep this behavior unchanged.

#### Why
This already matches the desired rule:
- Wolt current = same-day fallback
- not a weekly truth source

---

### 4. Preserve screenshot/manual rows when they exist for the same day
The current pipeline already applies manual overrides after collectors.
That means:
- collector generates Wolt current for today
- manual override can replace/override the same day if present

#### Recommendation
Treat this as the core precedence mechanism.
No architectural rewrite needed.

#### Meaning in practice
For a hybrid restaurant:
- if `Review` contains rows for today, those should win
- if not, Wolt current may stand for today

This is already aligned with the desired policy.

---

### 5. Improve Wolt row cleanup conservatively
Current Wolt output for Sziget can still be noisy:
- typo-like labels (`memü`, `nenü`)
- duplicated/fragmented items
- items with label but empty text

#### Recommended small improvement
Add a **light cleanup pass** inside or near `collect_wolt_current()` for Wolt hybrid restaurants only:
- normalize obvious label typos:
  - `memü` → `menü`
  - `nenü` → `menü`
- if an item has a label and price but no text, keep it only if it still looks like a meaningful standalone menu item
- otherwise drop or mark conservatively

#### Important constraint
Do **not** over-normalize into guessed structures.
This should remain a conservative cleanup, not semantic rewriting.

---

## Phase 3 — quality review behavior

### 6. `review_feed_quality.py` should distinguish fallback mode vs missing menu
Current review logic treats `wolt_current` restaurants with no usable menu as broadly unavailable.

#### Desired distinction
For Wolt-hybrid restaurants, QA should separate:
1. **acceptable same-day fallback available**
2. **no screenshot/manual input, but Wolt fallback exists**
3. **no screenshot/manual input and no usable Wolt fallback**
4. **Wolt fallback exists but is too noisy / suspicious**

#### Recommended implementation
Add Wolt-aware review wording such as:
- `Wolt same-day fallback aktív`
- `Wolt fallback elérhető, de review ajánlott`
- `nincs screenshot és nincs használható Wolt mai menü`

This is mostly a reporting change, not a structural data-model change.

---

### 7. Screenshot-needed logic should remain explicit
If a hybrid restaurant has no fresh screenshot and Wolt output is weak/noisy, the review output should still tell Peter/operator that screenshot help would improve quality.

#### Recommendation
For hybrid restaurants, prefer wording like:
- `screenshot hasznos lenne a tisztább heti forráshoz`

instead of treating the restaurant as purely broken.

---

## Phase 4 — daily audit behavior

### 8. Daily audit should recognize valid fallback mode
`daily_random_restaurant_audit.py` should not treat a hybrid restaurant as implicitly poor-quality just because:
- it is in `current_snapshot`
- it has only today’s menu

#### Recommended audit interpretation rule
If:
- source type is `wolt_current`
- today’s menu exists
- certainty is `current_snapshot`
- and content is readable enough

then this should be considered a **valid fallback state**, not a source failure.

---

### 9. Add a hybrid-source info note in the audit report later (optional)
Optional enhancement:
- report `üzemmód: screenshot-first / Wolt fallback`
for hybrid restaurants

#### Recommendation
Nice to have, not required for first implementation.

---

## Phase 5 — operational workflow

### 10. Screenshot inbox remains the main operator lever
No change to the fundamental operator workflow:
1. screenshot arrives
2. inbox scan sees it
3. manual/review conversion happens
4. build runs
5. same-day Wolt fallback is only used if no fresh screenshot/manual row exists

This keeps the system understandable and low-risk.

---

### 11. Cron implication
Current cron setup is already compatible:
- screenshot scanning already exists in the rebuild jobs
- daily random audit already exists at 09:30

#### Optional improvement later
Add a short Wolt-hybrid mention to the Monday/Tuesday quality summaries if a hybrid restaurant is running in fallback mode.

Example wording:
- `Sziget Bisztró ma Wolt-fallback módban fut; heti screenshot nem érkezett.`

---

## Recommended implementation order

### Step 1 — lightweight and high-value
- update hybrid restaurant notes in `Restaurants` sheet
- keep source semantics explicit

### Step 2 — review/reporting clarity
- refine `review_feed_quality.py` wording for Wolt-hybrid fallback interpretation

### Step 3 — conservative Wolt cleanup
- add minimal typo/fragment cleanup to `collect_wolt_current()`
- only where clearly safe

### Step 4 — optional audit/report enrichment
- add explicit hybrid-mode hint in the daily audit output

---

## Acceptance criteria
The implementation is good enough when all of these are true:

1. **Sziget never goes blank on a day when Wolt has a usable menu**
2. **A clean screenshot/manual row for the same day still wins over Wolt current**
3. **Wolt current is never represented as a fake full-week source**
4. **QA/reporting can distinguish valid fallback mode from actual missing data**
5. **Operators still know that screenshot/manual input is preferable when available**

---

## My recommendation
Do **not** redesign the source system for this.
The current architecture is already close to what we want.

The best next technical move is:
1. keep manual override precedence as the main control mechanism
2. improve Wolt wording and fallback interpretation in QA
3. add a small conservative cleanup layer for noisy Wolt labels/items

That gives better behavior without increasing system complexity too much.
