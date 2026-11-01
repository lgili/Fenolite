# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sheet entries from block ports (capability altium-schematic-writer, "Sheets of a module tree", "Sheet
entries from block ports" and "Block sheet name clash in Altium"; change c0269), on the authored sample
``tests/data/altium/blocks/design.py``. Read back with the product reader and importer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _altium_tree import catalog_symbols, documents, nets_of, project_files, read_back

from fenolite.backends.altium.hierarchy import crossings, name_clashes
from fenolite.backends.altium.read.sch.records import NetLabel, Port, SheetEntry
from fenolite.dsl import Design, to_model
from fenolite.lens.altium import ALTIUM_ISSUE_CODES, build_altium
from fenolite.lens.build import BuildOutput
from fenolite.model.design import Design as ModelDesign

SAMPLE = Path(__file__).resolve().parents[3] / "data" / "altium" / "blocks" / "design.py"


def sample(*replacements: tuple[str, str]) -> Design:
    text = SAMPLE.read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in text, old
        text = text.replace(old, new)
    scope: dict[str, Any] = {"__name__": "design"}
    exec(compile(text, str(SAMPLE), "exec"), scope)  # noqa: S102 - the repository's own test data
    design = scope["design"]
    assert isinstance(design, Design)
    return design


def built(model: ModelDesign, form: str = "binary") -> BuildOutput:
    return build_altium(
        model,
        name="blocks",
        form=form,  # type: ignore[arg-type]
        sheets="modules",
        authored_symbols=catalog_symbols(model),
        symbol_bodies="graphics",
    )


def test_block_instance_crossings(tmp_path: Path) -> None:
    model = to_model(sample())
    for form in ("binary", "ascii"):
        output = built(model, form)
        assert not [i for i in output.issues if i.severity == "error"]
        sheets = documents(output)
        child = sheets["blocks_f1.SchDoc"]
        ports = {p.name: p.io_type for p in child.of_type(Port)}
        entries = {e.name: e.io_type for e in sheets["blocks.SchDoc"].of_type(SheetEntry)}
        assert set(ports) == {"IN", "OUT", "TEST"} and ports == entries
        labels = {n.text for n in child.of_type(NetLabel)}
        assert {"SRC", "DST"} <= labels, "the stubs keep the circuit net names"
        assert {"SRC", "DST"} <= {n.text for n in sheets["blocks.SchDoc"].of_type(NetLabel)}
        design = read_back(tmp_path / form, output)
        assert nets_of(design) == nets_of(model)


def test_escaping_net_still_crosses() -> None:
    found = crossings(to_model(sample()), form="binary")
    assert [(c.name, c.label) for c in found["f1"]] == [("IN", "SRC"), ("OUT", "DST"), ("TEST", None)]


def test_power_port_stays_global() -> None:
    found = crossings(to_model(sample()), form="binary")
    assert "GND" not in {c.name for c in found["f1"]}
    sheets = documents(built(to_model(sample())))
    assert "GND" not in {p.name for p in sheets["blocks_f1.SchDoc"].of_type(Port)}


def test_escaping_net_named_like_a_port() -> None:
    model = to_model(sample(('TEST = Net("TEST")', 'TEST = Net("IN")')))
    assert name_clashes(model) == [("f1", "IN")]
    output = built(model)
    (clash,) = [i for i in output.issues if i.code == "build.block-sheet-name-clash"]
    assert clash.severity == "error" == ALTIUM_ISSUE_CODES[clash.code]
    assert "f1" in clash.message and "IN" in clash.message
    assert project_files(output) == {}


def test_designs_without_blocks_cross_by_net() -> None:
    from _altium_tree import tree_model

    found = crossings(tree_model(), form="binary")
    assert all(c.label is None for crossings_of in found.values() for c in crossings_of)


@pytest.mark.parametrize("sheets", ["flat"])
def test_flat_sheets_unaffected(sheets: str) -> None:
    model = to_model(sample())
    output = build_altium(
        model,
        name="blocks",
        form="binary",
        sheets=sheets,
        authored_symbols=catalog_symbols(model),  # type: ignore[arg-type]
    )
    assert not [i for i in output.issues if i.severity == "error"]
