# How to use the Review Workspace (non-technical)

This is the easiest human editing layer for Győr Menü.

## Open this sheet
<https://docs.google.com/spreadsheets/d/1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms/edit?usp=drivesdk>

It has two main tabs:
- `Restaurants`
- `Review`

## What to use each tab for
### Restaurants
Use this when you want to:
- add a new restaurant
- disable a restaurant temporarily
- fix the source URL
- fix the address or area

### Review
Use this when you want to:
- manually add a menu
- correct a broken menu
- fill in a Facebook-only menu
- fix a wrong price or wrong item text

## How to add a new restaurant
Go to `Restaurants` and add a new row.
The most important fields are:
- `active` → TRUE
- `slug` → short unique id, for example `kisvendeglo-gyor`
- `name` → restaurant name
- `source_type` → how the menu is collected
- `source_url` → where the menu comes from

If you are unsure about source types, ask before changing them.

## How to fix or add a menu manually
Go to `Review`.
Each row = one visible menu item.

Example:
- row 1 = soup
- row 2 = menu A
- row 3 = menu B

Important fields:
- `active` → TRUE
- `slug` → which restaurant
- `date` → for example `2026-06-03`
- `certainty` → usually `manual`
- `source_url` → original Facebook post or source link
- `label` → for example `Leves`, `A`, `B`
- `text` → the actual dish
- `price_huf` → optional number like `2990`

## Simple rule
If the page looks wrong, you usually do **not** need to touch code.
You usually fix it in:
- `Restaurants` if the source/restaurant metadata is wrong
- `Review` if the menu content is wrong or missing

## What happens after editing
The sheet itself does not instantly update the webpage.
A sync + build step still has to run.

That step reads:
- `Restaurants`
- `Review`

and rebuilds the final menu feed.

## Good editing habits
- keep `slug` consistent
- use ISO dates like `2026-06-03`
- keep prices as plain numbers in HUF
- put one menu item per row
- if something should not be used, set `active` to FALSE instead of deleting immediately

## When to ask for help
Ask if:
- you are unsure what `source_type` should be
- an automated restaurant suddenly stops updating
- you want to add a new type of source
- the same restaurant has multiple menu formats
