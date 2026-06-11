# Screenshot inbox workflow

## Goal
Handle menu sources that are hard to scrape automatically, especially Facebook/image-only menus.

## Drive folder structure
Root folder:
- `Menu Screenshots`

Current restaurant folders:
- `john-bull-pub/`
  - `inbox/`
  - `processed/`
  - `archive/`
- `sziget-bisztro/`
  - `inbox/`
  - `processed/`
  - `archive/`

## What each folder means
### inbox
Drop new screenshots here.
This is the active input queue.

### processed
Images that were already read and converted into structured menu data.

### archive
Old or no-longer-relevant screenshots that should be kept but not actively processed.

## Naming rule
Use:
- `YYYY-MM-DD-description.jpg`

Examples:
- `2026-06-03-menu.jpg`
- `2026-06-03-1.jpg`
- `2026-06-03-facebook-post.jpg`

If there are multiple screenshots for one day:
- `2026-06-03-1.jpg`
- `2026-06-03-2.jpg`

## Recommended operational flow
1. Save the screenshot from Facebook or another non-structured source
2. Upload it into the restaurant’s `inbox/` folder
3. Run the inbox scan / ask me to process it
4. I read the screenshot and convert it into structured menu rows
5. If needed, adjust in the Review sheet
6. Rebuild the feed
7. Move the image to `processed/`

## Current Drive links
### Root
<https://drive.google.com/drive/folders/1vvEfxJdk-nbIiWmOuE1WGXApdidGMCyT>

### John Bull inbox
<https://drive.google.com/drive/folders/1z4yW70fpxQCGHV8wYWtL-ycS8wWV2Gla>

### Sziget Bisztró inbox
<https://drive.google.com/drive/folders/1no0asEGxWF5i24uA1FXWakVY_WNik0Fl>

## Recommendation
Use this for restaurants that do not yet have a reliable structured weekly source.
For Sziget and similar Wolt-hybrid restaurants, use **screenshot-first + Wolt-current-fallback**:
- if a fresh screenshot exists, prefer screenshot/manual structured rows
- if no fresh screenshot exists, Wolt may be used conservatively for the current day only
- do not extrapolate a current Wolt snapshot into a fake full-week menu

See also:
- `docs/wolt-hybrid-source-rule.md`
