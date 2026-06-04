# UI/UX update — 2026-06-01

## What changed
The MVP frontend was upgraded from a basic feed viewer into a more decision-friendly mobile experience.

## Improvements made
- Added clearer **Today / Tomorrow / Week** tab navigation
- Added **search + exact-only filter + sorting** in one clean control area
- Added **URL state syncing** for:
  - selected view
  - search query
  - exact-only filter
  - sorting mode
- Added **share current view** button so a filtered state can be shared directly
- Added **clear filters** button for faster reset on mobile
- Added **confidence legend** explaining exact vs snapshot vs unsupported
- Added **summary pills** showing how many restaurants are currently visible and what source quality is available
- Improved restaurant cards with:
  - area chips
  - source type chips
  - clearer menu block headers
  - better mobile spacing
- Kept unsupported restaurants visible separately, instead of mixing them into the main result set

## Why this matters
This makes the page more useful for the actual lunch decision moment:
- fast scanning
- confidence-aware comparison
- easier sharing
- better mobile interaction

## Recommended next UI iteration
1. add sticky bottom filter button on mobile
2. add area-based quick chips (Belváros, Nádorváros, Sziget, etc.)
3. add distance-based ranking later
4. add map/list toggle later
5. add favorite restaurants later
