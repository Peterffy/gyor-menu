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
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
PUBLIC_DIR = BASE / "public"
RESTAURANTS_PATH = DATA_DIR / "restaurants.json"
OVERRIDES_PATH = DATA_DIR / "manual_overrides.json"

WEEKDAYS_HU = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap"]
WEEKDAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS_HU = {
    "január": 1,
    "február": 2,
    "március": 3,
    "április": 4,
    "május": 5,
    "június": 6,
    "július": 7,
    "augusztus": 8,
    "szeptember": 9,
    "október": 10,
    "november": 11,
    "december": 12,
}

KRISTALY_URL = "https://www.kristalyetterem.hu/"
WOLT_TEMPLATE = "https://wolt.com/hu/hun/{city}/restaurant/{slug}"
NADOR_PDF_BASE = "https://www.nadorvendeglo.hu/heti_menu/heti_menu_nador_{monday}.pdf"
ZOLDFA_PDF_URL = "https://ujzoldfa.hu/index.php?c=hmpdf"

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


def parse_hu_month_date(year: int, month_name: str, day: int) -> date:
    month = MONTHS_HU[month_name.strip().lower()]
    return date(year, month, day)


ALLOWED_PDF_DOMAINS = {"www.nadorvendeglo.hu", "nadorvendeglo.hu", "szalaivendeglo.hu", "www.szalaivendeglo.hu", "ujzoldfa.hu", "www.ujzoldfa.hu"}

def validate_source_url(url: str | None, meta: dict[str, Any]) -> str | None:
    """Ensure source URLs are allowed and use https:// where possible."""
    if not url:
        return None
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    # Allow any https:// URL, but reject non-http schemes
    if parsed.scheme not in ("http", "https"):
        meta.setdefault("notes", []).append(f"Rejected non-HTTP source URL scheme: {parsed.scheme}")
        return None
    # For weekly PDF collectors, validate against allowlist
    if meta.get("sourceType") in ("website_weekly_pdf", "website_weekly_pdf_listing"):
        if hostname not in ALLOWED_PDF_DOMAINS:
            meta.setdefault("notes", []).append(f"Source domain {hostname} not in PDF allowlist")
            return None
    return url


