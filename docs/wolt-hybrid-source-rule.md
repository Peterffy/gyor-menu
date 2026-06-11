# Wolt-hybrid source rule

## Purpose
Define how Győr Menü should operate restaurants whose best practical fallback source is a live Wolt menu, but where screenshot/manual intake may still produce cleaner daily or weekly menu data.

This is a **source precedence rule**, not an automatic publish rule.

---

## Scope
Use this rule for:
- restaurants already using `wolt_current`
- restaurants that may later become screenshot-first + Wolt-fallback hybrids

Current example:
- `Sziget Bisztró`

---

## Core rule

### Primary rule
**Screenshot/manual source wins over Wolt current snapshot when both are available and usable.**

Why:
- screenshots often preserve cleaner daily/weekly structure
- Wolt current menus are useful, but often noisy or incomplete
- Wolt current is usually strongest as a **same-day fallback**, not as a weekly truth source

---

## Source precedence

### 1. Screenshot/manual entry = preferred source
Use screenshot/manual rows first when:
- there is a fresh screenshot for the relevant day or week
- the screenshot content is readable enough to structure cleanly
- the result is more trustworthy/clear than the Wolt live category text

Typical output:
- `certainty = manual`
- `sourceLabel = Screenshot / manual`

This is especially suitable when:
- the screenshot shows a full week
- the screenshot text is clearer than Wolt
- labels like `Leves`, `Napi menü`, `Heti extra`, `Vega` are easier to preserve from the screenshot

### 2. Wolt current snapshot = same-day fallback
Use Wolt current snapshot when:
- no fresh screenshot is available
- or screenshot/manual data is stale
- and Wolt currently shows a usable menu for **today**

Typical output:
- `certainty = current_snapshot`
- `sourceLabel = Wolt current snapshot`

Important:
- treat Wolt current as **today-only reliable** unless the source explicitly shows a dated future menu
- do **not** pretend a current Wolt snapshot is a full-week source

### 3. If both exist on the same day
If screenshot/manual and Wolt current are both available for the same day:
- screenshot/manual remains the primary content source
- Wolt may still be used as a **sanity check** for:
  - prices
  - whether the venue is open today
  - whether a daily menu currently exists

But Wolt should not override a cleaner screenshot/manual structure unless the screenshot is clearly stale or wrong.

---

## What not to do

### Do not extrapolate a Wolt current menu into a fake week
Not allowed:
- taking one current Wolt menu and cloning/implying it across the rest of the week
- representing a current Wolt snapshot as an exact future-day menu

### Do not override a clean screenshot with a noisier Wolt parse
If screenshot/manual is cleaner and clearly current enough, keep it.

### Do not hide uncertainty
If the system is using Wolt current because screenshot/manual is missing, the data should remain clearly marked as `current_snapshot`.

---

## Daily operational rule

### For each Wolt-hybrid restaurant
1. Check whether a fresh screenshot exists in the screenshot inbox.
2. If yes:
   - process screenshot/manual rows
   - use those rows as the main source
3. If no screenshot exists:
   - allow Wolt current snapshot for today if the content is readable enough
4. If Wolt content is too noisy to trust:
   - keep it out of the feed or keep only very conservative output
   - note that screenshot/manual input is needed

---

## Quality bar for Wolt fallback
Wolt current is acceptable as fallback when:
- menu options are understandable
- prices are understandable
- labels are not excessively broken
- the output still helps a real user decide where to eat today

Wolt current is **not** good enough as fallback when:
- text is badly fragmented
- menu options are ambiguous
- prices are attached to the wrong items in a misleading way
- the result would reduce trust more than help coverage

---

## Audit interpretation rule
If a Wolt-backed restaurant has no screenshot/manual input for the week but still has a current Wolt menu today:
- that is **not automatically a source failure**
- it may simply mean the restaurant is currently operating in fallback mode

Audit/reporting should distinguish between:
- acceptable Wolt fallback mode
- missing menu entirely
- noisy / low-quality Wolt fallback needing manual screenshot help

---

## Sziget-specific interpretation
For `Sziget Bisztró`:
- screenshot/manual weekly input is usually cleaner than Wolt
- Wolt current remains useful to avoid a blank current day
- therefore the intended operating mode is:
  - **screenshot-first**
  - **Wolt current fallback for the current day**

---

## Registry / source notes recommendation
For hybrid restaurants, the registry notes should make the mode obvious.

Recommended wording pattern:
- `Screenshot-first source path; Wolt current fallback may be used for same-day coverage when no fresh screenshot is available.`

---

## Cron / workflow implication
This rule does **not** require automatic live publishing.

It does imply:
- screenshot inboxes remain important for hybrid restaurants
- daily checks should notice when a restaurant has fallen back to Wolt current mode
- quality review should be aware that Wolt fallback can be acceptable for the same day

---

## Short policy summary
If there is a good screenshot, use it.
If there is no screenshot, Wolt can cover **today**.
Do not treat Wolt current as a full-week truth source.
Keep certainty honest.
