# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Measure current import-emission counts, without claiming a rebuild or equivalence proof.

Only counts, declared ids and hashes leave this process. Converted source and vendored native content
remain in memory. The full corpus import test independently builds, verifies and judges equivalence.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from fenolite import __version__
from fenolite.importer.emit import Options, emit
from fenolite.importer.emit.design import design_name
from fenolite.importer.provenance import Provenance
from fenolite.importer.source import read_kicad

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
OUTPUT = ROOT / "docs" / "evidence" / "import-coverage.json"
PAGE = ROOT / "docs" / "evidence" / "import-corpus.md"
PREFIX = "kicad-demo-10-0-6-pcb-"
SCHEMA = "fenolite.import-coverage.v0"
BEGIN, END = "<!-- import-coverage:begin -->", "<!-- import-coverage:end -->"
ALLOWED = {"CC-BY-SA-4.0", "CC-BY-4.0", "CC0-1.0", "CERN-OHL-S-2.0", "CERN-OHL-W-2.0", "CERN-OHL-P-2.0"}


def canonical(data: object) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def digest(data: object) -> str:
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def declared() -> list[dict[str, Any]]:
    """All declared demo boards, including heavy rows; no fetching or licensing inference."""
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["file"]
    return [
        row
        for row in rows
        if row["id"].startswith(PREFIX) and "rt0" in row.get("uses", []) and row["license"] in ALLOWED
    ]


def cached(row: Mapping[str, Any], cache: Path) -> Path:
    name = unquote(Path(urlparse(row["url"]).path).name)
    return cache / row["id"] / name


def counts(rows: object) -> list[dict[str, Any]]:
    """The complete kind/count projection; source examples or native content are never recorded."""
    if not isinstance(rows, (list, tuple)):
        raise ValueError("unexpressed rows must be a sequence")
    found: list[dict[str, Any]] = []
    for row in rows:
        item = row.as_json() if hasattr(row, "as_json") else row
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("kind"), str)
            or type(item.get("count")) is not int
        ):
            raise ValueError("an unexpressed row needs a kind and integer count")
        found.append({"kind": item["kind"], "count": item["count"]})
    return sorted(found, key=lambda row: row["kind"])


def measure(path: Path, *, ident: str, date: str) -> dict[str, Any]:
    """Run the production reader and complete emitter, including vendoring and all coverage passes."""
    datetime.date.fromisoformat(date)
    before = path.read_bytes()
    source = read_kicad(path)
    if source.major not in (9, 10):
        raise ValueError("coverage measurements require an already supported KiCad 9/10 input")
    provenance = Provenance(date=date, fenolite=__version__)
    emission = emit(source, Options(design_name(source.name), provenance, target=source.major))
    # cmd_import returns this immutable emission.unexpressed tuple after self_check, unchanged.
    result = {
        "id": ident,
        "input_sha256": hashlib.sha256(before).hexdigest(),
        "unexpressed": counts(emission.unexpressed),
        "counts": dict(emission.counts),
    }
    if path.read_bytes() != before:
        raise ValueError("measurement changed its input")
    return {**result, "measurement_sha256": digest(result)}


def shown(rows: list[dict[str, Any]]) -> str:
    return ", ".join(f"{row['kind']} {row['count']}" for row in rows) or "none"


def table(observation: Mapping[str, Any]) -> str:
    lines = [BEGIN, "| row | input SHA-256 | current emission left out (kind count) |", "|---|---|---|"]
    for row in observation["rows"]:
        lines.append(
            f"| {row['id'].removeprefix(PREFIX)} | `{row['input_sha256']}` | {shown(row['unexpressed'])} |"
        )
    return "\n".join([*lines, END])


def write(observation: Mapping[str, Any]) -> None:
    text = PAGE.read_text(encoding="utf-8")
    rendered = table(observation)
    if BEGIN in text:
        start, end = text.index(BEGIN), text.index(END) + len(END)
        text = text[:start] + rendered + text[end:]
    else:
        text += "\n\n## Current source-emission observations\n\n" + rendered + "\n"
    OUTPUT.write_text(canonical(observation), encoding="utf-8")
    PAGE.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rows = []
    for entry in declared():
        source = cached(entry, args.cache)
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            parser.error(f"missing or changed declared input {entry['id']}")
        rows.append(measure(source, ident=entry["id"], date=args.date))
        print(entry["id"] + ": measured emission", flush=True)
    observation: dict[str, Any] = {
        "schema": SCHEMA,
        "date": args.date,
        "verification": "emission-only",
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
    }
    observation["measurement_sha256"] = digest(observation)
    if args.write:
        write(observation)
    else:
        print(canonical(observation), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
