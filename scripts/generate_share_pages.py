#!/usr/bin/env python3
"""Generate share-stable static restaurant pages with correct OG metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE / "public"
TEMPLATE_PATH = PUBLIC_DIR / "restaurant.html"
FEED_PATH = PUBLIC_DIR / "data" / "feed.json"

WEEKDAYS_HU = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap"]
STYLE_VERSION = "20260612logo8"
SCRIPT_VERSION = "20260612share1"
OG_IMAGE = "https://ebedmenuk.hu/assets/brand/logo.png?v=20260611logov2"


def build_detail_path(slug: str, day_index: int | None = None) -> str:
    if day_index is None:
        return f"/restaurant/{slug}/"
    return f"/restaurant/{slug}/day/{day_index}/"


def description_for(restaurant: dict[str, Any], day_index: int | None = None) -> str:
    name = restaurant.get("name", "Győri étterem")
    address = restaurant.get("address")
    if day_index is None:
        return f"{name} napi és heti menüje Győrben{f' – {address}' if address else ''}. Eredeti forrás, térkép és részletes menük a Mi a menü? oldalon."
    day_name = WEEKDAYS_HU[day_index]
    return f"{name} menüje Győrben erre a napra: {day_name}{f' – {address}' if address else ''}. Eredeti forrás, térkép és részletes menük a Mi a menü? oldalon."


def title_for(restaurant: dict[str, Any], day_index: int | None = None) -> str:
    name = restaurant.get("name", "Győri étterem")
    if day_index is None:
        return f"{name} napi menü Győr | Mi a menü?"
    return f"{name} – {WEEKDAYS_HU[day_index]} menü Győr | Mi a menü?"


def inject_bootstrap(text: str, slug: str, day_index: int | None) -> str:
    payload = {"slug": slug}
    if day_index is not None:
        payload["dayIndex"] = day_index
    bootstrap = f"  <script>window.__GYOR_MENU_SHARE_STATE__ = {json.dumps(payload, ensure_ascii=False)};</script>\n"
    needle = '  <script src="./vendor/leaflet/leaflet.js" defer></script>\n'
    if needle not in text:
        raise ValueError("Could not find script injection point in restaurant template")
    return text.replace(needle, bootstrap + '  <script src="/vendor/leaflet/leaflet.js" defer></script>\n', 1)


def absolutize_assets(text: str) -> str:
    replacements = {
        'href="./index.html"': 'href="/index.html"',
        'href="./adatkezeles.html"': 'href="/adatkezeles.html"',
        'src="./assets/brand/logo.png"': 'src="/assets/brand/logo.png"',
        'href="./vendor/leaflet/leaflet.css"': 'href="/vendor/leaflet/leaflet.css"',
        f'href="./styles.css?v={STYLE_VERSION}"': f'href="/styles.css?v={STYLE_VERSION}"',
        f'  <script src="./restaurant.js?v={SCRIPT_VERSION}" defer></script>\n': f'  <script src="/restaurant.js?v={SCRIPT_VERSION}" defer></script>\n',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def apply_meta(text: str, restaurant: dict[str, Any], day_index: int | None = None) -> str:
    path = build_detail_path(restaurant["slug"], day_index)
    full_url = f"https://ebedmenuk.hu{path}"
    title = title_for(restaurant, day_index)
    description = description_for(restaurant, day_index)

    replacements = {
        '<title>Győri étterem napi menüje | Mi a menü?</title>': f'<title>{title}</title>',
        '<link id="canonical-link" rel="canonical" href="https://ebedmenuk.hu/restaurant.html">': f'<link id="canonical-link" rel="canonical" href="{full_url}">',
        '<meta id="meta-og-title" property="og:title" content="Győri étterem napi menüje | Mi a menü?">': f'<meta id="meta-og-title" property="og:title" content="{title}">',
        '<meta id="meta-og-description" property="og:description" content="Győri étterem részletes napi és heti menüoldala, forráslinkkel és gyors áttekintéssel.">': f'<meta id="meta-og-description" property="og:description" content="{description}">',
        '<meta id="meta-og-url" property="og:url" content="https://ebedmenuk.hu/restaurant.html">': f'<meta id="meta-og-url" property="og:url" content="{full_url}">',
        f'<meta property="og:image" content="{OG_IMAGE}">': f'<meta property="og:image" content="{OG_IMAGE}">',
        '<meta id="meta-description" name="description" content="Győri étterem részletes napi és heti menüoldala, forráslinkkel és gyors áttekintéssel.">': f'<meta id="meta-description" name="description" content="{description}">',
        '<meta id="meta-twitter-title" name="twitter:title" content="Győri étterem napi menüje | Mi a menü?">': f'<meta id="meta-twitter-title" name="twitter:title" content="{title}">',
        '<meta id="meta-twitter-description" name="twitter:description" content="Győri étterem részletes napi és heti menüoldala, forráslinkkel és gyors áttekintéssel.">': f'<meta id="meta-twitter-description" name="twitter:description" content="{description}">',
    }
    for old, new in replacements.items():
        if old not in text:
            raise ValueError(f"Could not find expected template fragment: {old}")
        text = text.replace(old, new, 1)
    return text


def render_page(template: str, restaurant: dict[str, Any], day_index: int | None = None) -> str:
    page = apply_meta(template, restaurant, day_index)
    page = absolutize_assets(page)
    page = inject_bootstrap(page, restaurant["slug"], day_index)
    return page


def generate_share_pages(feed: dict[str, Any]) -> None:
    template = TEMPLATE_PATH.read_text()
    for restaurant in feed.get("restaurants", []):
        slug = restaurant.get("slug")
        if not slug:
            continue

        base_dir = PUBLIC_DIR / "restaurant" / slug
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "index.html").write_text(render_page(template, restaurant, None))

        for day_index in range(7):
            day_dir = base_dir / "day" / str(day_index)
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / "index.html").write_text(render_page(template, restaurant, day_index))



def main() -> None:
    feed = json.loads(FEED_PATH.read_text())
    generate_share_pages(feed)
    print(f"Generated share pages from {FEED_PATH}")


if __name__ == "__main__":
    main()
