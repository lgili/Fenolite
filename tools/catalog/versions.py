# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The versions of the shipped library records (change c0259, ``docs/library-records.md``, "Versions").

    uv run python tools/catalog/versions.py            # list what breaks the version rules
    uv run python tools/catalog/versions.py --update   # rewrite VERSIONS.toml after a reviewed change

``src/fenolite/catalog/data/VERSIONS.toml`` records, per shipped id, its kind, version and three digests
(record, output, interface). ``--update`` refuses to write while a record breaks a rule other than the file
being stale (an interface changed under an id, a changed definition without a MINOR version, a changed
record without a new version, a removed id used again); it keeps removed ids and raises the catalog
version when any entry changes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fenolite.catalog import records

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "src" / "fenolite" / "catalog" / "data" / records.VERSIONS_FILE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update", action="store_true", help="rewrite VERSIONS.toml")
    args = parser.parse_args(argv)
    tree = records.load_tree(FILE.parent, label="fenolite/catalog/data/", shipped=True)
    versions = (
        records.read_versions(FILE.read_text(encoding="utf-8"))
        if FILE.is_file()
        else records.Versions("1.0.0", "", ())
    )
    problems = records.version_problems(tree.records, versions)
    blocking = [problem for problem in problems if records.UPDATE_HINT not in problem]
    if blocking or not args.update:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    updated = records.updated_versions(tree.records, versions)
    FILE.write_text(records.versions_text(updated), encoding="utf-8", newline="\n")
    print(
        f"wrote {FILE.relative_to(ROOT)} (catalog {updated.catalog_version}, {len(updated.entries)} entries)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
