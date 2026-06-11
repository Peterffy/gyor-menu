#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

BASE = Path(__file__).resolve().parent.parent

TYPO_HINTS = {
    " memü": "valószínű OCR typo (menü)",
    " nenü": "valószínű OCR typo (menü)",
    " keves": "valószínű OCR typo (leves)",
    "None": "üres/törött sor",
}

SHORT_BAD_VALUES = {
    "rizzsel",
    "hasábburgonya",
    "krokett",
    "galuska",
    "pörkölttel/g,l/",
    "joghurtos kevert salátán/g,l/",
    "hasábburgonya/g,t/",
}

STRUCTURED_SOURCE_TYPES = {
    "website_weekly_html",
    "website_weekly_pdf",
    "website_weekly_pdf_listing",
}


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def find_suspicion_reasons(menu: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for item in menu.get("items", []):
        label = str(item.get("label") or "")
        text = item.get("text")
        if text is None or str(text).strip() == "":
            reasons.append(f"üres menüsor: {label or 'ismeretlen'}")
            continue
        t = str(text).strip()
        low = t.lower()
        for needle, reason in TYPO_HINTS.items():
            if needle.strip().lower() in low:
                reasons.append(reason)
        if low in SHORT_BAD_VALUES:
            reasons.append(f"túl rövid / töredékes tétel: {label} = {t}")
        if re.search(r"[a-záéíóöőúüű]{4,}és[A-ZÁÉÍÓÖŐÚÜŰ0-9]", t):
            reasons.append(f"összecsúszott szavak: {label}")
        if re.search(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]{2,}[./][A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]{1,}", t):
            reasons.append(f"zajos OCR / törött allergénkód: {label}")
        if re.search(r"[ÍÉÁŐŰÚÜÖÓ][^\s]{0,2}\s|\s[^\s]{0,2}[ÍÉÁŐŰÚÜÖÓ]", t):
            reasons.append(f"valószínű OCR zaj: {label}")
    out: list[str] = []
    for r in reasons:
        if r not in out:
            out.append(r)
    return out


def stable_daily_choice(slugs: list[str], seed_text: str) -> str:
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    rng = random.Random(seed)
    return rng.choice(sorted(slugs))


def restaurant_menu_for_date(restaurant: dict[str, Any], date_str: str) -> dict[str, Any] | None:
    menus = [m for m in restaurant.get("menus", []) if m.get("date") == date_str]
    return menus[0] if menus else None


def merge_registry_and_feed(feed_restaurant: dict[str, Any], registry_by_slug: dict[str, dict[str, Any]]) -> dict[str, Any]:
    reg_restaurant = registry_by_slug.get(feed_restaurant.get("slug", ""), {})
    return {**reg_restaurant, **feed_restaurant}


def restaurant_issue_codes(restaurant: dict[str, Any], date_str: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    source_type = restaurant.get("sourceType")
    address = (restaurant.get("address") or "").strip()

    if not address:
        issues.append({"code": "missing_address", "message": "hiányzó étteremcím"})
    elif address.lower() in {"győr", "gyor"}:
        issues.append({"code": "generic_registry_address", "message": "a registry-ben csak túl általános cím szerepel"})
    if not restaurant.get("area"):
        issues.append({"code": "missing_area", "message": "hiányzó városrész"})
    if not restaurant.get("sourceUrl"):
        issues.append({"code": "missing_source_url", "message": "hiányzó forráslink"})

    menu = restaurant_menu_for_date(restaurant, date_str)
    if not menu:
        issues.append({"code": "missing_menu_today", "message": "nincs menü az adott napra"})
        return issues

    item_text_blob = " ".join(str(item.get("text") or "") for item in menu.get("items", []))
    closure_detected = bool(re.search(r"\bzárva\b|\báramszünet\b|\btechnikai ok\b", item_text_blob, re.IGNORECASE))
    if closure_detected:
        issues.append({
            "code": "closure_notice_today",
            "message": "a hely ma zárva / rendkívüli állapot jelzés látszik",
        })
    else:
        suspicion_reasons = find_suspicion_reasons(menu)
        if suspicion_reasons:
            issues.append({
                "code": "suspicious_menu_text",
                "message": "gyanús / zajos menüszöveg",
                "details": suspicion_reasons,
            })

    item_counts = [len(m.get("items", [])) for m in restaurant.get("menus", []) if m.get("items")]
    today_count = len(menu.get("items", []))
    if not closure_detected and item_counts:
        typical = median(item_counts)
        if typical >= 3 and today_count <= max(1, typical - 2):
            issues.append({
                "code": "unusually_short_menu",
                "message": f"szokatlanul rövid napi menü ({today_count} tétel a tipikus {typical} helyett)",
            })

    if source_type in STRUCTURED_SOURCE_TYPES and menu.get("certainty") != "exact":
        issues.append({
            "code": "structured_source_not_exact",
            "message": f"strukturált forrás, de a certainty nem exact ({menu.get('certainty')})",
        })

    priced_items = sum(1 for item in menu.get("items", []) if item.get("priceHuf") or item.get("priceText"))
    if source_type in STRUCTURED_SOURCE_TYPES and today_count > 0 and priced_items == 0:
        issues.append({
            "code": "no_prices_on_structured_menu",
            "message": "strukturált forrású menü, de nincs egyetlen ár sem a napi menüben",
        })

    if source_type in STRUCTURED_SOURCE_TYPES and today_count > 0 and 0 < priced_items < today_count:
        issues.append({
            "code": "partial_prices_on_structured_menu",
            "message": f"strukturált forrású menü, de csak részleges az árfedettség ({priced_items}/{today_count})",
        })

    return issues


def peer_scan(restaurants: list[dict[str, Any]], registry_by_slug: dict[str, dict[str, Any]], date_str: str, issue_code: str) -> list[dict[str, str]]:
    affected: list[dict[str, str]] = []
    for feed_restaurant in restaurants:
        restaurant = merge_registry_and_feed(feed_restaurant, registry_by_slug)
        issues = restaurant_issue_codes(restaurant, date_str)
        if any(issue.get("code") == issue_code for issue in issues):
            affected.append({"slug": restaurant.get("slug", ""), "name": restaurant.get("name", "")})
    return affected


def build_report(feed: dict[str, Any], registry: dict[str, Any], selected_slug: str) -> str:
    date_str = feed["today"]
    by_slug = {r["slug"]: r for r in registry["restaurants"]}
    feed_restaurant = next(r for r in feed["restaurants"] if r["slug"] == selected_slug)
    merged = merge_registry_and_feed(feed_restaurant, by_slug)

    issues = restaurant_issue_codes(merged, date_str)
    menu = restaurant_menu_for_date(merged, date_str)
    item_count = len(menu.get("items", [])) if menu else 0
    price_count = sum(1 for item in (menu.get("items", []) if menu else []) if item.get("priceHuf") or item.get("priceText"))

    lines: list[str] = []
    lines.append(f"Győr Menü — napi random audit ({date_str})")
    lines.append("")
    lines.append(f"Kiválasztott étterem: {merged.get('name')} ({selected_slug})")
    lines.append(f"Forrástípus: {merged.get('sourceType') or 'ismeretlen'}")
    lines.append(f"Mai menü certainty: {(menu or {}).get('certainty', 'nincs menü')}")
    lines.append(f"Mai menü tételek: {item_count}")
    lines.append(f"Mai árazott tételek: {price_count}")
    lines.append("")
    lines.append("Mit ellenőriztünk:")
    lines.append("- registry metaadatok (cím, városrész, forráslink)")
    lines.append("- mai menü jelenléte")
    lines.append("- gyanús / zajos menüszöveg")
    lines.append("- szokatlanul rövid menü")
    lines.append("- certainty vs forrástípus")
    lines.append("- árak teljessége strukturált forrásnál")
    lines.append("")

    if not issues:
        lines.append("Eredmény: ennél az étteremnél most nem találtam automatikusan jelzett minőségi hibát.")
        lines.append("Napi státusz: rendben / nincs további keresztellenőrzés szükség.")
        return "\n".join(lines)

    lines.append(f"Talált problémák: {len(issues)}")
    for issue in issues:
        lines.append(f"- {issue['message']} [{issue['code']}]")
        for detail in issue.get("details", [])[:5]:
            lines.append(f"  · {detail}")
    lines.append("")
    lines.append("Ugyanezeket a problémakódokat keresztellenőriztem a többi étteremnél is:")
    restaurants = feed.get("restaurants", [])
    for issue in issues:
        peers = peer_scan(restaurants, by_slug, date_str, issue["code"])
        lines.append(f"- {issue['code']}: {len(peers)} érintett étterem")
        for peer in peers[:10]:
            lines.append(f"  · {peer['name']} ({peer['slug']})")
        if len(peers) > 10:
            lines.append(f"  · ... és még {len(peers) - 10}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", default=str(BASE / "public" / "data" / "feed.json"))
    ap.add_argument("--registry", default=str(BASE / "data" / "restaurants.json"))
    ap.add_argument("--date", help="Override feed.today for selection seed only")
    ap.add_argument("--slug", help="Audit a specific restaurant instead of daily random selection")
    ap.add_argument("--seed", help="Override selection seed text")
    args = ap.parse_args()

    feed = load_json(args.feed)
    registry = load_json(args.registry)
    date_str = args.date or feed["today"]
    restaurants = feed.get("restaurants", [])

    if args.slug:
        selected_slug = args.slug
    else:
        candidate_slugs = [r["slug"] for r in restaurants if restaurant_menu_for_date(r, feed["today"])]
        if not candidate_slugs:
            candidate_slugs = [r["slug"] for r in restaurants]
        seed_text = args.seed or f"gyor-menu-daily-audit:{date_str}"
        selected_slug = stable_daily_choice(candidate_slugs, seed_text)

    print(build_report(feed, registry, selected_slug))


if __name__ == "__main__":
    main()
