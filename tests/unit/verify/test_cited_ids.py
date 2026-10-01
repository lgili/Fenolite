# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hypothesis ids cited in text, and ids proposed by active changes (capability verification-evidence)."""

from __future__ import annotations

from pathlib import Path

from fenolite.verify import cited_ids, proposed_ids


def _tree(root: Path, files: dict[str, str | bytes]) -> Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return root


def test_ids_and_paths(tmp_path: Path) -> None:
    _tree(
        tmp_path, {"docs/a.md": "H-K-UNIT and H-G-ANGLE", "docs/sub/b.md": "again H-K-UNIT", "src/c.py": "x"}
    )
    found = cited_ids(["docs", "src"], base=tmp_path)
    assert found == {"H-G-ANGLE": ("docs/a.md",), "H-K-UNIT": ("docs/a.md", "docs/sub/b.md")}


def test_family_references(tmp_path: Path) -> None:
    text = "H-K-FMT-* and grep -c '^| H-K-LIB-' and H-K-00…H-K-03 and `H-K-KRT-*`"
    _tree(tmp_path, {"docs/x.md": text})
    assert set(cited_ids(["docs"], base=tmp_path)) == {
        "H-K-FMT-*",
        "H-K-LIB-*",
        "H-K-00-*",
        "H-K-03",
        "H-K-KRT-*",
    }


def test_skipped_files(tmp_path: Path) -> None:
    _tree(
        tmp_path,
        {
            "docs/.hidden.md": "H-K-UNIT",
            "docs/.cache/a.md": "H-K-UNIT",
            "docs/__pycache__/a.pyc": "H-K-UNIT",
            "docs/binary.bin": b"\xff\xfeH-K-UNIT",
            "docs/old/a.md": "H-K-UNIT",
            "docs/kept.md": "H-G-ANGLE",
        },
    )
    assert cited_ids(["docs"], base=tmp_path, exclude=["docs/old"]) == {"H-G-ANGLE": ("docs/kept.md",)}


def test_a_root_that_is_a_file(tmp_path: Path) -> None:
    _tree(tmp_path, {"CHANGELOG.md": "adds H-K-UNIT"})
    assert cited_ids([tmp_path / "CHANGELOG.md"], base=tmp_path) == {"H-K-UNIT": ("CHANGELOG.md",)}


def _design(*tables: str, after: str = "") -> str:
    return (
        "## Context\n\n| id | x |\n|---|---|\n| H-K-UNIT | listed elsewhere |\n\n"
        "## Hypotheses registered by this change\n\n" + "\n".join(tables) + after
    )


def test_proposed_ids(tmp_path: Path) -> None:
    first = (
        "| id | statement |\n|---|---|\n| H-K-SEXPR-LEX-10 | a |\n| `H-K-SEXPR-LEX-9` | b |\n| note | c |\n"
    )
    second = "| id | role |\n|---|---|\n| H-K-SEXPR-STRICT (c0006) | settles |\n"
    after = (
        "\n## Evidence level per behaviour (before merge)\n\n| behaviour |\n|---|\n| H-K-SEXPR-ESCAPES |\n"
    )
    _tree(
        tmp_path,
        {
            "openspec/changes/c0099-x/design.md": _design(first, second, after=after),
            "openspec/changes/archive/2026-01-01-c0097-z/design.md": _design("| H-K-SEXPR-NUM-READ | a |\n"),
        },
    )
    assert proposed_ids(tmp_path / "openspec" / "changes") == {
        "H-K-SEXPR-LEX-10",
        "H-K-SEXPR-LEX-9",
        "H-K-SEXPR-STRICT",
    }


def test_no_changes_folder(tmp_path: Path) -> None:
    assert proposed_ids(tmp_path / "openspec" / "changes") == frozenset()
