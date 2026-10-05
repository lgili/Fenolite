# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census of the cached Altium schematic corpus rows of one tag (change c0040).

    uv run python tools/altium_census.py --uses altium-sch [--json]
    uv run python tools/altium_census.py --uses altium-schlib [--json]

Reads every cached row of ``tests/corpus/manifest.toml`` that carries the tag with
``fenolite.backends.altium.read`` and prints the merged census: record ids, unknown record ids, unknown keys
per record id, key-case styles, ``WEIGHT`` agreement, owners, fractions, pin strings and tails, side streams,
stream sizes and issue codes. The output holds key names, record ids, class names, stream names, issue codes,
row ids and counts only, never a value of a file. Rows that are not cached are listed as missing.
"""

from __future__ import annotations

import argparse
import json
import os
import tomllib
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
TAGS = ("altium-sch", "altium-schlib")


def default_cache() -> Path:
    override = os.environ.get("FENOLITE_CORPUS_CACHE")
    return Path(override) if override else Path.home() / ".cache" / "fenolite" / "corpus"


def cached_rows(tag: str, cache: Path, manifest: Path = MANIFEST) -> tuple[list[tuple[str, Path]], list[str]]:
    """``(row id, cached path)`` of every row with ``tag``, and the ids of the rows not cached."""
    rows = tomllib.loads(manifest.read_text(encoding="utf-8")).get("file", [])
    found: list[tuple[str, Path]] = []
    missing: list[str] = []
    for row in rows:
        if tag not in row.get("uses", []):
            continue
        name = urllib.parse.unquote(Path(urllib.parse.urlparse(row["url"]).path).name) or row["id"]
        path = cache / row["id"] / name
        if path.is_file():
            found.append((row["id"], path))
        else:
            missing.append(row["id"])
    return found, missing


def census(tag: str, cache: Path) -> dict[str, Any]:
    """The merged census of the cached rows of ``tag`` and, per row, its issue codes and record count."""
    from fenolite.backends.altium.read import sch, schlib
    from fenolite.backends.altium.read.sch.census import merge

    rows, missing = cached_rows(tag, cache)
    items: list[dict[str, object]] = []
    per_row: dict[str, dict[str, object]] = {}
    for ident, path in rows:
        data = path.read_bytes()
        if tag == "altium-schlib":
            library = schlib.read_schlib(data)
            item = library.census()
            identity = sch.check_identity(library)
        else:
            document = sch.read_schematic(data)
            item = document.census()
            identity = sch.check_identity(document)
        items.append(item)
        per_row[ident] = {"issues": item["issues"], "identity mismatches": len(identity)}
    return {"tag": tag, "rows": [ident for ident, _ in rows], "missing": missing, "per row": per_row,
            "census": merge(items)}  # fmt: skip


def _text(result: dict[str, Any]) -> str:
    lines = [f"tag {result['tag']}: {len(result['rows'])} row(s), {len(result['missing'])} missing"]
    for key, value in result["census"].items():
        lines.append(f"{key}: {json.dumps(value, sort_keys=True)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uses", required=True, choices=TAGS, help="the corpus tag to read")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument(
        "--cache", type=Path, default=None, help="corpus cache (default: FENOLITE_CORPUS_CACHE)"
    )
    args = parser.parse_args(argv)
    result = census(args.uses, args.cache or default_cache())
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else _text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
