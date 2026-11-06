# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two Altium runs of change c0463: the hatch sample (task 3.1, S-2223) and the Repour oracle (task 4.1,
S-2224).

    uv run python tools/kit_pour_c0463.py prepare --out DIR
    uv run python tools/kit_pour_c0463.py record --saved DIR --tool "AD 26.5" --date 2026-11-07

``prepare`` writes, outside the repository:

- ``DIR/pour-hatched/``: the kit sample ``pour-hatched`` as ``fenolite kit build`` builds it (``computed/``,
  ``reference/`` and ``probes.json``);
- ``DIR/repour/<corpus id>/``: each of the eight public rows of the pour census, copied from the corpus
  cache as published;
- ``DIR/STEPS.md``, the steps of the run, and ``DIR/SHA256SUMS``.

After the run, ``record`` reads the boards Altium saved, ``DIR/pour-hatched/repoured.PcbDoc`` and
``DIR/repour/<corpus id>/repoured.PcbDoc``, and the typed ``DIR/messages.json`` when present, and writes
``tests/data/altium/kit/pour-hatched.json`` and ``tests/data/altium/kit/repour.json``
(``backends.altium.pourrecord``). The sample's record lists its poured tracks; a row's record holds
aggregates and hashes only, never a stretch of the row's geometry. No document Altium saved enters the
repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tomllib
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
SAMPLE = ROOT / "examples" / "kit" / "pour-hatched" / "design.py"
RECORDS = ROOT / "tests" / "data" / "altium" / "kit"
ROWS = tuple(f"altium-third-party-pcbdoc-{n:02d}" for n in range(1, 9))
"""The eight public rows of the pour census (``tests/corpus/test_altium_pour_census.py``)."""
SAVED = "repoured.PcbDoc"
MESSAGES = "messages.json"

STEPS = """# c0463: Altium's hatched pour (K6.12, S-2223) and the Repour oracle (S-2224)

Altium Designer 26 on the shared VM. Work on a copy of this folder. Open each document as a free document
(File » Open, no project). When Altium offers to repour on opening, answer **No**. Save only with
File » Save As under the name given, in the document's own folder. Never save a document of this folder
in place. Close each document after its save; close no document you did not open.

For each document, note in `messages.json` (the template below) every dialog that appeared and the number
of messages of each class in the Messages panel after the repour (`Error`, `Warning`, ...).

## 1. pour-hatched (K6.12)

1. Open `pour-hatched/reference/pour-hatched.PcbDoc`.
2. Tools » Polygon Pours » Repour All; confirm every polygon.
3. File » Save As `pour-hatched/repoured.PcbDoc`.

## 2. The eight public rows

For each folder `repour/<corpus id>/`, in order:

1. Open the one `.PcbDoc` of the folder.
2. Tools » Polygon Pours » Repour All; confirm every polygon.
3. File » Save As `repour/<corpus id>/repoured.PcbDoc`.

## messages.json

```json
{
  "pour-hatched": {"dialogs": [], "messages": {}},
  "altium-third-party-pcbdoc-01": {"dialogs": [], "messages": {}}
}
```

One key per document (`pour-hatched` and each corpus id). `dialogs` lists the title of each dialog in
order; `messages` maps a message class to its count. Do not copy message texts: they name the row's nets.

Then run, on the Mac, from the Fenolite checkout:

```
uv run python tools/kit_pour_c0463.py record --saved <this folder> \\
    --tool "AD <major>.<minor>" --date <YYYY-MM-DD>
```
"""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cache() -> Path:
    override = os.environ.get("FENOLITE_CORPUS_CACHE")
    return Path(override) if override else Path.home() / ".cache" / "fenolite" / "corpus"


def _rows() -> dict[str, Path]:
    """Each row of ``ROWS``, its cached file; ``SystemExit`` names a row that is not cached."""
    found: dict[str, Path] = {}
    for row in tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", []):
        if row["id"] in ROWS:
            name = urllib.parse.unquote(Path(urllib.parse.urlparse(row["url"]).path).name) or row["id"]
            found[row["id"]] = _cache() / row["id"] / name
    missing = [row for row in ROWS if row not in found or not found[row].is_file()]
    if missing:
        raise SystemExit(f"not cached: {', '.join(missing)} (uv run python tools/corpus_fetch.py)")
    return found


def prepare(out: Path) -> None:
    from fenolite.cli._kit import build_sample

    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    sample = build_sample(SAMPLE)
    for key, data in sample.files.items():
        target = out / "pour-hatched" / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for row, path in _rows().items():
        target = out / "repour" / row / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (out / "STEPS.md").write_text(STEPS, encoding="utf-8")
    sums = [f"{_sha(p)}  {p.relative_to(out).as_posix()}" for p in sorted(out.rglob("*")) if p.is_file()]
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"out": out.name, "files": len(sums)}))


def _messages(saved: Path) -> dict[str, object]:
    path = saved / MESSAGES
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def record(saved: Path, tool: str, date: str, out: Path) -> None:
    from fenolite.backends.altium.pourrecord import document_record, record_text

    messages = _messages(saved)
    reference = saved / "pour-hatched" / "reference" / "pour-hatched.PcbDoc"
    hatched = document_record(saved / "pour-hatched" / SAVED, detail=True)
    hatched["source_sha256"] = _sha(reference)
    hatched["messages"] = messages.get("pour-hatched", {})
    out.mkdir(parents=True, exist_ok=True)
    sample = {"sample": "examples/kit/pour-hatched/design.py", "sample_sha256": _sha(SAMPLE)}
    text = record_text("K6.12", tool, date, {"pour-hatched": hatched}, **sample)
    (out / "pour-hatched.json").write_text(text, encoding="utf-8")
    rows: dict[str, dict[str, object]] = {}
    for row in ROWS:
        folder = saved / "repour" / row
        if not (folder / SAVED).is_file():
            continue
        sources = [p for p in folder.glob("*.PcbDoc") if p.name != SAVED]
        entry = document_record(folder / SAVED)
        entry["file"] = SAVED
        entry["source_sha256"] = _sha(sources[0]) if len(sources) == 1 else ""
        entry["messages"] = messages.get(row, {})
        rows[row] = entry
    (out / "repour.json").write_text(record_text("repour", tool, date, rows), encoding="utf-8")
    print(json.dumps({"pour-hatched": len(hatched["polygons"]), "rows": sorted(rows)}))  # type: ignore[arg-type]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    made = sub.add_parser("prepare")
    made.add_argument("--out", type=Path, required=True)
    taken = sub.add_parser("record")
    taken.add_argument("--saved", type=Path, required=True)
    taken.add_argument("--tool", required=True)
    taken.add_argument("--date", required=True)
    taken.add_argument("--out", type=Path, default=RECORDS)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        prepare(args.out)
    else:
        record(args.saved, args.tool, args.date, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
