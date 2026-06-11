#!/usr/bin/env python3
"""Sync restaurant registry from a Google Sheet into restaurants.json.

Expected columns in tab `Restaurants`:
active, slug, name, address, area, source_type, automation_status, source_url, map_url, notes, lat, lng
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
OUT_DEFAULT = BASE / 'data' / 'restaurants.json'
TRUTHY = {'1', 'true', 'yes', 'y', 'x'}


def run_gog_get(sheet_id: str, range_a1: str) -> list[list[str]]:
    cmd = ['gog', 'sheets', 'get', sheet_id, range_a1, '--json', '--results-only', '--no-input']
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    return data if isinstance(data, list) else []


def normalize_row(headers: list[str], row: list[str]) -> dict[str, str]:
    padded = row + [''] * max(0, len(headers) - len(row))
    return {headers[i].strip(): (padded[i] or '').strip() for i in range(len(headers))}


def split_notes(value: str) -> list[str]:
    return [n.strip() for n in value.split('|') if n.strip()]


def parse_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(',', '.'))
    except ValueError:
        return None


def sync(sheet_id: str, out_path: Path, sheet_name: str = 'Restaurants', city: str = 'Győr') -> dict[str, Any]:
    values = run_gog_get(sheet_id, f'{sheet_name}!A:Z')
    if not values:
        result = {'city': city, 'sourceSheetId': sheet_id, 'restaurants': []}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    headers = [str(h).strip() for h in values[0]]
    restaurants = []
    for raw_row in values[1:]:
        row = normalize_row(headers, raw_row)
        active = row.get('active', '').strip().lower()
        if active and active not in TRUTHY:
            continue
        slug = row.get('slug', '')
        name = row.get('name', '')
        if not slug or not name:
            continue
        restaurants.append({
            'slug': slug,
            'name': name,
            'address': row.get('address', '') or None,
            'area': row.get('area', '') or None,
            'sourceType': row.get('source_type', ''),
            'automationStatus': row.get('automation_status', ''),
            'sourceUrl': row.get('source_url', '') or None,
            'mapUrl': row.get('map_url', '') or None,
            'notes': split_notes(row.get('notes', '')),
            'lat': parse_float(row.get('lat', '')),
            'lng': parse_float(row.get('lng', '')),
        })

    result = {'city': city, 'sourceSheetId': sheet_id, 'restaurants': restaurants}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sheet-id', required=True)
    parser.add_argument('--sheet-name', default='Restaurants')
    parser.add_argument('--city', default='Győr')
    parser.add_argument('--out', default=str(OUT_DEFAULT))
    args = parser.parse_args()

    result = sync(args.sheet_id, Path(args.out), sheet_name=args.sheet_name, city=args.city)
    print(json.dumps({
        'sheetId': args.sheet_id,
        'restaurantCount': len(result.get('restaurants', [])),
        'out': str(Path(args.out))
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
