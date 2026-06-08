#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DAYS = ['Kedd', 'Szerda', 'Csütörtök', 'Péntek', 'Szombat']


def fetch_day_texts(url: str, screenshot_dir: str | None = None) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 2200})
        page.goto(url, wait_until='domcontentloaded', timeout=90000)
        title_before = page.title()
        body_before = page.locator('body').inner_text()
        verification_bypassed = False
        if 'Hitelesítés' in title_before or 'Security Check' in body_before or 'VERIFY' in body_before:
            page.locator('#verify').click(timeout=15000)
            page.wait_for_timeout(1200)
            page.locator('#okBtn').click(timeout=15000)
            page.wait_for_load_state('networkidle', timeout=30000)
            verification_bypassed = True
        popup_closed = False
        close = page.locator('#hustle-popup-id-9 .hustle-button-close')
        if close.count():
            try:
                close.click(timeout=10000)
                page.wait_for_timeout(800)
                popup_closed = True
            except Exception:
                pass

        per_day_text = {}
        for day in DAYS:
            try:
                page.get_by_role('link', name=day).click(timeout=10000)
                page.wait_for_timeout(800)
                text = page.locator('body').inner_text()
                per_day_text[day] = text
                if screenshot_dir:
                    Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(screenshot_dir) / f'marcal_{day}.png'), full_page=True)
            except Exception as e:
                per_day_text[day] = f'__ERROR__:{e}'

        title_after = page.title()
        browser.close()
    return {
        'url': url,
        'title_before': title_before,
        'title_after': title_after,
        'verification_bypassed': verification_bypassed,
        'popup_closed': popup_closed,
        'per_day_text': per_day_text,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='https://marcal-etterem.hu/heti-menu/')
    ap.add_argument('--screenshot-dir')
    args = ap.parse_args()
    print(json.dumps(fetch_day_texts(args.url, args.screenshot_dir), ensure_ascii=False))


if __name__ == '__main__':
    main()
