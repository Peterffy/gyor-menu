#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def is_wolt_hybrid(meta: dict[str, Any]) -> bool:
    if meta.get('sourceType') != 'wolt_current':
        return False
    notes = ' '.join(meta.get('notes', [])).lower()
    return 'screenshot-first' in notes or 'wolt current fallback' in notes


def source_reason(meta: dict[str, Any]) -> str:
    source_type = meta.get('sourceType')
    if source_type in {"facebook_unstructured", "manual_review_only"}:
        return "screenshotra várunk"
    if source_type == "wolt_current":
        if is_wolt_hybrid(meta):
            return "nincs használható mai Wolt menü; screenshot hasznos lenne a tisztább heti forráshoz"
        return "a live forrásban most nincs használható mai menü"
    if source_type == "website_menu_image_snapshot":
        return "image/OCR source — review vagy kézi korrekció kellhet"
    if source_type in {"website_weekly_pdf", "website_weekly_pdf_listing", "website_weekly_html"}:
        return "a forrásoldal még nem frissült vagy a collector nem talált használható mai menüt"
    return "nincs használható mai menü vagy source review kell"


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
        if re.search(r"[A-Z]{2,}[a-záéíóöőúüű]{0,2}\s+[a-záéíóöőúüű]", t):
            reasons.append(f"gyanús OCR törmelék: {label}")
        if re.search(r"[ÍÉÁŐŰÚÜÖÓ][^\s]{0,2}\s|\s[^\s]{0,2}[ÍÉÁŐŰÚÜÖÓ]", t):
            reasons.append(f"valószínű OCR zaj: {label}")
    # dedupe preserve order
    out=[]
    for r in reasons:
        if r not in out:
            out.append(r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--feed', required=True)
    ap.add_argument('--registry', required=True)
    ap.add_argument('--manifest', required=False)
    args = ap.parse_args()

    feed = load_json(args.feed)
    registry = load_json(args.registry)
    manifest = load_json(args.manifest) if args.manifest and Path(args.manifest).exists() else {}

    today = feed['today']
    restaurants = registry['restaurants']
    by_slug = {r['slug']: r for r in restaurants}
    pending_by_slug: dict[str, list[dict[str, Any]]] = {}
    for rec in manifest.get('pending', []):
        pending_by_slug.setdefault(rec.get('slug', ''), []).append(rec)

    ok = []
    suspicious = []
    unavailable = []

    for rest in feed['restaurants']:
        slug = rest['slug']
        meta = by_slug.get(slug, {})
        menus = [m for m in rest.get('menus', []) if m.get('date') == today]
        if not menus:
            reason = source_reason(meta)
            if pending_by_slug.get(slug):
                reason = 'screenshotra várunk'
            unavailable.append({
                'name': rest['name'],
                'slug': slug,
                'reason': reason,
                'sourceUrl': meta.get('sourceUrl') or rest.get('sourceUrl') or '',
            })
            continue
        menu = menus[0]
        reasons = find_suspicion_reasons(menu)
        if reasons:
            suspicious.append({
                'name': rest['name'],
                'slug': slug,
                'certainty': menu.get('certainty'),
                'reasons': reasons,
                'sourceUrl': menu.get('sourceUrl') or rest.get('sourceUrl') or meta.get('sourceUrl') or '',
            })
        else:
            ok.append({
                'name': rest['name'],
                'slug': slug,
                'certainty': menu.get('certainty'),
                'mode': 'Wolt same-day fallback' if meta.get('sourceType') == 'wolt_current' and menu.get('certainty') == 'current_snapshot' else '',
                'sourceUrl': menu.get('sourceUrl') or rest.get('sourceUrl') or meta.get('sourceUrl') or '',
            })

    lines = []
    lines.append(f"Győr Menü minőségellenőrzés — {today}")
    lines.append("")
    lines.append(f"• Rendben / vállalható: {len(ok)} étterem")
    if ok:
        lines.extend([
            f"  - {x['name']} ({x['certainty']}{'; ' + x['mode'] if x.get('mode') else ''})"
            for x in ok
        ])
    lines.append("")
    lines.append(f"• Gyanús / review ajánlott: {len(suspicious)} étterem")
    if suspicious:
        for x in suspicious:
            lines.append(f"  - {x['name']} ({x['certainty']})")
            for r in x['reasons'][:3]:
                lines.append(f"    · {r}")
    lines.append("")
    lines.append(f"• Nincs elérhető mai menü: {len(unavailable)} étterem")
    if unavailable:
        for x in unavailable:
            lines.append(f"  - {x['name']} — {x['reason']}")
            if x['reason'] == 'screenshotra várunk' and x['sourceUrl']:
                lines.append(f"    forrás: {x['sourceUrl']}")
    lines.append("")
    if unavailable:
        screenshot_waiting = [x for x in unavailable if x['reason'] == 'screenshotra várunk']
        if screenshot_waiting:
            lines.append("• Screenshotra váró helyek:")
            for x in screenshot_waiting:
                lines.append(f"  - {x['name']}: {x['sourceUrl'] or 'forráslink hiányzik'}")
            lines.append("")
    lines.append("• Rövid összkép:")
    lines.append(f"  - frissült és vállalható: {len(ok)}")
    lines.append(f"  - gyanús: {len(suspicious)}")
    lines.append(f"  - nem elérhető: {len(unavailable)}")
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
