#!/usr/bin/env python3
"""
Build a Circle library containing the New Real Book, Vol. 1 tunes that are
available in ChoCo's v1.0.0 Real Book partition.

Inputs:
  1) ChoCo v1.0.0 ZIP or extracted directory
  2) Existing Circle_song_library.json
  3) New_Real_Book_Vol1_titles.json
  4) convert_choco_realbook_to_circle.py in the same directory

Behavior:
  - tags existing Circle matches with tags.books
  - converts ChoCo Real Book JAMS
  - matches only exact normalized titles / curated aliases from the manifest
  - avoids adding a second copy when Circle already has that composition
  - if ChoCo contains multiple candidates for the same title, keeps the most
    complete candidate (most chord events, then longest duration)
  - assigns valid Circle jazz accompaniment defaults to newly added songs
  - preserves source provenance independently of book membership
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


BOOK = "The New Real Book, Vol. 1"


def load_converter(path: Path):
    spec = importlib.util.spec_from_file_location("circle_choco_converter", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load converter: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def norm_title(value: str) -> str:
    s = unicodedata.normalize("NFKD", str(value or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("&", " and ")
    s = s.lower()
    # punctuation is not meaningful for matching, but words inside parentheses are
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def add_book_tag(song: Dict[str, Any]) -> None:
    tags = song.setdefault("tags", {})
    books = tags.setdefault("books", [])
    if BOOK not in books:
        books.append(BOOK)


def chord_event_count(song: Dict[str, Any]) -> int:
    return sum(1 for e in song.get("events", []) if isinstance(e, list) and e and e[0] == "c")


# These names are already present in Circle's accompaniment menus.
FOUR_FOUR_COMBOS = [
    {"style": "jazz", "guitar": "Swing comp",        "bass": "Walking chord tones", "drums": "Swing comp"},
    {"style": "jazz", "guitar": "Jazz ballad",       "bass": "Jazz two-feel",        "drums": "Jazz ballad"},
    {"style": "jazz", "guitar": "Jazz chord pocket", "bass": "Walking chord tones", "drums": "Swing sparse"},
    {"style": "jazz", "guitar": "Shell comp feel",   "bass": "Walking chord tones", "drums": "Four to the bar"},
    {"style": "jazz", "guitar": "Four-to-bar comp",  "bass": "Walking chord tones", "drums": "Four to the bar"},
    {"style": "jazz", "guitar": "Swing arp",         "bass": "Jazz two-feel",        "drums": "Swing push"},
]
METER_COMBOS = {
    "3/4":  {"style": "jazz", "guitar": "Sparse jazz waltz", "bass": "Sparse root–third",        "drums": "Brush waltz"},
    "6/8":  {"style": "jazz", "guitar": "6/8 blues comp",    "bass": "6/8 blues walk",            "drums": "6/8 blues"},
    "12/8": {"style": "jazz", "guitar": "12/8 blues comp",   "bass": "12/8 chord-tone walk",      "drums": "12/8 blues"},
}


def accompaniment_for(song: Dict[str, Any], ordinal: int) -> Dict[str, str] | None:
    meter = str(song.get("meter") or "4/4")
    if meter == "4/4":
        return dict(FOUR_FOUR_COMBOS[ordinal % len(FOUR_FOUR_COMBOS)])
    combo = METER_COMBOS.get(meter)
    return dict(combo) if combo else None


def build_alias_map(manifest: Dict[str, Any]) -> Tuple[Dict[str, str], List[str]]:
    titles = list(manifest.get("titles") or [])
    lookup: Dict[str, str] = {}
    for title in titles:
        n = norm_title(title)
        if n in lookup and lookup[n] != title:
            raise ValueError(f"Normalized title collision: {lookup[n]!r} / {title!r}")
        lookup[n] = title

    for canonical, aliases in (manifest.get("aliases") or {}).items():
        if canonical not in titles:
            raise ValueError(f"Alias canonical title is not in title list: {canonical}")
        for alias in aliases:
            n = norm_title(alias)
            if n in lookup and lookup[n] != canonical:
                raise ValueError(f"Alias collision: {alias!r} -> {canonical!r}, already {lookup[n]!r}")
            lookup[n] = canonical
    return lookup, titles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("choco_source", type=Path, help="ChoCo v1.0.0 ZIP or extracted folder")
    ap.add_argument("--base", type=Path, default=Path("Circle_song_library.json"))
    ap.add_argument("--manifest", type=Path, default=Path("New_Real_Book_Vol1_titles.json"))
    ap.add_argument("--converter", type=Path, default=Path("convert_choco_realbook_to_circle.py"))
    ap.add_argument("--output", type=Path, default=Path("Circle_song_library_NRB1_expanded.json"))
    ap.add_argument("--report", type=Path, default=Path("New_Real_Book_Vol1_build_report.txt"))
    args = ap.parse_args()

    base_doc = json.loads(args.base.read_text(encoding="utf-8"))
    base_songs = list(base_doc.get("songs") or [])
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    lookup, canonical_titles = build_alias_map(manifest)
    converter = load_converter(args.converter)

    # First tag every existing Circle song that matches the book.
    existing_by_canonical: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for song in base_songs:
        canonical = lookup.get(norm_title(song.get("title", "")))
        if canonical:
            add_book_tag(song)
            existing_by_canonical[canonical].append(song)

    # Convert ChoCo Real Book songs and retain only titles in this book.
    candidates: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    examined = converted_ok = 0
    conversion_errors: List[str] = []
    for name, payload, file_id in converter.iter_jams(args.choco_source):
        examined += 1
        try:
            jam = json.loads(payload.decode("utf-8-sig"))
            song = converter.convert_one(jam, name, file_id)
            if not song:
                continue
            converted_ok += 1
            canonical = lookup.get(norm_title(song.get("title", "")))
            if canonical:
                candidates[canonical].append(song)
        except Exception as exc:
            conversion_errors.append(f"{name}: {type(exc).__name__}: {exc}")

    additions: List[Dict[str, Any]] = []
    duplicate_candidates: List[str] = []
    available_existing: List[str] = []
    unavailable: List[str] = []
    added_titles: List[str] = []

    for idx, canonical in enumerate(canonical_titles):
        if existing_by_canonical.get(canonical):
            available_existing.append(canonical)
            continue

        pool = candidates.get(canonical, [])
        if not pool:
            unavailable.append(canonical)
            continue

        pool.sort(key=lambda s: (chord_event_count(s), float(s.get("duration_q") or 0)), reverse=True)
        chosen = pool[0]
        if len(pool) > 1:
            duplicate_candidates.append(
                f"{canonical}: selected {chosen.get('source_file')} from {len(pool)} ChoCo candidates"
            )

        # Use the book's canonical spelling for the Circle title, but retain source_file.
        chosen["title"] = canonical
        add_book_tag(chosen)
        accomp = accompaniment_for(chosen, len(additions))
        if accomp:
            chosen["accompaniment"] = accomp
        else:
            chosen["accompaniment_note"] = (
                f"No native Circle accompaniment assignment for source meter {chosen.get('meter')}"
            )
        additions.append(chosen)
        added_titles.append(canonical)

    final_songs = base_songs + additions

    # Update document metadata without changing provenance of pre-existing songs.
    base_doc["version"] = max(int(base_doc.get("version") or 1), 4)
    base_doc["songs"] = final_songs
    base_doc.setdefault("tag_schema", {})["books"] = (
        "Published songbooks/collections in which the composition appears; "
        "independent of harmonic-data source."
    )

    sources = base_doc.setdefault("sources", {})
    rb = sources.setdefault("choco_real_book", {})
    rb.update({
        "name": "ChoCo / The Real Book",
        "choco_release": "v1.0.0",
        "license": "CC BY 4.0",
        "source_partition": "real-book",
    })
    rb["songs"] = sum(1 for s in final_songs if s.get("source") == "choco_real_book")

    build = base_doc.setdefault("build", {})
    build["total_songs"] = len(final_songs)
    build["real_book_songs"] = rb["songs"]
    build.setdefault("book_tags", {})[BOOK] = sum(
        1 for s in final_songs if BOOK in ((s.get("tags") or {}).get("books") or [])
    )
    build["new_real_book_vol1_added_this_build"] = len(additions)

    args.output.write_text(
        json.dumps(base_doc, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    report = [
        "Circle — New Real Book, Vol. 1 selective expansion",
        "====================================================",
        f"Book titles in manifest: {len(canonical_titles)}",
        f"Base Circle songs: {len(base_songs)}",
        f"Existing Circle matches tagged: {len(available_existing)}",
        f"ChoCo Real Book JAMS examined: {examined}",
        f"ChoCo JAMS successfully converted: {converted_ok}",
        f"New book songs added from ChoCo: {len(additions)}",
        f"Book titles represented after build: {len(available_existing) + len(additions)}",
        f"Book titles not available/matched in ChoCo: {len(unavailable)}",
        f"Final Circle song count: {len(final_songs)}",
        "",
        "EXISTING CIRCLE MATCHES",
        "-----------------------",
        *available_existing,
        "",
        "ADDED FROM CHOCO",
        "----------------",
        *added_titles,
        "",
        "NOT MATCHED / NOT AVAILABLE",
        "---------------------------",
        *unavailable,
    ]
    if duplicate_candidates:
        report += ["", "MULTIPLE CHOCO CANDIDATES", "-------------------------", *duplicate_candidates]
    if conversion_errors:
        report += ["", "CONVERSION ERRORS", "-----------------", *conversion_errors]

    args.report.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report[:9]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
