# Győr Menü 🍽️

Mobile-first lunch menu aggregator for Győr.

See what's for lunch today at local restaurants — no fluff, no prices, just menus.

**Live:** `https://gyor-menu.vercel.app`

---

## Current restaurants (6)

| Restaurant | Source type |
|-----------|------------|
| Sziget Bisztró | Weekly screenshot (Facebook) |
| Kristály Étterem | Weekly HTML menu |
| Nádor Vendéglő | Weekly PDF menu |
| John Bull Pub | Screenshot inbox + manual review |
| Szalai Vendéglő | Weekly PDF menu |
| Radó by Westy | Manual / repeated snapshot |

See the [Review workspace](https://docs.google.com/spreadsheets/d/1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms/edit?usp=drivesdk) for full source tracking.

---

## Structure

```
data/                  — restaurant registry + config
docs/                  — operator documentation
public/                — static frontend (HTML/CSS/JS)
public/data/feed.json  — generated menu feed
scripts/               — build, sync, screenshot tools
```

## For operators

- [Google Sheet review workflow](docs/how-to-use-review-workspace-nontechnical.md)
- [Screenshot inbox workflow](docs/how-to-use-screenshot-inbox-nontechnical.md)

## For developers

Build the feed:

```bash
python3 scripts/run_build_pipeline.py \
  --workspace-sheet-id 1cT-KT1nKCrWW9z9Y7pzurpkPLEN2YyPL5VJj6vnTGms \
  --out public/data/feed.json
```

Scan screenshot inboxes:

```bash
python3 scripts/scan_screenshot_inboxes.py \
  --config data/screenshot_inbox_config.json \
  --out data/screenshot_inbox_manifest.json
```

---

Built with ❤️ by [Fórián Stúdió](https://forianstudio.com)