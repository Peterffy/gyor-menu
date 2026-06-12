#!/usr/bin/env python3
"""Build pipeline for Győr Menü.

Supports:
- workspace sheet with `Restaurants` + `Review` tabs
- legacy review-only sheet
- pure local build with no sync
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace-sheet-id', help='Google Sheet ID with Restaurants + Review tabs')
    parser.add_argument('--sheet-id', help='Legacy/manual override sheet ID (review rows only)')
    parser.add_argument('--out', default=str(BASE / 'public' / 'data' / 'feed.json'))
    parser.add_argument('--today-override', help='Logical today date for build_feed.py as YYYY-MM-DD')
    args = parser.parse_args()

    if args.workspace_sheet_id:
        subprocess.run([
            'python3', str(BASE / 'scripts' / 'sync_restaurant_registry_sheet.py'),
            '--sheet-id', args.workspace_sheet_id,
            '--sheet-name', 'Restaurants',
            '--out', str(BASE / 'data' / 'restaurants.json')
        ], check=True)
        subprocess.run([
            'python3', str(BASE / 'scripts' / 'sync_sheet_overrides.py'),
            '--sheet-id', args.workspace_sheet_id,
            '--sheet-name', 'Review',
            '--out', str(BASE / 'data' / 'manual_overrides.json')
        ], check=True)
    elif args.sheet_id:
        subprocess.run([
            'python3', str(BASE / 'scripts' / 'sync_sheet_overrides.py'),
            '--sheet-id', args.sheet_id,
            '--out', str(BASE / 'data' / 'manual_overrides.json')
        ], check=True)

    build_cmd = [
        'python3', str(BASE / 'scripts' / 'build_feed.py'),
        '--out', args.out
    ]
    if args.today_override:
        build_cmd.extend(['--today-override', args.today_override])

    subprocess.run(build_cmd, check=True)


if __name__ == '__main__':
    main()
