# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent c0266 library subset, with authored geometry and malformed inputs only."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from fenolite.backends.librepcb.reader import CC0_SHA256, read_library
from fenolite.backends.librepcb.sexpr import Invalid, parse, quantity
from fenolite.library.licences import normalised_digest

DEMO = Path(__file__).resolve().parents[3] / "data/librepcb/demo"


def test_reader_relationships() -> None:
    found = read_library(DEMO)
    assert [e.kind for e in found.elements] == ["symbol", "package", "component", "device"]
    assert not found.skipped
    assert found.of_kind("device")[0].node.text("component") == found.of_kind("component")[0].uuid
    assert normalised_digest((DEMO / "LICENSE.txt").read_bytes()) != CC0_SHA256
    assert "Authored for Fenolite" in (DEMO / "LICENSE.txt").read_text()


def test_authored_licence_placeholder_registered() -> None:
    manifest = tomllib.loads((DEMO.parents[1] / "MANIFEST.toml").read_text())
    row = next(row for row in manifest["file"] if row["path"] == "tests/data/librepcb/demo/LICENSE.txt")
    assert row["origin"] == "authored" and "placeholder" in row["notes"]
    assert "not public legal text" in row["notes"]


def test_element_version_skips_one_uuid(tmp_path: Path) -> None:
    shutil.copytree(DEMO, tmp_path, dirs_exist_ok=True)
    marker = next((tmp_path / "pkg").rglob(".librepcb-pkg"))
    marker.write_text("999\n")
    found = read_library(tmp_path)
    assert len(found.elements) == 3
    assert found.skipped[0].uuid == marker.parent.name and "format" in found.skipped[0].reason


def test_root_version_refused(tmp_path: Path) -> None:
    (tmp_path / ".librepcb-lib").write_text("999\n")
    with pytest.raises(Invalid, match="library format"):
        read_library(tmp_path)


def test_own_tokenizer_escaped_strings_and_exact_units() -> None:
    node = parse('(root (name "A\\nB\\"C\\\\D") (position -1.234567 2))')
    assert node.text("name") == 'A\nB"C\\D'
    assert quantity("-1.234567") == -1_234_567
    assert quantity("0.000001", angle=True) == 1


@pytest.mark.parametrize(
    "text",
    [
        "(a",
        "(a))",
        "(a) (b)",
        '(a "x\\q")',
        "(a ; comment)",
        '(a "unterminated)',
        "atom",
        "(" * 65 + "a" + ")" * 65,
    ],
)
def test_tokenizer_fails_closed(text: str) -> None:
    with pytest.raises(Invalid):
        parse(text)


@pytest.mark.parametrize("text", ["0.0000001", "NaN", "Infinity", "bad", "1e100"])
def test_no_rounding_or_floats(text: str) -> None:
    with pytest.raises(Invalid):
        quantity(text)


def test_symlink_is_not_read(tmp_path: Path) -> None:
    shutil.copytree(DEMO, tmp_path, dirs_exist_ok=True)
    path = next((tmp_path / "sym").rglob("symbol.lp"))
    path.unlink()
    path.symlink_to(next((DEMO / "sym").rglob("symbol.lp")))
    assert "symlink" in read_library(tmp_path).skipped[0].reason
