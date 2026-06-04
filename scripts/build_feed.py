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
        "notes": meta.get("notes", []),
        "menus": [],
    }


# ---------- Wolt / Sziget ----------
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
    html = requests.get(KRISTALY_URL, headers=HEADERS, timeout=30)
    html.raise_for_status()
    html = html.text
    soup = BeautifulSoup(html, "html.parser")
    section = soup.find("section", id="heti-menu")
    if not section:
        return []

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
            # Guard: if column 3 looks like food text, it's likely mis-parsed — treat as extra text instead
            if price_text and looks_like_food_descriptor(price_text):
                soup_or_description = price_text
                price_text = None
                items[-1]["text"] = " — ".join([p for p in [soup, soup_or_description] if p]) or None
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

    # Compute vertical bands for each day
    day_bands: list[tuple[str, int, int]] = []
    for i, (day_en, top) in enumerate(day_rows):
        end = day_rows[i + 1][1] if i + 1 < len(day_rows) else 9999
        day_bands.append((day_en, top, end))

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
            # Join fragments, strip trailing allergen codes and prices
            raw = " ".join(frags)
            # Strip trailing price (e.g. "4990.-")
            raw = re.sub(r"\s*\d{3,5}\.-\s*$", "", raw).strip()
            # Normalise whitespace
            raw = re.sub(r"\s+", " ", raw).strip()
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
                if meta.get("slug") == "uj-zoldfa":
                    base["menus"] = collect_uj_zoldfa_week(meta, ctx)
                else:
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
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate existing feed, don't rebuild")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    feed = build_feed()

    errors = validate_feed(feed)
    for err in errors:
        print(f"  [VALIDATION] {err}")

    if any(e.startswith("CRITICAL") for e in errors):
        print("FATAL: validation errors prevent publishing")
        raise SystemExit(1)

    out_path.write_text(json.dumps(feed, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")
    if errors:
        print("Non-critical validation warnings above — feed written but review recommended")


if __name__ == "__main__":
    main()
