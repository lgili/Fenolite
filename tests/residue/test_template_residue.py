# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Residue check of the shipped sheet examples (capability sheet-templates, "Shipped sheet examples",
scenario "Residue check"; change c0012). An allowlist: every number cites ``fenolite-choice`` or one of the
registered public sources S-0077, S-0078 and S-0079; every text is a neutral token, a label listed in
``docs/formats/sheets.md`` or a one-character zone label; the written ``.kicad_wks`` has no residue. No
test of this change reads a kicad-templates sheet or KiCad's default sheet.

Change c0046 ("Authored sheet fixtures and corpus rows") adds: no tracked file has the extension
``.SchDot``, in any letter case; no file under ``src/fenolite/templates/`` or
``src/fenolite/backends/altium/`` starts with the compound-file signature; and the texts of the authored
Altium templates of ``tests/_altium_sheet.py`` are special strings, words of its ``WORDS`` or one-character
labels."""

from __future__ import annotations

import re
import subprocess
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import _altium_sheet
import _scanmod
import pytest

from fenolite.backends.altium.cfb import SIGNATURE
from fenolite.backends.altium.read.sch import read_schematic
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


# --- change c0046: no committed Altium template -------------------------------------------------------------

NO_COMPOUND_FILE = ("src/fenolite/templates", "src/fenolite/backends/altium")
"""The packages that must hold no compound file: a binary template there would ship with the wheel."""


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def schdot_problems(files: Iterable[str]) -> list[str]:
    """The files with the extension ``.SchDot``, in any letter case."""
    return [f"{name}: a sheet template (.SchDot) must not be committed" for name in files
            if name.lower().endswith(".schdot")]  # fmt: skip


def compound_problems(root: Path, folders: Iterable[str] = NO_COMPOUND_FILE) -> list[str]:
    """The files under ``folders`` that start with the compound-file signature."""
    problems: list[str] = []
    for folder in folders:
        for path in sorted((root / folder).rglob("*")):
            if path.is_file():
                with path.open("rb") as handle:
                    if handle.read(len(SIGNATURE)) == SIGNATURE:
                        problems.append(f"{path.relative_to(root).as_posix()}: a compound file")
    return problems


def fixture_text_problems(texts: Iterable[str], words: frozenset[str] = _altium_sheet.WORDS) -> list[str]:
    """The texts that are not a special string, a listed generic word or a one-character label."""
    return [
        f"text {text!r} is not a special string, a word of WORDS or a one-character label"
        for text in texts
        if not (text.startswith("=") or text in words or len(text) == 1)
    ]


def fixture_texts() -> tuple[list[str], list[str]]:
    """The ``TEXT`` values of the labels and the ``NAME`` values of the parameters of every authored
    template, read back from its ASCII form."""
    texts: list[str] = []
    names: list[str] = []
    for name in _altium_sheet.CASES:
        for record in read_schematic(_altium_sheet.template(name, form="ascii")).records:
            if record.props is None:
                continue
            if record.record_id == 41:
                names.append(record.props.text("NAME"))
            elif record.props.has("TEXT"):
                texts.append(record.props.text("TEXT"))
    return texts, names


def test_no_template_is_committed() -> None:
    files = tracked_files()
    assert files and schdot_problems(files) == []
    assert compound_problems(ROOT) == []


def test_a_committed_template_is_refused(tmp_path: Path) -> None:
    files = [*tracked_files(), "docs/a4.SchDot"]
    assert schdot_problems(files) == ["docs/a4.SchDot: a sheet template (.SchDot) must not be committed"]
    assert len(schdot_problems(["a/B.SCHDOT", "c.schdot", "d.SchDoc", "e.schdot.md"])) == 2
    package = tmp_path / "src" / "fenolite" / "templates"
    package.mkdir(parents=True)
    (package / "sheet.bin").write_bytes(_altium_sheet.template("a4", form="binary"))
    (package / "notes.txt").write_bytes(_altium_sheet.template("a4", form="ascii"))
    assert compound_problems(tmp_path, ["src/fenolite/templates"]) == [
        "src/fenolite/templates/sheet.bin: a compound file"
    ]


def test_authored_altium_templates_hold_generic_texts() -> None:
    texts, names = fixture_texts()
    assert len(texts) >= 30 and fixture_text_problems(texts) == []
    assert names and set(names) <= _altium_sheet.PARAMETER_NAMES
    assert fixture_text_problems(["=Title", "A", "Rev", "Approved by Bob"]) == [
        "text 'Approved by Bob' is not a special string, a word of WORDS or a one-character label"
    ]
