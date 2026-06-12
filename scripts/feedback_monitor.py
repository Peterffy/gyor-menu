#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent.parent
WORKSPACE = BASE.parents[1]
STATE_PATH = WORKSPACE / "memory" / "state" / "gyor-menu-feedback-monitor.json"
SHEET_ID = "1fNro-xh51Ca3GO0wY8-EbIcKhmK6DSFkVIRyRdvuSNs"
SHEET_RANGE = "Form Responses 1!A:Z"
TZ = ZoneInfo("Europe/Budapest")
KEEP_SIGNATURES = 500


@dataclass
class FeedbackRow:
    timestamp_raw: str
    timestamp: datetime | None
    restaurant: str
    feedback_type: str
    note: str
    source_link: str
    date_raw: str
    signature: str


def run_gog() -> list[list[str]]:
    cmd = [
        "gog", "sheets", "get", SHEET_ID, SHEET_RANGE,
        "--json", "--results-only", "--no-input",
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    return data if isinstance(data, list) else []


def parse_timestamp(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=TZ)
        except ValueError:
            pass
    return None


def normalize_rows(values: list[list[str]]) -> list[FeedbackRow]:
    if not values:
        return []
    rows: list[FeedbackRow] = []
    for raw in values[1:]:
        padded = list(raw) + [""] * (6 - len(raw))
        if not any(cell.strip() for cell in padded):
            continue
        payload = {
            "timestamp": padded[0].strip(),
            "restaurant": padded[1].strip(),
            "date": padded[2].strip(),
            "feedback_type": padded[3].strip(),
            "note": padded[4].strip(),
            "source_link": padded[5].strip(),
        }
        signature = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        rows.append(FeedbackRow(
            timestamp_raw=payload["timestamp"],
            timestamp=parse_timestamp(payload["timestamp"]),
            restaurant=payload["restaurant"],
            feedback_type=payload["feedback_type"],
            note=payload["note"],
            source_link=payload["source_link"],
            date_raw=payload["date"],
            signature=signature,
        ))
    rows.sort(key=lambda r: (r.timestamp or datetime.min.replace(tzinfo=TZ), r.signature))
    return rows


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"seenSignatures": []}
    return json.loads(STATE_PATH.read_text())


def save_state(rows: list[FeedbackRow], state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    seen = list(state.get("seenSignatures", []))
    seen_set = set(seen)
    for row in rows:
        if row.signature not in seen_set:
            seen.append(row.signature)
            seen_set.add(row.signature)
    state["seenSignatures"] = seen[-KEEP_SIGNATURES:]
    state["lastSyncAt"] = datetime.now(TZ).isoformat()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def summarize_rows(rows: list[FeedbackRow], heading: str) -> str:
    by_type: dict[str, int] = {}
    restaurants: dict[str, int] = {}
    lines: list[str] = []
    for row in rows:
        by_type[row.feedback_type or "Ismeretlen"] = by_type.get(row.feedback_type or "Ismeretlen", 0) + 1
        restaurants[row.restaurant or "Ismeretlen étterem"] = restaurants.get(row.restaurant or "Ismeretlen étterem", 0) + 1
    type_part = ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))) or "nincs típus"
    restaurant_part = ", ".join(sorted(restaurants.keys())) or "ismeretlen"
    lines.append(heading)
    lines.append(f"Új bejegyzések: {len(rows)}")
    lines.append(f"Érintett éttermek: {restaurant_part}")
    lines.append(f"Típusok: {type_part}")
    lines.append("")
    lines.append("Részletek:")
    for row in rows[:8]:
        parts = [row.restaurant or "Ismeretlen étterem"]
        if row.feedback_type:
            parts.append(row.feedback_type)
        if row.date_raw:
            parts.append(f"nap: {row.date_raw}")
        if row.note:
            parts.append(f"megj.: {row.note}")
        lines.append(f"- {' | '.join(parts)}")
    if len(rows) > 8:
        lines.append(f"- … és még {len(rows) - 8} további")
    lines.append("")
    lines.append("Javasolt következő lépés: nézd át az érintett éttermek feedjét és döntsd el, hogy source-fix, review-check vagy UX/backlog tétel kell.")
    return "\n".join(lines).strip()


def mode_watch(rows: list[FeedbackRow], state: dict[str, Any]) -> str:
    seen = set(state.get("seenSignatures", []))
    new_rows = [row for row in rows if row.signature not in seen]
    save_state(rows, state)
    if not new_rows:
        return ""
    return summarize_rows(new_rows, "Győr Menü feedback figyelő — új visszajelzés érkezett")


def mode_daily(rows: list[FeedbackRow], state: dict[str, Any]) -> str:
    now = datetime.now(TZ)
    threshold = now - timedelta(hours=24)
    recent = [row for row in rows if row.timestamp and row.timestamp >= threshold]
    save_state(rows, state)
    if not recent:
        return "Győr Menü napi feedback digest\n\nAz elmúlt 24 órában nem érkezett új visszajelzés."
    return summarize_rows(recent, "Győr Menü napi feedback digest — elmúlt 24 óra")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["watch", "daily"])
    args = ap.parse_args()

    values = run_gog()
    rows = normalize_rows(values)
    state = load_state()

    if args.mode == "watch":
        out = mode_watch(rows, state)
    else:
        out = mode_daily(rows, state)

    if out:
        print(out)


if __name__ == "__main__":
    main()
