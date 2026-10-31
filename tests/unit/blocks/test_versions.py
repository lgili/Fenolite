# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The version rules of shipped blocks (capability block-library, "Shipped block versions" and
"Replacements of blocks"; change c0268). The committed ``VERSIONS.toml`` holds every shipped block, and the
rules are proved with the authored blocks of ``tests/data/blocks/versions/``."""

from __future__ import annotations

import importlib.util
import runpy
from pathlib import Path

from fenolite.dsl import describe
from fenolite.dsl.block import BlockDef
from fenolite.dsl.record import (
    BlockRecord,
    VersionRow,
    read_versions,
    version_problems,
    version_row,
    versions_text,
)

ROOT = Path(__file__).resolve().parents[3]
FILE = ROOT / "src" / "fenolite" / "blocks" / "VERSIONS.toml"
DATA = ROOT / "tests" / "data" / "blocks"
TOOL = runpy.run_path(str(ROOT / "tools" / "blocks" / "versions.py"))


def record(name: str, folder: Path = DATA / "versions", attribute: str = "div") -> BlockRecord:
    spec = importlib.util.spec_from_file_location(
        f"_c0268_versions_{folder.name}_{name}", folder / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    exec(compile(Path(spec.origin).read_bytes(), spec.origin, "exec"), module.__dict__)
    found = getattr(module, attribute)
    assert isinstance(found, BlockDef)
    return describe(found)


def committed() -> tuple[VersionRow, ...]:
    return (version_row(record("base")),)


def test_committed_file_holds_every_shipped_block() -> None:
    rows = read_versions(FILE.read_text(encoding="utf-8"))
    assert version_problems(TOOL["shipped_records"](), rows) == []
    assert FILE.read_text(encoding="utf-8") == versions_text(rows)


def test_unchanged_block_passes() -> None:
    assert version_problems([record("base")], committed()) == []


def test_port_renamed_under_an_id() -> None:
    """Scenario "Port renamed under an id"."""
    (problem,) = version_problems([record("renamed")], committed())
    assert problem.startswith("Acme:div:") and "interface change needs a new id with replaces" in problem


def test_default_changed_without_a_minor_step() -> None:
    """Scenario "Default changed without a minor step"."""
    (problem,) = version_problems([record("default")], committed())
    assert problem.startswith("Acme:div:") and "MINOR version above 1.0.0" in problem


def test_doc_changed_without_a_patch_step() -> None:
    (problem,) = version_problems([record("docs")], committed())
    assert "PATCH version above 1.0.0" in problem


def test_removed_id_is_not_reused() -> None:
    (problem,) = version_problems([record("base")], (VersionRow("Acme:div", removed=True),))
    assert "removed and must not be used again" in problem


def test_missing_and_unshipped_rows() -> None:
    assert "not in VERSIONS.toml" in version_problems([record("base")], ())[0]
    assert "not shipped" in version_problems([], committed())[0]


def test_replacement_without_deprecation() -> None:
    old, new = record("replace", DATA, "div"), record("replace", DATA, "div2")
    rows = (version_row(old), version_row(new))
    (problem,) = version_problems([old, new], rows)
    assert "Acme:div2 replaces Acme:div" in problem and "deprecated.by" in problem


def test_rows_round_trip() -> None:
    rows = (*committed(), VersionRow("Acme:gone", removed=True))
    assert read_versions(versions_text(rows)) == tuple(sorted(rows, key=lambda r: r.id))
    assert TOOL["updated"]([record("base")], (VersionRow("Acme:gone", "1.0.0", "a", "b", "c"),)) == list(
        sorted(rows, key=lambda r: r.id)
    )
