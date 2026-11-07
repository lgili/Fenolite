# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Full local native ASTs survive scoped cache selection and serialization (c0327)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from _buildhelp import build
from _contextual_symbols import NATIVE_ID, code

from fenolite.backends.kicad import sch, symbol_contexts, symembed
from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.cli._script import run_design_script
from fenolite.core.errors import FormatError
from fenolite.dsl import copper, to_model
from fenolite.lens.drawn import read_drawn


def inputs(folder: Path, target: int = 9):
    script = code(folder, target)
    design = run_design_script(script).design
    value = read_drawn((folder / "schematic.toml").read_text(encoding="utf-8"))
    contexts = symbol_contexts.read(
        folder / symbol_contexts.FILE,
        drawing_path=folder / "schematic.toml",
        drawn=value,
        project_folder=folder,
    )
    return design, value, contexts


def make(folder: Path, target: int, design, value, contexts):
    return build(
        design,
        target,
        project_dir=folder,
        drawn=value,
        context_symbols=contexts,
        copper_intents=copper(design),
    )


@pytest.mark.parametrize("target", [9, 10])
def test_each_sheet_writes_its_full_original_native_ast(target: int, tmp_path: Path) -> None:
    folder = tmp_path / "code"
    design, value, contexts = inputs(folder, target)
    before = to_model(design).circuit
    made = make(folder, target, design, value, contexts)
    assert made.files and not any(i.severity == "error" for i in made.issues), made.issues
    files = symbol_contexts.source_files(value, f"{design.name}.kicad_sch")
    native = {}
    for (sheet, lib_id), full in contexts.symbols.items():
        raw = parse(made.files[files[sheet]].decode("utf-8")).find("lib_symbols")
        assert raw is not None
        written = next(item for item in raw.nodes("symbol") if item.atoms()[0].value == lib_id)
        expected = symembed.embed_symbol(full.definition, target=target, show_hidden_power=False)
        assert written == expected.node
        native[(sheet, lib_id)] = written
    snapshots = [node for (sheet, lib_id), node in native.items() if lib_id == NATIVE_ID]
    assert len(snapshots) == 2 and snapshots[0].nodes("property") != snapshots[1].nodes("property")
    assert [
        (c.ref, c.value, c.lib_symbol_ref, c.lib_footprint_ref, c.dnp) for c in made.design.circuit.components
    ] == [(c.ref, c.value, c.lib_symbol_ref, c.lib_footprint_ref, c.dnp) for c in before.components]


def test_wrong_context_snapshot_refuses_even_with_identical_pins(tmp_path: Path) -> None:
    folder = tmp_path / "code"
    design, value, contexts = inputs(folder)
    first, second = [key for key in contexts.symbols if key[1] == NATIVE_ID]
    swapped = dict(contexts.symbols)
    swapped[first], swapped[second] = swapped[second], swapped[first]
    with pytest.raises(FormatError, match="wrong full native context binding"):
        make(folder, 9, design, value, replace(contexts, symbols=swapped))


def test_global_power_projection_cannot_accept_local_power(tmp_path: Path) -> None:
    folder = tmp_path / "code"
    design, value, contexts = inputs(folder, 10)
    library = folder / "lib/Mini.kicad_sym"
    text = library.read_text(encoding="utf-8")
    assert "(power)" in text
    library.write_text(text.replace("(power)", "(power local)"), encoding="utf-8")
    with pytest.raises(FormatError, match="changes native semantics"):
        make(folder, 10, design, value, contexts)


@pytest.mark.parametrize("entire_group", [False, True])
def test_missing_first_or_entire_native_group_cannot_fall_back(entire_group: bool, tmp_path: Path) -> None:
    folder = tmp_path / "code"
    design, value, contexts = inputs(folder)
    first = next(key for key in contexts.symbols if key[1] == NATIVE_ID)
    removed = {key for key in contexts.symbols if key[1] == NATIVE_ID} if entire_group else {first}
    kept = {key: full for key, full in contexts.symbols.items() if key not in removed}
    with pytest.raises(FormatError, match="context binding is missing"):
        make(folder, 9, design, value, replace(contexts, symbols=kept))


def test_unknown_context_entry_refuses_before_output(tmp_path: Path) -> None:
    folder = tmp_path / "code"
    design, value, contexts = inputs(folder)
    full = next(iter(contexts.symbols.values()))
    extra = (value.root, full.lib_id)
    changed = replace(
        contexts,
        symbols={**contexts.symbols, extra: full},
        definition_digests={**contexts.definition_digests, extra: symbol_contexts.definition_sha(full)},
    )
    with pytest.raises(FormatError, match="unknown="):
        make(folder, 9, design, value, changed)


@pytest.mark.parametrize("defect", ["property", "duplicate", "extra"])
def test_actual_written_property_loss_refuses_despite_equal_pins(
    defect: str, tmp_path: Path, monkeypatch
) -> None:
    folder = tmp_path / "code"
    design, value, contexts = inputs(folder)
    write = sch.write_schematic

    def corrupt(*args, **kwargs):
        made = write(*args, **kwargs)
        if defect == "property":
            return replace(
                made, text=made.text.replace("Authored sheet metadata snapshot B", "WRONG_CONTEXT")
            )
        root = parse(made.text)
        library = root.find("lib_symbols")
        if library is None or not library.nodes("symbol"):
            return made
        first = library.nodes("symbol")[0]
        extra = (
            first
            if defect == "duplicate"
            else first.with_children((Atom.string("Authored:Extra"), *first.children[1:]))
        )
        changed = library.with_children((extra, *library.children))
        return replace(
            made, text=dumps(root.with_children(tuple(changed if n is library else n for n in root.children)))
        )

    monkeypatch.setattr(sch, "write_schematic", corrupt)
    message = "written contextual native AST " + (
        "differs" if defect == "property" else "has duplicate/missing/unknown"
    )
    with pytest.raises(FormatError, match=message):
        make(folder, 9, design, value, contexts)
