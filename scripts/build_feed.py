#!/usr/bin/env python3
"""Build a normalized Győr Menü JSON feed.

Outputs a static JSON file the mobile site can read directly.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
PUBLIC_DIR = BASE / "public"
RESTAURANTS_PATH = DATA_DIR / "restaurants.json"
OVERRIDES_PATH = DATA_DIR / "manual_overrides.json"

WEEKDAYS_HU = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap"]
WEEKDAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

KRISTALY_URL = "https://www.kristalyetterem.hu/"
WOLT_TEMPLATE = "https://wolt.com/hu/hun/{city}/restaurant/{slug}"
NADOR_PDF_BASE = "https://www.nadorvendeglo.hu/heti_menu/heti_menu_nador_{monday}.pdf"

HEADERS = {"User-Agent": "Mozilla/5.0"}


@dataclass
class CollectContext:
    today: date
    tomorrow: date
    monday: date


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def maybe_load_overrides() -> list[dict[str, Any]]:
    if OVERRIDES_PATH.exists():
        return load_json(OVERRIDES_PATH).get("overrides", [])
    return []


def iso(d: date) -> str:
    return d.isoformat()


def hu_day(d: date) -> str:
    return WEEKDAYS_HU[d.weekday()]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_price_huf(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return None
    return int(digits)


def is_closure_text(text: str | None) -> bool:
    if not text:
        return False
    normalized = text.strip().upper()
    return normalized in {"ZÁRVA", "ZARVA", "CLOSED"}


def map_dates_for_current_week(ctx: CollectContext) -> dict[str, str]:
    return {WEEKDAYS_HU[i]: iso(ctx.monday + timedelta(days=i)) for i in range(7)}


def build_base_restaurant(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": meta["slug"],
        "name": meta["name"],
        "address": meta.get("address"),
        "area": meta.get("area"),
        "sourceType": meta.get("sourceType"),
        "automationStatus": meta.get("automationStatus"),
        "sourceUrl": meta.get("sourceUrl"),
        "mapUrl": meta.get("mapUrl"),
        "notes": meta.get("notes", []),
        "menus": [],
    }


# ---------- Wolt / Sziget ----------
def collect_wolt_current(meta: dict[str, Any], ctx: CollectContext) -> list[dict[str, Any]]:
    slug = meta["slug"]
    url = WOLT_TEMPLATE.format(city="gyor", slug=slug)
    html = requests.get(url, headers=HEADERS, timeout=30).text
    m = re.search(r'<script type="application/json" class="query-state">(.+?)</script>', html, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))

    categories = None
    items = None
    for q in data.get("queries", []):
        state_data = q.get("state", {}).get("data")
        if isinstance(state_data, dict) and "categories" in state_data and "items" in state_data:
            categories = state_data["categories"]
            items = state_data["items"]
            break
    if not categories or not items:
        return []

    item_map = {it["id"]: it for it in items}
    menu_cat = None
    for cat in categories:
        if cat["name"].strip().lower() == "menü":
            menu_cat = cat
            break
    if not menu_cat:
        return []

    entries = []
    for iid in menu_cat.get("item_ids", []):
        item = item_map.get(iid)
        if not item:
            continue
        desc = (item.get("description") or "").replace("\n", ", ").strip()
        price_huf = int(item.get("price", 0) / 100) if item.get("price") else None
        entries.append({
            "label": item.get("name"),
            "text": desc or None,
            "priceHuf": price_huf,
            "priceText": f"{price_huf:,} Ft".replace(",", " ") if price_huf else None,
        })

    if not entries:
        return []

    return [{
        "date": iso(ctx.today),
        "dayNameHu": hu_day(ctx.today),
        "certainty": "current_snapshot",
        "sourceLabel": "Wolt current snapshot",
        "sourceUrl": meta.get("sourceUrl"),
        "updatedAt": now_iso(),
        "items": entries,
        "notes": [
            "This source usually shows a live current menu without an explicit date.",
            "Safe for current-day browsing; not reliable as an exact future-day menu."
        ],
    }]


# ---------- Kristály ----------
def collect_kristaly_week(meta: dict[str, Any], ctx: CollectContext) -> list[dict[str, Any]]:
    html = requests.get(KRISTALY_URL, headers=HEADERS, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    section = soup.find("section", id="heti-menu")
    if not section:
        return []

    date_map = map_dates_for_current_week(ctx)
    menus = []
    for row in section.select(".table .day-row"):
        day_el = row.select_one(".day")
        if not day_el:
            continue
        day_name = day_el.get_text(strip=True)
        if day_name not in date_map:
            continue

        items = []
        for m in row.find_all("div", class_="menu"):
            label_el = m.select_one("span")
            label = label_el.get_text(strip=True) if label_el else ""
            full_text = m.get_text("\n", strip=True)
            content = full_text.replace(label, "", 1).strip()
            quoted_letter = label.startswith('"') and label.endswith('"') and len(label) == 3
            if not content and (len(label) <= 2 or quoted_letter):
                continue
            items.append({
                "label": label or None,
                "text": content or None,
                "priceHuf": None,
                "priceText": None,
            })

        if items:
            menus.append({
                "date": date_map[day_name],
                "dayNameHu": day_name,
                "certainty": "exact",
                "sourceLabel": "Weekly website menu",
                "sourceUrl": meta.get("sourceUrl"),
                "updatedAt": now_iso(),
                "items": items,
                "notes": [],
            })
    return menus


# ---------- Nádor ----------
def current_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def fetch_nador_pdf(ctx: CollectContext) -> bytes | None:
    monday = current_monday(ctx.today).strftime("%Y%m%d")
    url = NADOR_PDF_BASE.format(monday=monday)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    return resp.content if resp.status_code == 200 else None


def fetch_weekly_pdf_from_listing(meta: dict[str, Any], ctx: CollectContext) -> bytes | None:
    listing_url = meta.get("sourceUrl")
    if not listing_url:
        return None
    html = requests.get(listing_url, headers=HEADERS, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    monday_token = ctx.monday.strftime("%Y%m%d")

    chosen = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith('.pdf') and monday_token in href:
            chosen = urljoin(listing_url, href)
            break
    if not chosen:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith('.pdf'):
                chosen = urljoin(listing_url, href)
    if not chosen:
        return None
    resp = requests.get(chosen, headers=HEADERS, timeout=30)
    return resp.content if resp.status_code == 200 else None


def parse_fourcol_pdf_week(pdf_bytes: bytes, meta: dict[str, Any], ctx: CollectContext) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "menu.pdf"
        xml_path = Path(tmp) / "menu.xml"
        pdf_path.write_bytes(pdf_bytes)
        subprocess.run([
            "pdftohtml", "-xml", "-i", "-nodrm", str(pdf_path), str(xml_path)
        ], check=False, capture_output=True, timeout=30)
        tree = ElementTree.parse(str(xml_path))

    page = tree.getroot().find("page")
    if page is None:
        return []

    texts: list[tuple[int, int, str]] = []
    for el in page.findall("text"):
        top = int(el.get("top", 0))
        left = int(el.get("left", 0))
        content = "".join(el.itertext()).strip()
        if content:
            texts.append((top, left, content))
    texts.sort(key=lambda x: (x[0], x[1]))

    day_positions: dict[str, int] = {}
    for top, left, content in texts:
        if left > 150:
            continue
        upper = content.upper().strip()
        for en, hu in zip(WEEKDAYS_EN, WEEKDAYS_HU):
            if upper == hu.upper():
                day_positions[en] = top
                break

    if not day_positions:
        return []

    sorted_days = sorted(day_positions.items(), key=lambda x: x[1])
    boundaries = []
    for i, (day_en, top_pos) in enumerate(sorted_days):
        start = (sorted_days[i - 1][1] + top_pos) // 2 if i > 0 else 0
        end = (top_pos + sorted_days[i + 1][1]) // 2 if i + 1 < len(sorted_days) else 9999
        boundaries.append((day_en, start, end, top_pos))

    date_map = {WEEKDAYS_EN[i]: iso(ctx.monday + timedelta(days=i)) for i in range(7)}
    menus = []
    labels = ["A menü", "B menü", "C menü", "D menü"]

    def col_group(x: int) -> int:
        if x < 350:
            return 0
        if x < 600:
            return 1
        if x < 850:
            return 2
        return 3

    for day_en, start, end, label_top in boundaries:
        if day_en == "monday":
            # Monday in the current PDF format often just means closed.
            continue
        bucket = [(left, content) for top, left, content in texts if start <= top < end and top != label_top]
        cols: dict[int, list[str]] = {0: [], 1: [], 2: [], 3: []}
        for left, content in bucket:
            cols[col_group(left)].append(content)

        items = []
        for idx in range(4):
            col = cols.get(idx, [])
            if not col:
                continue
            soup = col[0] if len(col) > 0 else None
            main = col[1] if len(col) > 1 else None
            price_text = col[2] if len(col) > 2 else None
            items.append({
                "label": labels[idx],
                "text": " — ".join([p for p in [soup, main] if p]) or None,
                "priceHuf": parse_price_huf(price_text),
                "priceText": price_text,
            })
        if items:
            # Ignore explicit closure-only days.
            if all(is_closure_text(item.get("text")) for item in items):
                continue
            # Szalai should behave like a weekday lunch-menu source in the current product.
            if meta.get("slug") == "szalai-vendeglo" and day_en in {"saturday", "sunday"}:
                continue
            menus.append({
                "date": date_map[day_en],
                "dayNameHu": WEEKDAYS_HU[WEEKDAYS_EN.index(day_en)],
                "certainty": "exact",
                "sourceLabel": "Weekly PDF menu",
                "sourceUrl": meta.get("sourceUrl"),
                "updatedAt": now_iso(),
                "items": items,
                "notes": [],
            })
    return menus


# ---------- Overrides ----------
def apply_overrides(restaurants: list[dict[str, Any]], overrides: list[dict[str, Any]]) -> None:
    by_slug = {r["slug"]: r for r in restaurants}
    for override in overrides:
        slug = override.get("slug")
        if slug not in by_slug:
            continue
        target = by_slug[slug]
        menus = target.setdefault("menus", [])
        menus = [m for m in menus if m.get("date") != override.get("date")]
        menus.append({
            "date": override["date"],
            "dayNameHu": WEEKDAYS_HU[date.fromisoformat(override["date"]).weekday()],
            "certainty": override.get("certainty", "manual"),
            "sourceLabel": "Manual override",
            "sourceUrl": override.get("sourceUrl"),
            "updatedAt": now_iso(),
            "items": override.get("items", []),
            "notes": override.get("notes", []),
        })
        target["menus"] = sorted(menus, key=lambda m: m["date"])


def build_feed() -> dict[str, Any]:
    registry = load_json(RESTAURANTS_PATH)
    overrides = maybe_load_overrides()
    today = date.today()
    ctx = CollectContext(today=today, tomorrow=today + timedelta(days=1), monday=current_monday(today))

    restaurants_out = []
    for meta in registry.get("restaurants", []):
        base = build_base_restaurant(meta)
        source_type = meta.get("sourceType")
        try:
            if source_type == "wolt_current":
                base["menus"] = collect_wolt_current(meta, ctx)
            elif source_type == "website_weekly_html":
                base["menus"] = collect_kristaly_week(meta, ctx)
            elif source_type == "website_weekly_pdf":
                pdf = fetch_nador_pdf(ctx)
                base["menus"] = parse_fourcol_pdf_week(pdf, meta, ctx) if pdf else []
            elif source_type == "website_weekly_pdf_listing":
                pdf = fetch_weekly_pdf_from_listing(meta, ctx)
                base["menus"] = parse_fourcol_pdf_week(pdf, meta, ctx) if pdf else []
            elif source_type in {"facebook_unstructured", "manual_review_only", "website_menu_image_snapshot"}:
                base["notes"] = base.get("notes", []) + [
                    "This source currently relies on manual review, image-based extraction, or fallback input."
                ]
            else:
                base["notes"] = base.get("notes", []) + [f"Unsupported source type: {source_type}"]
        except Exception as exc:  # noqa: BLE001
            base["notes"] = base.get("notes", []) + [f"Collector error: {exc}"]
        restaurants_out.append(base)

    apply_overrides(restaurants_out, overrides)

    feed = {
        "generatedAt": now_iso(),
        "city": registry.get("city", "Győr"),
        "today": iso(ctx.today),
        "tomorrow": iso(ctx.tomorrow),
        "weekStart": iso(ctx.monday),
        "restaurants": sorted(restaurants_out, key=lambda r: r["name"]),
    }
    return feed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PUBLIC_DIR / "data" / "feed.json"))
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    feed = build_feed()
    out_path.write_text(json.dumps(feed, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
