#!/usr/bin/env python3
"""Sync manual overrides from a Google Sheet into manual_overrides.json.

Expected columns in sheet tab `Overrides`:
active, slug, date, certainty, source_url, notes, label, text, price_huf

Each row represents one menu item. Rows are grouped by (slug, date).
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
OUT_DEFAULT = BASE / "data" / "manual_overrides.json"

TRUTHY = {"1", "true", "yes", "y", "x"}


def run_gog_get(sheet_id: str, range_a1: str) -> list[list[str]]:
    cmd = [
        "gog", "sheets", "get", sheet_id, range_a1,
        "--json", "--results-only", "--no-input"
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    return data if isinstance(data, list) else []


def normalize_row(headers: list[str], row: list[str]) -> dict[str, str]:
    padded = row + [""] * max(0, len(headers) - len(row))
    return {headers[i].strip(): (padded[i] or "").strip() for i in range(len(headers))}


def parse_price(value: str) -> int | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else None


def sync(sheet_id: str, out_path: Path, sheet_name: str = "Overrides") -> dict[str, Any]:
    values = run_gog_get(sheet_id, f"{sheet_name}!A:Z")
    if not values:
        result = {"sourceSheetId": sheet_id, "overrides": []}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    headers = [str(h).strip() for h in values[0]]
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for raw_row in values[1:]:
        row = normalize_row(headers, raw_row)
        active = row.get("active", "").strip().lower()
        if active and active not in TRUTHY:
            continue
        slug = row.get("slug", "")
        date = row.get("date", "")
        if not slug or not date:
            continue

        key = (slug, date)
        if key not in grouped:
            notes_raw = row.get("notes", "")
            notes = [n.strip() for n in notes_raw.split("|") if n.strip()] if notes_raw else []
            grouped[key] = {
                "slug": slug,
                "date": date,
                "certainty": row.get("certainty", "manual") or "manual",
                "sourceUrl": row.get("source_url", "") or None,
                "notes": notes,
                "items": [],
            }

        grouped[key]["items"].append({
            "label": row.get("label", "") or None,
            "text": row.get("text", "") or None,
            "priceHuf": parse_price(row.get("price_huf", "")),
            "priceText": f"{parse_price(row.get('price_huf', '')):,} Ft".replace(",", " ") if parse_price(row.get("price_huf", "")) else None,
        })

    result = {
        "sourceSheetId": sheet_id,
        "overrides": sorted(grouped.values(), key=lambda x: (x["date"], x["slug"])),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet-id", required=True)
    parser.add_argument("--sheet-name", default="Overrides")
    parser.add_argument("--out", default=str(OUT_DEFAULT))
    args = parser.parse_args()

    result = sync(args.sheet_id, Path(args.out), sheet_name=args.sheet_name)
    print(json.dumps({
        "sheetId": args.sheet_id,
        "overrideCount": len(result.get("overrides", [])),
        "out": str(Path(args.out))
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
