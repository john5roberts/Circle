#!/usr/bin/env python3
"""Convert ChoCo v1.0.0 Real Book JAMS into Circle's compact song-library JSON.

Designed for the Circle app. Input may be either:
  * ChoCo's v1.0.0 release ZIP, or
  * a directory containing ChoCo .jams files.

The converter scans only real-book_*.jams files, preserves Harte chord symbols,
converts symbolic measure/beat timing to quarter-note durations, carries meter
and key changes when they can be recovered, and supplies Roman-root functions
for Circle's visual display. It can optionally merge the converted songs into an
existing Circle_song_library.json.

No third-party Python packages are required.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

EVENT_FORMAT = {
    "c": '["c", duration_q, raw_harte, raw_roman, measure]',
    "n": '["n", duration_q, measure]',
    "s": '["s", at_q, label, code, measure]',
    "k": '["k", at_q, raw_key, tonic, mode, measure]',
    "m": '["m", at_q, meter, measure]',
}

PC = {
    "C": 0, "B#": 0,
    "C#": 1, "Db": 1,
    "D": 2,
    "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4,
    "E#": 5, "F": 5,
    "F#": 6, "Gb": 6,
    "G": 7,
    "G#": 8, "Ab": 8,
    "A": 9,
    "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11,
}

ROMAN_BY_SEMITONE = {
    0: "I", 1: "-II", 2: "II", 3: "-III", 4: "III", 5: "IV",
    6: "#IV", 7: "V", 8: "-VI", 9: "VI", 10: "-VII", 11: "VII",
}

CHORDISH_RE = re.compile(r"^(?:N|X|[A-G](?:#|b|-)?(?::|$))", re.I)
REALBOOK_RE = re.compile(r"(?:^|/)real-book_(\d+)\.jams$", re.I)


def compact_num(x: float) -> float | int:
    if abs(x - round(x)) < 1e-9:
        return int(round(x))
    return round(x, 6)


def recursively_find(obj: Any, keys: Sequence[str]) -> Optional[Any]:
    wanted = {k.lower() for k in keys}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in wanted and v not in (None, "", [], {}):
                return v
        for v in obj.values():
            hit = recursively_find(v, keys)
            if hit not in (None, "", [], {}):
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = recursively_find(v, keys)
            if hit not in (None, "", [], {}):
                return hit
    return None


def stringify_credit(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        vals = [stringify_credit(x) for x in v]
        return " / ".join(x for x in vals if x)
    if isinstance(v, dict):
        # Prefer common name-bearing keys before falling back to all scalar values.
        for key in ("name", "artist", "composer", "performer", "value", "label"):
            if key in v:
                s = stringify_credit(v[key])
                if s:
                    return s
        vals = [stringify_credit(x) for x in v.values()]
        vals = [x for x in vals if x]
        return " / ".join(dict.fromkeys(vals))
    return str(v).strip()


def normalize_root(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("♭", "b").replace("♯", "#")
    s = s.replace("-", "b") if len(s) <= 3 else s
    m = re.match(r"^([A-Ga-g])([#b]?)", s)
    if not m:
        return ""
    return m.group(1).upper() + m.group(2)


def parse_key(value: Any) -> Tuple[str, str, str]:
    """Return raw_key, tonic, mode."""
    if isinstance(value, dict):
        tonic = recursively_find(value, ["tonic", "root", "key"])
        mode = recursively_find(value, ["mode", "quality"])
        if tonic:
            t = normalize_root(str(tonic))
            mo = str(mode or "major").lower()
            mo = "minor" if ("min" in mo or mo in {"aeolian", "dorian", "phrygian"}) else "major"
            raw = str(recursively_find(value, ["label", "value", "raw"]) or f"{t}:{mo}")
            return raw, t or "C", mo
        value = recursively_find(value, ["value", "label", "name"]) or ""

    raw = str(value or "").strip()
    s = raw.replace("♭", "b").replace("♯", "#")
    # ChoCo/HarTe-ish: C:maj, C:min; common: Cm, C major, c
    m = re.match(r"^\s*([A-Ga-g])([#b-]?)(?::|\s*)?(.*)$", s)
    if not m:
        return raw, "C", "major"
    accidental = m.group(2)
    accidental = "b" if accidental == "-" else accidental
    tonic = m.group(1).upper() + accidental
    tail = m.group(3).strip().lower()
    is_minor = ("min" in tail or tail in {"m", "minor", "aeolian", "dorian", "phrygian"})
    # Lower-case bare tonic is conventionally minor in several harmony corpora.
    if not tail and m.group(1).islower():
        is_minor = True
    mode = "minor" if is_minor else "major"
    return raw or tonic, tonic, mode


def chord_root(raw: str) -> str:
    s = str(raw or "").strip().replace("♭", "b").replace("♯", "#")
    m = re.match(r"^([A-Ga-g])([#b-]?)", s)
    if not m:
        return ""
    accidental = "b" if m.group(2) == "-" else m.group(2)
    return m.group(1).upper() + accidental


def chord_quality(raw: str) -> str:
    s = str(raw or "")
    q = s.split(":", 1)[1] if ":" in s else "maj"
    q = q.split("/", 1)[0].lower()
    if q.startswith("min") or q.startswith("hdim") or q.startswith("dim"):
        return "minor"
    return "major"


def roman_for_chord(raw: str, tonic: str) -> str:
    root = chord_root(raw)
    if root not in PC or tonic not in PC:
        return "?"
    semitone = (PC[root] - PC[tonic]) % 12
    r = ROMAN_BY_SEMITONE[semitone]
    if chord_quality(raw) == "minor":
        r = re.sub(r"[IV]+", lambda m: m.group(0).lower(), r)
    return r


def annotation_namespace(a: Dict[str, Any]) -> str:
    return str(a.get("namespace") or a.get("annotation_type") or "").lower()


def annotation_score(a: Dict[str, Any]) -> int:
    ns = annotation_namespace(a)
    sb = json.dumps(a.get("sandbox", {}), ensure_ascii=False).lower()
    score = 0
    if "chord" in ns: score += 5
    if "harte" in ns: score += 5
    if "harte" in sb: score += 4
    data = a.get("data") or []
    vals = [str(x.get("value", "")) for x in data[:12] if isinstance(x, dict)]
    score += sum(1 for v in vals if CHORDISH_RE.match(v))
    return score


def choose_chord_annotation(jam: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    anns = [a for a in (jam.get("annotations") or []) if isinstance(a, dict)]
    candidates = []
    for a in anns:
        ns = annotation_namespace(a)
        vals = [str(x.get("value", "")) for x in (a.get("data") or [])[:16] if isinstance(x, dict)]
        if "chord" in ns or sum(bool(CHORDISH_RE.match(v)) for v in vals) >= 3:
            candidates.append(a)
    return max(candidates, key=annotation_score) if candidates else None


def key_annotations(jam: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for a in (jam.get("annotations") or []):
        if not isinstance(a, dict): continue
        ns = annotation_namespace(a)
        if ("key" in ns or "tonal" in ns) and "chord" not in ns:
            out.append(a)
    return out


def meter_annotations(jam: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for a in (jam.get("annotations") or []):
        if not isinstance(a, dict): continue
        ns = annotation_namespace(a)
        if "meter" in ns or "timesig" in ns or "time_signature" in ns or "time-signature" in ns:
            out.append(a)
    return out


def parse_meter(v: Any) -> Optional[Tuple[int, int]]:
    if isinstance(v, dict):
        num = recursively_find(v, ["numerator", "num_beats", "beats", "count"])
        den = recursively_find(v, ["denominator", "beat_units", "beat_unit", "unit"])
        try:
            if num and den: return int(float(num)), int(float(den))
        except Exception:
            pass
        v = recursively_find(v, ["value", "label", "meter", "time_signature"])
    s = str(v or "")
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if not m: return None
    num, den = int(m.group(1)), int(m.group(2))
    if num <= 0 or den <= 0: return None
    return num, den


def parse_measure_beat(v: Any) -> Optional[Tuple[int, float]]:
    """Best-effort decode of ChoCo/JAMS-X symbolic time anchors."""
    if isinstance(v, dict):
        measure = recursively_find(v, ["measure", "bar", "measure_index", "bar_index"])
        beat = recursively_find(v, ["beat", "position", "beat_position", "offset"])
        try:
            if measure is not None and beat is not None:
                return int(float(measure)), float(beat)
        except Exception:
            pass
        # Some serializers wrap the components under value/index/components.
        for key in ("value", "index", "components", "time", "start"):
            if key in v:
                hit = parse_measure_beat(v[key])
                if hit: return hit
        return None
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        try:
            return int(float(v[0])), float(v[1])
        except Exception:
            return None
    if isinstance(v, str):
        s = v.strip()
        m = re.search(r"(?:m(?:easure)?\s*)?(\d+)\s*[:;,|]\s*(?:b(?:eat)?\s*)?([0-9.]+)", s, re.I)
        if m:
            return int(m.group(1)), float(m.group(2))
        m = re.search(r"measure\s*=\s*(\d+).*?beat\s*=\s*([0-9.]+)", s, re.I)
        if m:
            return int(m.group(1)), float(m.group(2))
    return None


def numeric_duration(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)) and math.isfinite(float(v)):
        return float(v)
    if isinstance(v, dict):
        for keys in (["beats", "beat", "value", "duration", "length"],):
            hit = recursively_find(v, keys)
            if isinstance(hit, (int, float)):
                return float(hit)
            try:
                if hit is not None: return float(str(hit))
            except Exception:
                pass
    try:
        return float(v)
    except Exception:
        return None


@dataclass(order=True)
class MeterPoint:
    measure: int
    beat: float
    numerator: int
    denominator: int

    @property
    def label(self) -> str:
        return f"{self.numerator}/{self.denominator}"

    @property
    def quarter_per_beat(self) -> float:
        return 4.0 / self.denominator


def fallback_meter_from_jam(jam: Dict[str, Any]) -> Tuple[int, int]:
    for root in (jam.get("sandbox", {}), jam.get("file_metadata", {}), jam):
        v = recursively_find(root, ["time_signature", "timesig", "meter"])
        m = parse_meter(v)
        if m: return m
    return 4, 4


def build_meter_points(jam: Dict[str, Any]) -> List[MeterPoint]:
    base = fallback_meter_from_jam(jam)
    pts: List[MeterPoint] = [MeterPoint(1, 1.0, base[0], base[1])]
    for ann in meter_annotations(jam):
        for obs in ann.get("data") or []:
            if not isinstance(obs, dict): continue
            m = parse_meter(obs.get("value"))
            mb = parse_measure_beat(obs.get("time"))
            if m and mb:
                pts.append(MeterPoint(mb[0], mb[1], m[0], m[1]))
    # Also allow a list of signatures in sandboxes.
    for root in (jam.get("sandbox", {}), jam.get("file_metadata", {})):
        candidate = recursively_find(root, ["time_signatures", "meters", "meter_changes"])
        if isinstance(candidate, list):
            for item in candidate:
                if not isinstance(item, dict): continue
                m = parse_meter(item)
                mb = parse_measure_beat(item)
                if m and mb: pts.append(MeterPoint(mb[0], mb[1], m[0], m[1]))
    uniq = {(p.measure, round(p.beat, 6)): p for p in pts}
    return sorted(uniq.values())


def meter_at(points: Sequence[MeterPoint], measure: int, beat: float = 1.0) -> MeterPoint:
    keys = [(p.measure, p.beat) for p in points]
    i = bisect_right(keys, (measure, beat)) - 1
    return points[max(0, i)]


def abs_quarters(measure: int, beat: float, meters: Sequence[MeterPoint]) -> float:
    # Measures/beat positions in ChoCo v1.0 start at 1.
    measure = max(1, int(measure))
    q = 0.0
    for m in range(1, measure):
        mp = meter_at(meters, m, 1.0)
        q += mp.numerator * mp.quarter_per_beat
    mp = meter_at(meters, measure, beat)
    q += max(0.0, beat - 1.0) * mp.quarter_per_beat
    return q


def duration_quarters(obs: Dict[str, Any], mb: Optional[Tuple[int, float]], meters: Sequence[MeterPoint]) -> float:
    d = numeric_duration(obs.get("duration"))
    if d is not None and d > 0:
        if mb:
            mp = meter_at(meters, mb[0], mb[1])
            return d * mp.quarter_per_beat
        return d
    # Fallback handled later from the next chord onset.
    return 0.0


def global_key_fallback(jam: Dict[str, Any]) -> Tuple[str, str, str]:
    for root in (jam.get("sandbox", {}), jam.get("file_metadata", {}), jam):
        v = recursively_find(root, ["key", "tonality", "global_key", "globalkey"])
        if v not in (None, "", [], {}):
            return parse_key(v)
    return "C", "C", "major"


def build_key_points(jam: Dict[str, Any], meters: Sequence[MeterPoint]) -> List[Tuple[float, int, str, str, str]]:
    points: List[Tuple[float, int, str, str, str]] = []
    for ann in key_annotations(jam):
        for obs in ann.get("data") or []:
            if not isinstance(obs, dict): continue
            raw, tonic, mode = parse_key(obs.get("value"))
            mb = parse_measure_beat(obs.get("time"))
            if mb:
                q = abs_quarters(mb[0], mb[1], meters)
                points.append((q, mb[0], raw, tonic, mode))
            elif isinstance(obs.get("time"), (int, float)):
                # Score files should normally be symbolic; keep numeric values as beat offsets.
                q = float(obs["time"])
                points.append((q, 1, raw, tonic, mode))
    if not points:
        raw, tonic, mode = global_key_fallback(jam)
        points = [(0.0, 1, raw, tonic, mode)]
    points.sort(key=lambda x: x[0])
    # remove exact repetitions
    clean = []
    for p in points:
        if not clean or p[2:] != clean[-1][2:] or abs(p[0] - clean[-1][0]) > 1e-9:
            clean.append(p)
    return clean


def key_at(points: Sequence[Tuple[float, int, str, str, str]], q: float) -> Tuple[str, str, str]:
    times = [x[0] for x in points]
    i = bisect_right(times, q) - 1
    p = points[max(0, i)]
    return p[2], p[3], p[4]


def observation_onset(obs: Dict[str, Any], meters: Sequence[MeterPoint], ordinal: int) -> Tuple[float, int, Optional[Tuple[int, float]]]:
    mb = parse_measure_beat(obs.get("time"))
    if mb:
        return abs_quarters(mb[0], mb[1], meters), mb[0], mb
    t = obs.get("time")
    if isinstance(t, (int, float)):
        return float(t), 1 + ordinal, None
    return float(ordinal * 4), 1 + ordinal, None


def extract_title_artist(jam: Dict[str, Any], source_name: str) -> Tuple[str, str]:
    fm = jam.get("file_metadata") or {}
    title = recursively_find(fm, ["title", "track_title", "work_title", "name"])
    if not title:
        title = recursively_find(jam.get("sandbox", {}), ["title", "track_title", "work_title"])
    if not title:
        title = Path(source_name).stem

    # Real Book is score-based; composer is a better browser credit than performer.
    artist = recursively_find(fm, ["composer", "composers"])
    if not artist:
        artist = recursively_find(jam.get("sandbox", {}), ["composer", "composers"])
    if not artist:
        artist = recursively_find(fm, ["artist", "artists", "performer", "performers"])
    if not artist:
        artist = recursively_find(jam.get("sandbox", {}), ["artist", "artists", "performer", "performers"])
    return stringify_credit(title) or Path(source_name).stem, stringify_credit(artist) or "Unknown"


def convert_one(jam: Dict[str, Any], source_name: str, file_id: int) -> Optional[Dict[str, Any]]:
    chord_ann = choose_chord_annotation(jam)
    if not chord_ann:
        return None
    data = [x for x in (chord_ann.get("data") or []) if isinstance(x, dict)]
    if not data:
        return None

    meters = build_meter_points(jam)
    keys = build_key_points(jam, meters)
    title, artist = extract_title_artist(jam, source_name)

    chord_rows = []
    for i, obs in enumerate(data):
        raw = str(obs.get("value") or "").strip()
        q, measure, mb = observation_onset(obs, meters, i)
        dq = duration_quarters(obs, mb, meters)
        chord_rows.append([q, measure, mb, dq, raw, obs])
    chord_rows.sort(key=lambda r: r[0])

    # Fill missing/zero durations from next onset; final fallback = one measure beat.
    for i, row in enumerate(chord_rows):
        if row[3] > 0: continue
        if i + 1 < len(chord_rows) and chord_rows[i + 1][0] > row[0]:
            row[3] = chord_rows[i + 1][0] - row[0]
        else:
            mp = meter_at(meters, row[1], row[2][1] if row[2] else 1.0)
            row[3] = mp.quarter_per_beat

    initial_raw, initial_tonic, initial_mode = key_at(keys, chord_rows[0][0])
    initial_meter = meter_at(meters, chord_rows[0][1], chord_rows[0][2][1] if chord_rows[0][2] else 1.0).label

    events: List[List[Any]] = []
    # Key and meter changes are inserted at their symbolic locations.
    change_events: List[Tuple[float, int, int, List[Any]]] = []
    for p in meters:
        at = abs_quarters(p.measure, p.beat, meters)
        change_events.append((at, 0, p.measure, ["m", compact_num(at), p.label, p.measure]))
    for q, measure, raw, tonic, mode in keys:
        change_events.append((q, 1, measure, ["k", compact_num(q), raw, tonic, mode, measure]))

    # Keep only changes after zero; top-level key/meter already hold the initial state.
    changes_by_q: Dict[float, List[List[Any]]] = {}
    for q, _ord, _m, ev in sorted(change_events, key=lambda x: (x[0], x[1])):
        if q <= 1e-9: continue
        changes_by_q.setdefault(round(q, 9), []).append(ev)

    for q, measure, mb, dq, raw, _obs in chord_rows:
        for ev in changes_by_q.get(round(q, 9), []):
            events.append(ev)
        if raw.upper() in {"N", "NC", "N.C.", "X"}:
            events.append(["n", compact_num(dq), measure])
        else:
            _kr, tonic, _km = key_at(keys, q)
            roman = roman_for_chord(raw, tonic)
            events.append(["c", compact_num(dq), raw, roman, measure])

    # Meter/key events that happen between chord onsets still matter.
    chord_qs = {round(r[0], 9) for r in chord_rows}
    extras = []
    for q, evs in changes_by_q.items():
        if q not in chord_qs:
            for ev in evs: extras.append((q, ev))
    if extras:
        timed = []
        cursor = 0.0
        # Rebuild with sortable absolute-onset metadata for change events and chord events.
        for ev in events:
            if ev[0] in {"k", "m", "s"}:
                timed.append((float(ev[1]), 0, ev))
            else:
                # Approximate current onset from sequential chord durations when explicit onset isn't stored.
                timed.append((cursor, 1, ev))
                cursor += float(ev[1])
        for q, ev in extras: timed.append((q, 0, ev))
        events = [ev for _, _, ev in sorted(timed, key=lambda x: (x[0], x[1]))]

    end_q = max((r[0] + r[3] for r in chord_rows), default=0.0)
    song = {
        "id": f"choco_real_book_{file_id}",
        "artist": artist,
        "title": title,
        "key": {"tonic": initial_tonic, "mode": initial_mode, "raw": initial_raw},
        "meter": initial_meter,
        "duration_q": compact_num(end_q),
        "events": events,
        "source": "choco_real_book",
        "source_file": Path(source_name).name,
        "timing": "source_symbolic_measure_beat",
    }
    return song


def iter_jams(source: Path) -> Iterator[Tuple[str, bytes, int]]:
    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            names = []
            for n in zf.namelist():
                m = REALBOOK_RE.search(n)
                if m: names.append((int(m.group(1)), n))
            for file_id, n in sorted(names):
                yield n, zf.read(n), file_id
    elif source.is_dir():
        files = []
        for p in source.rglob("real-book_*.jams"):
            m = re.match(r"real-book_(\d+)\.jams$", p.name, re.I)
            if m: files.append((int(m.group(1)), p))
        for file_id, p in sorted(files):
            yield str(p), p.read_bytes(), file_id
    else:
        raise FileNotFoundError(f"Input is neither a ZIP nor a directory: {source}")


def load_base(path: Optional[Path]) -> List[Dict[str, Any]]:
    if not path: return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else list(data.get("songs") or [])


def output_document(songs: List[Dict[str, Any]], base_count: int, converted_count: int, skipped: List[str]) -> Dict[str, Any]:
    return {
        "format": "Circle Song Library Compact",
        "version": 2,
        "sources": {
            "cocopops_billboard": {
                "name": "CoCoPops Billboard subset (derived from McGill Billboard Project)",
                "notes": "Present when --base is supplied with Circle's existing song library."
            },
            "choco_real_book": {
                "name": "ChoCo / The Real Book",
                "choco_release": "v1.0.0",
                "license": "CC BY 4.0",
                "source_partition": "real-book",
                "timing_note": "Symbolic measure/beat timing converted to quarter-note durations for Circle."
            }
        },
        "event_format": EVENT_FORMAT,
        "build": {
            "base_songs": base_count,
            "real_book_songs": converted_count,
            "total_songs": len(songs),
            "skipped_real_book_files": len(skipped),
        },
        "songs": songs,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="ChoCo v1.0.0 ZIP or directory containing JAMS files")
    ap.add_argument("-o", "--output", type=Path, default=Path("Circle_song_library.json"))
    ap.add_argument("--base", type=Path, help="Existing Circle_song_library.json to prepend/merge")
    ap.add_argument("--limit", type=int, default=0, help="Convert only first N Real Book files (testing)")
    ap.add_argument("--report", type=Path, default=None, help="Optional text validation report")
    args = ap.parse_args(argv)

    base = load_base(args.base)
    converted: List[Dict[str, Any]] = []
    skipped: List[str] = []
    seen = 0
    for name, payload, file_id in iter_jams(args.source):
        if args.limit and seen >= args.limit: break
        seen += 1
        try:
            jam = json.loads(payload.decode("utf-8-sig"))
            song = convert_one(jam, name, file_id)
            if song: converted.append(song)
            else: skipped.append(f"{name}: no usable chord annotation")
        except Exception as e:
            skipped.append(f"{name}: {type(e).__name__}: {e}")

    all_songs = base + converted
    doc = output_document(all_songs, len(base), len(converted), skipped)
    args.output.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    report_lines = [
        "Circle ChoCo Real Book conversion report",
        "=======================================",
        f"Input: {args.source}",
        f"Base Circle songs: {len(base)}",
        f"Real Book JAMS examined: {seen}",
        f"Real Book songs converted: {len(converted)}",
        f"Skipped: {len(skipped)}",
        f"Output total: {len(all_songs)}",
        f"Output file: {args.output}",
    ]
    if skipped:
        report_lines += ["", "Skipped files:"] + skipped
    report = "\n".join(report_lines) + "\n"
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0 if converted else 2


if __name__ == "__main__":
    raise SystemExit(main())
