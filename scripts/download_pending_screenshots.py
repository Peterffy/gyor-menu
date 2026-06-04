#!/usr/bin/env python3
"""Download pending screenshot inbox files listed in the manifest.

This is a preparation tool for later OCR / processing. By default it downloads all
pending images into a local working directory grouped by restaurant slug.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MANIFEST_DEFAULT = BASE / 'data' / 'screenshot_inbox_manifest.json'
OUT_DIR_DEFAULT = BASE / 'tmp' / 'screenshot-inbox-downloads'


def download(file_id: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        'gog', 'drive', 'download', file_id,
        '--out', str(out_path),
        '--no-input'
    ], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', default=str(MANIFEST_DEFAULT))
    parser.add_argument('--out-dir', default=str(OUT_DIR_DEFAULT))
    parser.add_argument('--slug', help='Only download pending files for one restaurant slug')
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    out_dir = Path(args.out_dir)
    count = 0
    for restaurant in manifest.get('restaurants', []):
        slug = restaurant['slug']
        if args.slug and slug != args.slug:
            continue
        for file in restaurant.get('pendingFiles', []):
            out_path = out_dir / slug / file['name']
            download(file['fileId'], out_path)
            count += 1
    print(json.dumps({'downloaded': count, 'outDir': str(out_dir)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
