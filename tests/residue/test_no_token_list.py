# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""No list of private identifiers is committed, in clear or hashed form.

The one exception is the public KiCad format inventory ``src/fenolite/backends/kicad/data/tokens.toml``
(change c0007), whose content is checked: only the inventory's own keys, and rows citing registered
public sources.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from pathlib import Path

import _scanmod

scan = _scanmod.load()
ALLOWED_IN_RESIDUE = {"README.md", "patterns.regex", "blobs.sha256", "scope.toml", "scan.py"}
INVENTORY = "src/fenolite/backends/kicad/data/tokens.toml"
INVENTORY_KEYS = {"format", "collected_at", "token", "form", "note"}
LISTY_NAME = re.compile(
    r"(?i)(token|denylist|blocklist|deny-list|block-list)[^/]*\.(txt|sha256|lst|list|json|toml|csv)$"
)


def offending(files: list[str]) -> list[str]:
    bad = []
    for rel in files:
        parts = Path(rel).parts
        if parts[:2] == ("tools", "residue") and len(parts) == 3 and parts[2] not in ALLOWED_IN_RESIDUE:
            bad.append(rel)
        elif LISTY_NAME.search(rel) and rel != INVENTORY:
            bad.append(rel)
    return bad


def inventory_problems(root: Path) -> list[str]:
    """The allowed inventory must hold only the inventory keys and rows citing registered sources."""
    path = root / INVENTORY
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [f"{INVENTORY}: not valid TOML ({exc})"]
    problems = [f"{INVENTORY}: foreign top-level key {key!r}" for key in sorted(set(data) - INVENTORY_KEYS)]
    if data.get("format") != 1:
        problems.append(f"{INVENTORY}: format must be 1")
    registered = set(
        re.findall(r"^\| (S-\d{4}) ", (root / "docs/evidence/sources.md").read_text(encoding="utf-8"), re.M)
    )
    for table in ("token", "form"):
        for row in data.get(table, []):
            cited = [s for s in row.get("sources", []) if s in registered]
            if not cited:
                problems.append(f"{INVENTORY}: row {row.get('id', '?')} cites no registered source")
    return problems


def test_no_token_list_in_repository() -> None:
    bad = offending(scan.tree_files(scan.REPO))
    assert not bad, "token lists must never be committed:\n" + "\n".join(bad)


def test_detector() -> None:
    assert offending(["tools/residue/tokens.sha256", "docs/private-tokens.txt", "tools/residue/scan.py"]) == [
        "tools/residue/tokens.sha256",
        "docs/private-tokens.txt",
    ]


def test_inventory_is_allowed_and_checked() -> None:
    assert INVENTORY not in offending(scan.tree_files(scan.REPO))
    problems = inventory_problems(scan.REPO)
    assert not problems, "\n".join(problems)


def test_other_token_lists_still_fail() -> None:
    assert offending(
        ["tools/residue/tokens.sha256", "src/fenolite/backends/kicad/data/tokens.txt", INVENTORY]
    ) == [
        "tools/residue/tokens.sha256",
        "src/fenolite/backends/kicad/data/tokens.txt",
    ]


def test_inventory_with_foreign_content_fails(tmp_path: Path) -> None:
    (tmp_path / "docs" / "evidence").mkdir(parents=True)
    shutil.copy(scan.REPO / "docs/evidence/sources.md", tmp_path / "docs/evidence/sources.md")
    target = tmp_path / INVENTORY
    target.parent.mkdir(parents=True)
    target.write_text((scan.REPO / INVENTORY).read_text(encoding="utf-8") + '\n[[denylist]]\nname = "x"\n')
    problems = inventory_problems(tmp_path)
    assert any("denylist" in p and INVENTORY in p for p in problems), problems


def test_inventory_row_without_registered_source_fails(tmp_path: Path) -> None:
    (tmp_path / "docs" / "evidence").mkdir(parents=True)
    (tmp_path / "docs/evidence/sources.md").write_text("| S-0001 | x |\n")
    target = tmp_path / INVENTORY
    target.parent.mkdir(parents=True)
    target.write_text('format = 1\n[[token]]\nid = "x"\nsources = ["S-9999"]\n')
    assert inventory_problems(tmp_path) == [f"{INVENTORY}: row x cites no registered source"]
