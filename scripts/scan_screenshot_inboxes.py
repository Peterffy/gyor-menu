#!/usr/bin/env python3
"""Scan Google Drive screenshot inbox folders and build a machine-readable manifest.

This does not OCR anything yet. It prepares a clean list of pending screenshot inputs
so they can later be processed automatically.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
CONFIG_DEFAULT = BASE / 'data' / 'screenshot_inbox_config.json'
OUT_DEFAULT = BASE / 'data' / 'screenshot_inbox_manifest.json'
IMAGE_MIME_PREFIXES = ('image/',)
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.gif')


def run_drive_ls(parent_id: str) -> list[dict[str, Any]]:
    cmd = [
        'gog', 'drive', 'ls',
        '--parent', parent_id,
        '--max', '200',
        '--json', '--results-only', '--no-input'
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and 'files' in data:
        return data['files']
    return []


def is_image(file: dict[str, Any]) -> bool:
    mime = (file.get('mimeType') or '').lower()
    name = (file.get('name') or '').lower()
    return mime.startswith(IMAGE_MIME_PREFIXES) or name.endswith(IMAGE_EXTS)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def scan(config_path: Path, out_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text())
    restaurants_out = []
    total_pending = 0

    for restaurant in config.get('restaurants', []):
        inbox_id = restaurant['inboxFolderId']
        files = run_drive_ls(inbox_id)
        image_files = [f for f in files if is_image(f)]
        pending = []
        for f in sorted(image_files, key=lambda x: x.get('name', '')):
            pending.append({
                'fileId': f.get('id'),
                'name': f.get('name'),
                'mimeType': f.get('mimeType'),
                'createdTime': f.get('createdTime'),
                'modifiedTime': f.get('modifiedTime'),
                'webViewLink': f.get('webViewLink'),
                'parentInboxFolderId': inbox_id,
            })
        total_pending += len(pending)
        restaurants_out.append({
            'slug': restaurant['slug'],
            'restaurantName': restaurant.get('restaurantName'),
            'inboxFolderId': inbox_id,
            'processedFolderId': restaurant.get('processedFolderId'),
            'archiveFolderId': restaurant.get('archiveFolderId'),
            'pendingCount': len(pending),
            'pendingFiles': pending,
        })

    manifest = {
        'generatedAt': now_iso(),
        'rootFolderId': config.get('rootFolderId'),
        'rootFolderName': config.get('rootFolderName'),
        'totalPending': total_pending,
        'restaurants': restaurants_out,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(CONFIG_DEFAULT))
    parser.add_argument('--out', default=str(OUT_DEFAULT))
    args = parser.parse_args()

    manifest = scan(Path(args.config), Path(args.out))
    print(json.dumps({
        'config': args.config,
        'out': args.out,
        'totalPending': manifest['totalPending'],
        'restaurantCount': len(manifest['restaurants'])
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