def parse_price_huf(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return None
    return int(digits)


def clean_carmen_item_text(raw: str) -> str:
    cut_markers = [
        "A menük gyümölcslevessel",
        "Áraink bruttó árak",
        "Az ételek allergén tartalmát",
    ]
    cut_positions = [raw.find(marker) for marker in cut_markers if marker in raw]
    if cut_positions:
        raw = raw[:min(cut_positions)]
    raw = re.sub(r"\s*[–-]?\s*(\d{1,2}[ .]?\d{3}|\d{3,5})\s*(?:,-)?\s*Ft\s*$", "", raw, flags=re.IGNORECASE)
    return raw.strip(" ,;-/")


def clean_carmen_menus(menus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for menu in menus:
        menu_copy = json.loads(json.dumps(menu, ensure_ascii=False))
        for item in menu_copy.get("items", []):
            text = item.get("text")
            if text:
                item["text"] = clean_carmen_item_text(text)
        cleaned.append(menu_copy)
    return cleaned


def fallback_menus_from_recent_feeds(slug: str, wanted_dates: set[str]) -> list[dict[str, Any]]:
    """Recover menus for the current week from recent feed snapshots.

    Used when a source publishes next week's menu too early and we still need the
    currently visible week to remain populated until the scheduled week switch.
    """
    snapshots: list[str] = []
    live_feed = PUBLIC_DIR / "data" / "feed.json"
    if live_feed.exists():
        try:
            snapshots.append(live_feed.read_text())
        except Exception:
            pass

    for ref in ["HEAD~1", "HEAD~2", "HEAD~3", "HEAD~4", "HEAD~5"]:
        try:
            raw = subprocess.check_output(
                ["git", "show", f"{ref}:public/data/feed.json"],
                cwd=str(BASE),
                text=True,
                timeout=15,
            )
            snapshots.append(raw)
        except Exception:
            continue

    for raw in snapshots:
        try:
            feed = json.loads(raw)
        except Exception:
            continue
        for restaurant in feed.get("restaurants", []):
            if restaurant.get("slug") != slug:
                continue
            menus = [m for m in restaurant.get("menus", []) if m.get("date") in wanted_dates]
            if wanted_dates.issubset({m.get("date") for m in menus}):
                if slug == "carmen-etterem":
                    return clean_carmen_menus(menus)
                return menus
    return []


def extract_price_huf(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(\d{1,2}[ .]?\d{3}|\d{3,5})\s*(?:,-)?\s*Ft", text, re.IGNORECASE)
    return parse_price_huf(match.group(0)) if match else None


def format_price_text(price_huf: int | None) -> str | None:
    return f"{price_huf:,} Ft".replace(",", " ") if price_huf else None


def looks_like_food_descriptor(text: str | None) -> bool:
    """Check if a string is more likely a food descriptor than a price."""
    if not text:
        return False
    t = text.strip()
    # Hungarian food descriptors commonly appearing in column 3 (price column)
    food_words = {"zöldsalátával", "savanyúsággal", "párolva", "ropogósra sütve"}
    if t.lower() in food_words:
        return True
    # Contains letters and no digits → not a price
    if re.search(r'[a-zA-ZáéíóöőúüűÁÉÍÓÖŐÚÜŰ]', t) and not re.search(r'[0-9]', t):
        return True
    return False


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
        "lat": meta.get("lat"),
        "lng": meta.get("lng"),
        "notes": meta.get("notes", []),
        "menus": [],
    }


# ---------- Wolt / Sziget ----------
def normalize_wolt_menu_label(label: str | None) -> str | None:
    if not label:
        return label
    cleaned = re.sub(r"\s+", " ", str(label)).strip()
    cleaned = re.sub(r"memü", "menü", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"nenü", "menü", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    return cleaned


def normalize_wolt_menu_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.replace("\n", ", ")
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    return cleaned or None


def is_meaningful_wolt_label_only_item(label: str | None) -> bool:
    if not label:
        return False
    low = label.lower()
    keywords = ("menü", "menu", "extra", "vega", "leves", "főétel")
    return any(keyword in low for keyword in keywords)


def collect_wolt_current(meta: dict[str, Any], ctx: CollectContext) -> list[dict[str, Any]]:
    slug = meta["slug"]
    url = WOLT_TEMPLATE.format(city="gyor", slug=slug)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text
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
        label = normalize_wolt_menu_label(item.get("name"))
        desc = normalize_wolt_menu_text(item.get("description"))
        price_huf = int(item.get("price", 0) / 100) if item.get("price") else None
        if not desc and not is_meaningful_wolt_label_only_item(label):
            continue
        entries.append({
            "label": label,
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
    html = requests.get(KRISTALY_URL, headers=HEADERS, timeout=30)
    html.raise_for_status()
    html = html.text
    soup = BeautifulSoup(html, "html.parser")
    section = soup.find("section", id="heti-menu")
    if not section:
        return []

    section_text = re.sub(r"\s+", " ", section.get_text(" ", strip=True))
    main_price_match = re.search(r"Menü áraink helyben\s*(\d{1,2}[ .]?\d{3})\s*Ft", section_text, re.IGNORECASE)
    main_price_huf = parse_price_huf(main_price_match.group(1)) if main_price_match else None

    date_map = map_dates_for_current_week(ctx)
    menus = []
    # Only take the first table (current week) — the site sometimes shows two weeks
    first_table = section.select_one(".table")
    if not first_table:
        return []
    for row in first_table.select(".day-row"):
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
            normalized_label = label.strip('"')
            price_huf = main_price_huf if normalized_label in {"A", "B", "C"} else None
            items.append({
                "label": label or None,
                "text": content or None,
                "priceHuf": price_huf,
                "priceText": format_price_text(price_huf),
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
    resp.raise_for_status()
    return resp.content if resp.status_code == 200 else None


def fetch_weekly_pdf_from_listing(meta: dict[str, Any], ctx: CollectContext) -> bytes | None:
    listing_url = validate_source_url(meta.get("sourceUrl"), meta)
    if not listing_url:
        return None
    html = requests.get(listing_url, headers=HEADERS, timeout=30)
    html.raise_for_status()
    html_text = html.text
    soup = BeautifulSoup(html_text, "html.parser")
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
    resp.raise_for_status()
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
        if i > 0:
            start = (sorted_days[i - 1][1] + top_pos) // 2
        else:
            # first day should skip the PDF title/header but still include the soup row above the day label
            start = max(0, top_pos - 40)
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
            price_idx = None
            for i in range(len(col) - 1, -1, -1):
                if parse_price_huf(col[i]) is not None:
                    price_idx = i
                    break
            price_text = col[price_idx] if price_idx is not None else None
            main_parts = col[1:price_idx] if price_idx is not None else col[1:]
            # if the would-be price is actually food text, keep it inside the main text instead
            if price_text and looks_like_food_descriptor(price_text):
                main_parts = col[1:]
                price_text = None
            main = " ".join([part for part in main_parts if part]).strip() or None
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


# ---------- Új Zöldfa (PDF grid: Leves + Menü A-E, 7 days) ----------

def collect_uj_zoldfa_week(meta: dict[str, Any], ctx: CollectContext) -> list[dict[str, Any]]:
    resp = requests.get(ZOLDFA_PDF_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    pdf_bytes = resp.content

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "menu.pdf"
        xml_path = Path(tmp) / "menu.xml"
        pdf_path.write_bytes(pdf_bytes)
        subprocess.run(
            ["pdftohtml", "-xml", "-i", "-nodrm", str(pdf_path), str(xml_path)],
            check=False, capture_output=True, timeout=30,
        )
        tree = ElementTree.parse(str(xml_path))

    page = tree.getroot().find("page")
    if page is None:
        return []

    # Collect all text elements with (top, left, content)
    texts: list[tuple[int, int, str]] = []
    for el in page.findall("text"):
        top = int(el.get("top", 0))
        left = int(el.get("left", 0))
        content = "".join(el.itertext()).strip()
        if content:
            texts.append((top, left, content))
    texts.sort(key=lambda x: (x[0], x[1]))

    # Column labels: Leves ~231, Menü A ~393, Menü B ~555, Menü C ~717, Menü D ~879, Menü E ~1042
    # We group by column band (midpoints between header positions)
    # Using fixed boundaries from observed XML positions with generous slack
    def col_label(left: int) -> str | None:
        if 200 <= left < 312:   return "Leves"
        if 312 <= left < 474:   return "A menü"
        if 474 <= left < 636:   return "B menü"
        if 636 <= left < 798:   return "C menü"
        if 798 <= left < 960:   return "D menü"
        if left >= 960:          return "E menü"
        return None  # day name column

    # Find day row boundaries by detecting day name text (left < 200, bold)
    day_rows: list[tuple[str, int]] = []  # (day_en, top)
    for top, left, content in texts:
        if left >= 200:
            continue
        hu = content.strip()
        if hu in WEEKDAYS_HU:
            day_en = WEEKDAYS_EN[WEEKDAYS_HU.index(hu)]
            day_rows.append((day_en, top))

    if not day_rows:
        return []

    # Compute vertical bands for each day.
    # The PDF is slightly misaligned: some meal text can begin a few pixels above
    # the day label, while the next day starts just below the previous band.
    # So use a small negative/positive tolerance around day-label tops instead of
    # a midpoint cut, which was too aggressive for weekend rows.
    day_bands: list[tuple[str, int, int]] = []
    for i, (day_en, top) in enumerate(day_rows):
        start = max(0, top - 4)
        if i + 1 < len(day_rows):
            next_top = day_rows[i + 1][1]
            end = max(start + 1, next_top - 4)
        else:
            end = 619  # observed footer/jegy legend starts below the Sunday content block
        day_bands.append((day_en, start, end))

    date_map = {WEEKDAYS_EN[i]: iso(ctx.monday + timedelta(days=i)) for i in range(7)}
    menus = []

    for day_en, row_top, row_end in day_bands:
        # Gather text fragments in this row, grouped by column
        col_texts: dict[str, list[str]] = {}
        for top, left, content in texts:
            if top < row_top or top >= row_end:
                continue
            label = col_label(left)
            if label is None:
                continue
            col_texts.setdefault(label, []).append(content)

        if not col_texts:
            continue

        items = []
        for label in ["Leves", "A menü", "B menü", "C menü", "D menü", "E menü"]:
            frags = col_texts.get(label)
            if not frags:
                continue
            # Join fragments, strip footer/disclaimer bleed and trailing prices.
            raw = " ".join(frags)
            footer_markers = [
                "Ebédjegy",
                "A MENÜ ÁRAK",
                "Jelmagyarázat:",
                "G - Glutén",
                "1 / 1",
            ]
            cut_positions = [raw.find(marker) for marker in footer_markers if marker in raw]
            if cut_positions:
                raw = raw[:min(cut_positions)]
            # Strip trailing price (e.g. "4990.-")
            raw = re.sub(r"\s*\d{3,5}\.-\s*$", "", raw).strip()
            # Normalise whitespace
            raw = re.sub(r"\s+", " ", raw).strip(" ,;-/")
            if raw:
                items.append({"label": label, "text": raw})

        if not items:
            continue
        # Skip Saturday/Sunday if it only has a soup (weekends have higher-priced a la carte, not lunch)
        if day_en in {"saturday", "sunday"} and len(items) == 1 and items[0]["label"] == "Leves":
            continue

        menus.append({
            "date": date_map[day_en],
            "dayNameHu": WEEKDAYS_HU[WEEKDAYS_EN.index(day_en)],
            "certainty": "exact",
            "sourceLabel": "Heti menü PDF",
            "sourceUrl": ZOLDFA_PDF_URL,
            "updatedAt": now_iso(),
            "items": items,
            "notes": [],
        })

    return menus


# ---------- Carmen (weekly HTML menu) ----------

def collect_carmen_week(meta: dict[str, Any], ctx: CollectContext) -> list[dict[str, Any]]:
    url = meta.get("sourceUrl") or "https://www.carmenetterem.hu/hu/business-menu"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    article = soup.find("section", class_="article") or soup.find("article") or soup
    lines = [re.sub(r"\s+", " ", x).strip() for x in article.get_text("\n", strip=True).splitlines()]
    lines = [x for x in lines if x]

    m = re.search(r"(\d{4})\.\s*([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]+)\s*(\d{1,2})-(\d{1,2})\.", " ".join(lines))
    if not m:
        return []
    year = int(m.group(1))
    month_name = m.group(2)
    start_day = int(m.group(3))
    monday = parse_hu_month_date(year, month_name, start_day)
    source_date_map = {WEEKDAYS_HU[i]: iso(monday + timedelta(days=i)) for i in range(5)}

    # If Carmen already switched to next week before the site should switch weeks,
    # keep the currently visible week's menus from a recent feed snapshot.
    if monday > ctx.monday:
        wanted_dates = {iso(ctx.monday + timedelta(days=i)) for i in range(5)}
        fallback = fallback_menus_from_recent_feeds(meta.get("slug", ""), wanted_dates)
        if fallback:
            return fallback

    date_map = source_date_map
    menus = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line not in WEEKDAYS_HU[:5]:
            i += 1
            continue
        day_name = line
        i += 1
        day_lines = []
        while i < len(lines) and lines[i] not in WEEKDAYS_HU[:5]:
            day_lines.append(lines[i])
            i += 1

        items = []
        soups = []
        j = 0
        while j < len(day_lines) and day_lines[j] != "A:":
            cur = day_lines[j]
            if cur in {"Leves", "DÉLI MENÜ", "Napi ajándék desszert"} or cur.startswith("(") or "Ft" in cur:
                j += 1
                continue
            soups.append(cur)
            j += 1
        if soups:
            items.append({"label": "Leves", "text": " / ".join(soups)})

        while j < len(day_lines):
            label = day_lines[j]
            if label not in {"A:", "B:", "C:", "X:"}:
                j += 1
                continue
            pretty = {"A:": "A menü", "B:": "B menü", "C:": "C menü", "X:": "X menü"}[label]
            j += 1
            chunks = []
            while j < len(day_lines) and day_lines[j] not in {"A:", "B:", "C:", "X:"}:
                cur = day_lines[j]
                if cur.startswith("(") or cur == "Napi ajándék desszert":
                    j += 1
                    continue
                if cur.startswith("A menük gyümölcslevessel") or cur.startswith("Áraink bruttó árak") or cur.startswith("Az ételek allergén tartalmát"):
                    break
                chunks.append(cur)
                j += 1
            if chunks:
                raw = " ".join(chunks)
                price_huf = extract_price_huf(raw)
                cleaned = clean_carmen_item_text(raw)
                items.append({
                    "label": pretty,
                    "text": cleaned or raw,
                    "priceHuf": price_huf,
                    "priceText": format_price_text(price_huf),
                })

        if items:
            menus.append({
                "date": date_map[day_name],
                "dayNameHu": day_name,
                "certainty": "exact",
                "sourceLabel": "Weekly website menu",
                "sourceUrl": url,
                "updatedAt": now_iso(),
                "items": items,
                "notes": [],
            })
    return menus


# ---------- Marcal (weekly HTML text menu) ----------

def parse_marcal_week_from_text(text: str, url: str) -> list[dict[str, Any]]:
    matches = list(re.finditer(r"(\d{4})\.(\d{2})\.(\d{2})\.\s*-?\s*([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]+)", text))
    menus = []
    for idx, m in enumerate(matches):
        day_block_start = m.start()
        day_block_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[day_block_start:day_block_end]
        if "Levesek" not in block[:500]:
            continue
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        day_name = WEEKDAYS_HU[d.weekday()]
        if day_name not in WEEKDAYS_HU[1:6]:
            continue
        lines = [re.sub(r"\s+", " ", x).strip() for x in block.splitlines()]
        lines = [x for x in lines if x]
        flat_block = " ".join(lines)
        daily_price_match = re.search(r"(?:Napi\s+)?Menüajánlatunk\s*El\s*vitelre\s*(\d{1,2}[ .]?\d{3}|\d{3,5})\s*,-?\s*Ft,?\s*helyben(?:\s+fogyasztva)?:?\s*(\d{1,2}[ .]?\d{3}|\d{3,5})(?:\s*,-?\s*Ft)?", flat_block, re.IGNORECASE)
        super_price_match = re.search(r"Szuper menü:?\s*El\s*vitelre\s*(\d{1,2}[ .]?\d{3}|\d{3,5})\s*,-?\s*Ft,?\s*helyben(?:\s+fogyasztva)?:?\s*(\d{1,2}[ .]?\d{3}|\d{3,5})(?:\s*,-?\s*Ft)?", flat_block, re.IGNORECASE)
        daily_price_huf = parse_price_huf(daily_price_match.group(2)) if daily_price_match else None
        super_price_huf = parse_price_huf(super_price_match.group(2)) if super_price_match else None

        items = []
        soups = []
        menu_heading_idx = None
        for idx2, line2 in enumerate(lines):
            if line2 in {"Napi menüajánlatunk", "Menüajánlatunk"}:
                menu_heading_idx = idx2
                break
        j = 0
        while j < len(lines) and (menu_heading_idx is None or j < menu_heading_idx):
            cur = lines[j]
            if cur in {m.group(0), day_name, "Levesek", f"- {day_name}", f"{day_name}"} or cur.startswith("2026.") or cur.startswith("("):
                j += 1
                continue
            if cur in {"P", "éntek"}:
                j += 1
                continue
            if "Desszertek" in cur or "Szuper menü" in cur or "Allergének" in cur:
                break
            if "Ft" not in cur and len(cur) > 2:
                soups.append(cur)
            j += 1
        if soups:
            items.append({"label": "Levesek", "text": " / ".join(soups[:4])})

        if menu_heading_idx is not None:
            start = menu_heading_idx + 1
            mains = []
            for cur in lines[start:]:
                if cur.startswith("Desszertek") or cur.startswith("Szuper menü") or cur.startswith("Allergének"):
                    break
                if cur in {"P", "éntek"}:
                    continue
                if "Ft" in cur or cur.startswith("Elvitelre") or cur.startswith("Minden napi menü") or cur.startswith("Halászlé+"):
                    continue
                mains.append(cur)
            for n, meal in enumerate(mains[:6], 1):
                items.append({
                    "label": f"Napi menü {n}",
                    "text": meal,
                    "priceHuf": daily_price_huf,
                    "priceText": format_price_text(daily_price_huf),
                })

        if "Szuper menü" in lines:
            start = lines.index("Szuper menü") + 1
            supers = []
            for cur in lines[start:]:
                if cur.startswith("Allergének") or cur.startswith("Minden napi menü"):
                    break
                if "Ft" in cur or cur.startswith("El") or cur.startswith("helyben") or cur.startswith("vitelre") or cur.startswith("Minden napi menü") or cur.startswith("Halászlé+"):
                    continue
                supers.append(cur)
            for n, meal in enumerate(supers[:3], 1):
                items.append({
                    "label": f"Szuper menü {n}",
                    "text": meal,
                    "priceHuf": super_price_huf,
                    "priceText": format_price_text(super_price_huf),
                })

        if items:
            menus.append({
                "date": iso(d),
                "dayNameHu": day_name,
                "certainty": "exact",
                "sourceLabel": "Weekly website menu",
                "sourceUrl": url,
                "updatedAt": now_iso(),
                "items": items,
                "notes": [],
            })
    return menus


def collect_marcal_week(meta: dict[str, Any], ctx: CollectContext) -> list[dict[str, Any]]:
    url = meta.get("sourceUrl") or "https://marcal-etterem.hu/heti-menu/"
    script = Path(__file__).resolve().parent / 'fetch_marcal_browser_text.py'
    python_bin = Path(__file__).resolve().parent.parent / '.venv' / 'bin' / 'python'
    if script.exists() and python_bin.exists():
        try:
            raw = subprocess.check_output(
                [str(python_bin), str(script), '--url', url],
                text=True,
                timeout=180,
            )
            data = json.loads(raw)
            per_day_text = data.get('per_day_text') or {}
            menus: list[dict[str, Any]] = []
            seen_dates: set[str] = set()
            for _day, text in per_day_text.items():
                if not text or str(text).startswith('__ERROR__'):
                    continue
                for menu in parse_marcal_week_from_text(text, url):
                    if menu['date'] in seen_dates:
                        continue
                    seen_dates.add(menu['date'])
                    menus.append(menu)
            if menus:
                return sorted(menus, key=lambda x: x['date'])
        except Exception:
            pass
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    text = soup.get_text('\n', strip=True)
    return parse_marcal_week_from_text(text, url)


# ---------- Komédiás (weekly website image OCR) ----------

def fetch_komedias_menu_image_url(meta: dict[str, Any]) -> str | None:
    page_url = meta.get("sourceUrl") or "https://komediasetterem.hu/index.php/heti-menu"
    resp = requests.get(page_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    candidates: list[str] = []
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        lower = src.lower()
        if "/images/heti_menu/" not in lower:
            continue
        if re.search(r"/amenu\d+\.(jpg|jpeg|png)$", lower):
            candidates.append(urljoin(page_url, src))
    return candidates[0] if candidates else None


def ocr_hun_image_crop(img: Image.Image, box: tuple[int, int, int, int], psm: str = "6") -> str:
    crop = img.crop(box).convert("L")
    crop = ImageOps.autocontrast(crop)
    crop = crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.LANCZOS)
    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "crop.png"
        out_base = Path(tmp) / "ocr"
        crop.save(in_path)
        subprocess.run(
            ["tesseract", str(in_path), str(out_base), "-l", "hun", "--psm", psm],
            check=False,
            capture_output=True,
            timeout=30,
        )
        txt_path = out_base.with_suffix(".txt")
        if not txt_path.exists():
            return ""
        return txt_path.read_text(errors="ignore")


def clean_ocr_fragment(text: str) -> str:
    text = text.replace("|", " ")
    replacements = {
        "fÍriss": "friss",
        "Íriss": "friss",
        "tooston": "Roston",
        "toston": "Roston",
        "ppparadicsommal": "paradicsommal",
        "pparadicsommal": "paradicsommal",
        "pparadicsom": "paradicsom",
        "aradicsom": "paradicsom",
        "C(öménymag": "Köménymag",
        "Koöoménymag": "Köménymag",
        "BBrassói": "Brassói",
        "rassói": "Brassói",
        "nhorkával": "uborkával",
        "jföllel": "tejföllel",
        "tetejföllel": "tejföllel",
        "chips el": "chips-el",
        "rizibizivelés": "rizibizivel és",
        "rizzselés": "rizzsel és",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\bp+paradicsommal\b", "paradicsommal", text)
    text = re.sub(r"\bp+paradicsom\b", "paradicsom", text)
    text = re.sub(r"\bBBrassói\b", "Brassói", text)
    text = text.replace("sütvel", "sütve")
    text = text.replace("(G,,T)", "(G,L,T)")
    text = text.replace("kukoricapelyhes;", "kukoricapelyhes")
    # remove common standalone OCR allergen debris outside parentheses
    text = re.sub(r"(?<!\()\b(?:IGT|GT|G|L|T|IG)\b(?!\))", "", text)
    text = text.replace("[", " ").replace("]", " ")
    text = re.sub(r"\bte\s*$", "", text)
    text = re.sub(r"\b([js])\b", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"^[;:,.!\s]+", "", text)
    return text.strip(" -|\n\t")


def parse_komedias_cell(text: str) -> tuple[str | None, str | None]:
    lines = [clean_ocr_fragment(x) for x in text.splitlines() if clean_ocr_fragment(x)]
    if not lines:
        return None, None
    soup_lines: list[str] = []
    rest: list[str] = []
    seen_non_soup = False
    soup_wrap_markers = ("chips", "kenyérkock", "gombóccal", "taco", "pirított")
    for line in lines:
        lower = line.lower()
        is_probable_junk = len(re.sub(r"[^a-záéíóöőúüűA-ZÁÉÍÓÖŐÚÜŰ]", "", line)) <= 2
        if is_probable_junk:
            continue
        if not seen_non_soup and (
            "leves" in lower
            or (soup_lines and any(marker in lower for marker in soup_wrap_markers))
        ):
            soup_lines.append(line)
            continue
        seen_non_soup = True
        rest.append(line)
    soup = clean_ocr_fragment(" ".join(soup_lines)) if soup_lines else None
    main = clean_ocr_fragment(" ".join(rest)) if rest else None
    return soup, main


def collect_komedias_week(meta: dict[str, Any], ctx: CollectContext) -> list[dict[str, Any]]:
    img_url = fetch_komedias_menu_image_url(meta)
    if not img_url:
        return []
    resp = requests.get(img_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content))
    width, height = img.size

    def rx(v: int) -> int:
        return round(v / 1488 * width)

    def ry(v: int) -> int:
        return round(v / 2104 * height)

    cols = {
        "A": (rx(170), rx(590)),
        "B": (rx(590), rx(960)),
        "V": (rx(960), rx(1360)),
    }
    rows = [
        ("monday", ry(620), ry(790)),
        ("tuesday", ry(790), ry(965)),
        ("wednesday", ry(965), ry(1145)),
        ("thursday", ry(1145), ry(1325)),
        ("friday", ry(1325), ry(1515)),
    ]

    menus = []
    date_map = {WEEKDAYS_EN[i]: iso(ctx.monday + timedelta(days=i)) for i in range(7)}
    for day_en, y1, y2 in rows:
        a_text = ocr_hun_image_crop(img, (cols["A"][0], y1, cols["A"][1], y2))
        b_text = ocr_hun_image_crop(img, (cols["B"][0], y1, cols["B"][1], y2))
        v_text = ocr_hun_image_crop(img, (cols["V"][0], y1, cols["V"][1], y2))

        soup_a, main_a = parse_komedias_cell(a_text)
        soup_b, main_b = parse_komedias_cell(b_text)
        soup_v, main_v = parse_komedias_cell(v_text)

        if soup_v and main_v and main_v.lower().startswith("el (l)"):
            soup_v = clean_ocr_fragment(f"{soup_v}-el (L)")
            main_v = clean_ocr_fragment(re.sub(r"^el \(l\)\s*", "", main_v, flags=re.I))

        items: list[dict[str, Any]] = []
        if soup_a or soup_b:
            soup_ab = soup_a or soup_b
            if soup_ab:
                items.append({"label": "Leves (A+B)", "text": soup_ab})
        if soup_v and soup_v != (soup_a or soup_b):
            items.append({"label": "Leves (Vega)", "text": soup_v})
        if main_a:
            items.append({"label": "A menü", "text": main_a})
        if main_b:
            items.append({"label": "B menü", "text": main_b})
        if main_v:
            items.append({"label": "Vega", "text": main_v})

        # Guardrails against OCR junk
        items = [it for it in items if it.get("text") and len(it["text"].strip()) > 6]
        if not items:
            continue

        menus.append({
            "date": date_map[day_en],
            "dayNameHu": WEEKDAYS_HU[WEEKDAYS_EN.index(day_en)],
            "certainty": "current_snapshot",
            "sourceLabel": "Website menu image OCR",
            "sourceUrl": img_url,
            "updatedAt": now_iso(),
            "items": items,
            "notes": [
                "Parsed from Komédiás weekly menu image on the website.",
                "OCR-based extraction; minor text errors may remain."
            ],
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


def build_feed(today_override: date | None = None) -> dict[str, Any]:
    registry = load_json(RESTAURANTS_PATH)
    overrides = maybe_load_overrides()
    today = today_override or date.today()
    ctx = CollectContext(today=today, tomorrow=today + timedelta(days=1), monday=current_monday(today))

    restaurants_out = []
    for meta in registry.get("restaurants", []):
        base = build_base_restaurant(meta)
        source_type = meta.get("sourceType")
        try:
            if source_type == "wolt_current":
                base["menus"] = collect_wolt_current(meta, ctx)
            elif source_type == "website_weekly_html":
                if meta.get("slug") == "kristaly-etterem":
                    base["menus"] = collect_kristaly_week(meta, ctx)
                elif meta.get("slug") == "carmen-etterem":
                    base["menus"] = collect_carmen_week(meta, ctx)
                elif meta.get("slug") == "marcal-etterem":
                    base["menus"] = collect_marcal_week(meta, ctx)
                else:
                    base["notes"] = base.get("notes", []) + ["Unsupported weekly HTML collector"]
            elif source_type == "website_weekly_pdf":
                if meta.get("slug") == "uj-zoldfa":
                    base["menus"] = collect_uj_zoldfa_week(meta, ctx)
                else:
                    pdf = fetch_nador_pdf(ctx)
                    base["menus"] = parse_fourcol_pdf_week(pdf, meta, ctx) if pdf else []
            elif source_type == "website_weekly_pdf_listing":
                pdf = fetch_weekly_pdf_from_listing(meta, ctx)
                base["menus"] = parse_fourcol_pdf_week(pdf, meta, ctx) if pdf else []
            elif source_type == "website_menu_image_snapshot":
                if meta.get("slug") == "komedias-etterem":
                    base["menus"] = collect_komedias_week(meta, ctx)
                else:
                    base["notes"] = base.get("notes", []) + [
                        "This source currently relies on manual review, image-based extraction, or fallback input."
                    ]
            elif source_type in {"facebook_unstructured", "manual_review_only"}:
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
    feed = strip_internal_urls(feed)
    return feed


def strip_internal_urls(feed: dict[str, Any]) -> dict[str, Any]:
    """Remove internal Drive URLs from public feed fields."""
    drive_pattern = re.compile(r'drive\.google\.com/(?:file|open|drive/folders)/')
    for restaurant in feed.get("restaurants", []):
        for menu in restaurant.get("menus", []):
            if menu.get("sourceUrl") and drive_pattern.search(menu["sourceUrl"]):
                # Replace internal source with the restaurant's canonical source
                menu["sourceUrl"] = restaurant.get("sourceUrl", None)
                if menu.get("sourceLabel", "").startswith("Manual override"):
                    menu["sourceLabel"] = "Screenshot / manual"
            # Strip Drive URLs from notes too
            safe_notes = []
            for note in menu.get("notes", []):
                if drive_pattern.search(note):
                    note = re.sub(r'https?://drive\.google\.com/\S+', '(internal source)', note)
                safe_notes.append(note)
            menu["notes"] = safe_notes
    return feed


def validate_feed(feed: dict[str, Any]) -> list[str]:
    """Validate feed and return list of warnings/errors. Fail loudly on critical issues."""
    errors = []
    today = feed.get("today", "")
    restaurants = feed.get("restaurants", [])

    if not restaurants:
        errors.append("CRITICAL: feed has zero restaurants — refusing to publish")

    today_menus = 0
    for r in restaurants:
        for m in r.get("menus", []):
            if m.get("date") == today:
                today_menus += 1

    if today_menus == 0:
        errors.append("WARNING: no restaurant has a menu for today — data may be stale")

    # Check that each collector didn't silently fail
    for r in restaurants:
        notes = r.get("notes", [])
        collector_errors = [n for n in notes if "error" in n.lower() or "collector error" in n.lower()]
        if collector_errors:
            errors.append(f"Collector error for {r['slug']}: {'; '.join(collector_errors)}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PUBLIC_DIR / "data" / "feed.json"))
    parser.add_argument("--today-override", help="Logical today date to publish as YYYY-MM-DD")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate existing feed, don't rebuild")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    today_override = date.fromisoformat(args.today_override) if args.today_override else None
    feed = build_feed(today_override=today_override)

    errors = validate_feed(feed)
    for err in errors:
        print(f"  [VALIDATION] {err}")

    if any(e.startswith("CRITICAL") for e in errors):
        print("FATAL: validation errors prevent publishing")
        raise SystemExit(1)

    out_path.write_text(json.dumps(feed, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")

    from generate_share_pages import generate_share_pages
    generate_share_pages(feed)
    print("Generated share-stable restaurant pages")

    if errors:
        print("Non-critical validation warnings above — feed written but review recommended")


if __name__ == "__main__":
    main()
