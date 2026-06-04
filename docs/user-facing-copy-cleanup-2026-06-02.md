# User-facing copy cleanup — 2026-06-02

## Goal
Reduce technical language on the public-facing page while preserving the underlying reliability logic internally.

## Main copy changes
### Before
- Pontos dátum
- Aktuális snapshot
- Nem automatizált
- Snapshot / source-type-heavy phrasing

### After
- Ellenőrzött
- Élő forrás
- Forrás megnyitása

## UX intent
The page should feel like a lunch decision tool, not an internal data operations dashboard.

## Specific updates made
- Hero subtitle rewritten in simpler, more human language
- Search placeholder simplified
- `Csak pontos dátumú források` changed to `Csak ellenőrzött menük`
- Technical legend rewritten in user-facing terms
- Summary pills rewritten in simpler language
- Technical source type chip removed from restaurant cards
- Menu blocks now show `Frissítve: ...` instead of technical source labels
- Snapshot menus now get a human explanation: check the original source before going
- Unsupported restaurants now get a simple explanation rather than raw technical notes
- `Forrás` link renamed to `Eredeti forrás`

## Important product principle preserved
The internal reliability model still exists in code and data. Only the copy shown to users was cleaned up.
