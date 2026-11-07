# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The versions of the shipped blocks (change c0268, ``docs/blocks.md``, "Version rules").

    uv run python tools/blocks/versions.py            # list what breaks the version rules
    uv run python tools/blocks/versions.py --update   # rewrite VERSIONS.toml after a reviewed change

``src/fenolite/blocks/VERSIONS.toml`` records, per shipped block id, its version and three digests (record,
definition, interface). ``--update`` refuses to write while a block breaks a rule other than the file
being stale (an interface changed under an id, a changed definition without a MINOR version, a changed
record without a PATCH version, a removed id used again, a replacement without a deprecation); it keeps
removed ids, marked ``removed = true``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fenolite.cli.blocksrc import find_blocks
from fenolite.dsl.record import (
    UPDATE_HINT,
    VERSIONS_FILE,
    BlockRecord,
    VersionRow,
    read_versions,
    version_problems,
    version_row,
    versions_text,
)

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "src" / "fenolite" / "blocks" / VERSIONS_FILE


def shipped_records() -> list[BlockRecord]:
    """The records of the shipped blocks (the catalog source ``builtin``)."""
    return [entry.record for entry in find_blocks() if entry.source == "builtin"]


def updated(records: list[BlockRecord], rows: tuple[VersionRow, ...]) -> list[VersionRow]:
    """``rows`` rewritten for ``records``: a removed id is kept and marked."""
    current = {row.id: row for row in (version_row(record) for record in records)}
    for row in rows:
        if row.id not in current:
            current[row.id] = VersionRow(row.id, removed=True)
    return sorted(current.values(), key=lambda row: row.id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--update", action="store_true", help="rewrite VERSIONS.toml")
    args = parser.parse_args(argv)
    records = shipped_records()
    rows = read_versions(FILE.read_text(encoding="utf-8")) if FILE.is_file() else ()
    problems = version_problems(records, rows)
    blocking = [
        problem for problem in problems if UPDATE_HINT not in problem and "not shipped" not in problem
    ]
    if blocking or not args.update:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    FILE.write_text(versions_text(updated(records, rows)), encoding="utf-8", newline="\n")
    print(f"wrote {FILE.relative_to(ROOT)} ({len(records)} blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
