# Győr Menü cron schedule

## Purpose
These cron jobs keep the menu feed refreshed around the times when restaurants usually publish new weekly menus.

## Time zone
All jobs use:
- `Europe/Budapest`

## Active schedule
### Weekly general refresh
- **Monday 09:00** — full workspace sync + feed build
- **Monday 11:00** — second Monday pass / retry

### Radó-specific refresh
- **Tuesday 09:00** — Radó-focused refresh
- **Tuesday 11:00** — second Tuesday pass / retry

## What each job does
Each cron job runs the same core workflow:
1. scan screenshot inbox folders
2. sync the Google Sheet review workspace
   - `Restaurants`
   - `Review`
3. rebuild `public/data/feed.json`
4. do a brief sanity check
5. send a short status summary back to Telegram

## Why this schedule was chosen
### Monday
Most restaurants publish their weekly menus on Monday morning.
The second Monday run helps catch places that publish later in the morning.

### Tuesday for Radó
Radó by Westy typically publishes its repeating Tuesday–Friday menu on Tuesday morning.
The second Tuesday run gives a fallback if the first publication is delayed.

## Current cron intent
This is a practical MVP schedule, not a high-frequency real-time sync.
The goal is:
- good enough freshness
- low operational overhead
- easy review when something breaks

## Related systems
These jobs work together with:
- Google Sheet review workspace
- screenshot inbox fallback flow
- feed builder pipeline

## Recommendation
If the publishing habits of restaurants change later, the cron windows should be adjusted rather than increasing frequency blindly.
