# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Residue check of the shipped sheet examples (capability sheet-templates, "Shipped sheet examples",
scenario "Residue check"; change c0012). An allowlist: every number cites ``fenolite-choice`` or one of the
registered public sources S-0077, S-0078 and S-0079; every text is a neutral token, a label listed in
``docs/formats/sheets.md`` or a one-character zone label; the written ``.kicad_wks`` has no residue. No
test of this change reads a kicad-templates sheet or KiCad's default sheet."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import _scanmod
import pytest

from fenolite.backends.kicad.wks import write_drawing_sheet
from fenolite.model.presentation import SheetText, split_tokens
from fenolite.templates import EXAMPLES, build_sheet, example_path, load_spec

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_SOURCES = frozenset({"S-0077", "S-0078", "S-0079"})
scan = _scanmod.load()


def registered() -> set[str]:
    text = (ROOT / "docs" / "evidence" / "sources.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| (S-\d{4}) \|", text, flags=re.MULTILINE))


def listed_labels() -> set[str]:
    """The ``label`` column of the "Title-block labels" table of ``sheets.md``."""
    text = (ROOT / "docs" / "formats" / "sheets.md").read_text(encoding="utf-8")
    section = text.split("## Title-block labels", 1)[1]
    rows = [line for line in section.splitlines() if line.startswith("| ") and not line.startswith("| label")]
    return {line.split("|")[1].strip() for line in rows if not set(line) <= {"|", "-", " "}}


def provenance_problems(data: dict[str, Any]) -> list[str]:
    values: dict[str, Any] = data.get("provenance", {}).get("values", {})
    known = registered()
    problems = []
    for path, origin in values.items():
        if origin == "fenolite-choice":
            continue
        if origin not in ALLOWED_SOURCES:
            problems.append(f"{path} cites {origin!r}, which is not an allowed source")
        elif origin not in known:
            problems.append(f"{path} cites {origin!r}, which is not registered")
    return problems


def text_problems(texts: list[str]) -> list[str]:
    labels = listed_labels()
    problems = []
    for text in texts:
        parts = split_tokens(text)
        literal = "".join(p for p in parts if isinstance(p, str))
        if not literal:
            continue  # tokens only
        if text in labels or (len(text) == 1 and text.isalnum()):
            continue
        problems.append(f"text {text!r} is not a token, a listed label or a zone label")
    return problems


def sheet_texts(source: str, name: str) -> list[str]:
    spec = load_spec(source, file=name)
    return [i.text for i in build_sheet(spec).items if isinstance(i, SheetText)]


@pytest.mark.parametrize("name", EXAMPLES)
def test_residue_check(name: str) -> None:
    path = example_path(name)
    source = path.read_text(encoding="utf-8")
    assert provenance_problems(tomllib.loads(source)) == []
    assert text_problems(sheet_texts(source, name)) == []
    written = write_drawing_sheet(build_sheet(load_spec(path, require_provenance=True))).text
    assert scan.scan_bytes(f"{name}.kicad_wks", written.encode("utf-8"), scan.load_config()) == []


def test_labels_are_listed() -> None:
    assert {"Title", "Legal owner", "Identification number"} <= listed_labels()


@pytest.mark.parametrize("bad", ["S-0066", "S-0058"])
def test_value_from_kicad_files_refused(bad: str) -> None:
    data = tomllib.loads(example_path("iso5457_generic").read_text(encoding="utf-8"))
    data["provenance"]["values"]["margins.left"] = bad
    assert provenance_problems(data) == [f"margins.left cites {bad!r}, which is not an allowed source"]


def test_unlisted_text_refused() -> None:
    source = example_path("iso5457_generic").read_text(encoding="utf-8")
    copy = source.replace('label = "Legal owner"', 'label = "Approved by Bob"')
    assert text_problems(sheet_texts(copy, "copy")) == [
        "text 'Approved by Bob' is not a token, a listed label or a zone label"
    ]
