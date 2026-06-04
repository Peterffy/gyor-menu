# Favorites and detail pages update — 2026-06-02

## What changed
This round moved the MVP closer to the chosen product direction: 
**"Mi van ma/holnap a kedvenc helyeimen?"**

## Main changes
### 1. Favorites-first UX
- Added a visible **Kedvenc helyeim** selector
- Restaurants can now be marked with checkboxes
- Favorites are stored in the browser via local storage
- Favorites are sorted to the front in recommended mode
- Added **Csak kedvenceim** filter

### 2. One-day-at-a-time focus
- Removed the week tab from the main public experience
- Main list now focuses on **Ma** and **Holnap** only

### 3. Cleaner list cards
Main list now stays closer to the intended lightweight decision view:
- restaurant name
- update time
- source link
- menu items
- price
- less extra metadata in the list itself

### 4. Separate restaurant pages
Added `restaurant.html` + `restaurant.js`.

Restaurant detail pages now hold the heavier information:
- address
- area
- source link
- map link
- detailed menu view
- per-day toggle (today/tomorrow)

This keeps the main list cleaner while still allowing deeper inspection.

### 5. Map moved off the main list
The map link is now part of the restaurant detail page instead of being emphasized on the main list.

## Why this matters
This is a better fit for the intended first user persona:
- office worker / local employee
- quick weekday lunch decision
- repeat checking of known places

## Recommended next steps
1. add more restaurants
2. improve favorite presets / areas
3. test whether people actually use favorites
4. later add restaurant confirmation states and restaurant-managed updates
