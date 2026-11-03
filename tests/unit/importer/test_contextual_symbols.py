# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Complete local metadata and closed native semantic boundaries (c0327)."""

from __future__ import annotations

import json
import shutil
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest
from _contextual_symbols import (
    FIRST,
    FIXTURE,
    NATIVE_ID,
    SECOND,
    change,
    definition,
    project,
    property_value,
    source,
)

from fenolite.backends.kicad import drawn
from fenolite.backends.kicad import symbol_contexts as contexts
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.errors import FormatError
from fenolite.importer.emit import Options, emit
from fenolite.importer.emit.sheets import Hierarchy
from fenolite.importer.provenance import Provenance
from fenolite.importer.schematic import drawing as source_drawing
from fenolite.importer.schematic import symbols
from fenolite.importer.source import read_kicad
from fenolite.importer.vendor import vendor
from fenolite.lens.drawn import read_drawn


def without_properties(node: Node) -> Node:
    return node.with_children(tuple(c for c in node.children
                                   if not isinstance(c, Node) or c.name != "property"))  # fmt: skip


def test_authored_local_metadata_witness_is_not_a_pin_or_body_change() -> None:
    first = definition((FIXTURE / FIRST).read_text(encoding="utf-8"))
    second = definition((FIXTURE / SECOND).read_text(encoding="utf-8"))
    assert first != second
    assert without_properties(first) == without_properties(second)
    assert first.nodes("property") != second.nodes("property")
    a, b = source().hierarchy[FIRST], source().hierarchy[SECOND]
    assert a.native_ids != b.native_ids
    left = next(s for s in a.lib_symbols if s.lib_id == NATIVE_ID)
    right = next(s for s in b.lib_symbols if s.lib_id == NATIVE_ID)
    assert drawn.unit_signature(left, 1) == drawn.unit_signature(right, 1)
    # A wrong-context metadata choice is observably wrong even with equal pins.
    assert dumps(first, style="compact") != dumps(second, style="compact")


def test_metadata_variants_keep_every_occurrence_including_the_first() -> None:
    made = symbols(source(), target=9)
    assert {(FIRST, NATIVE_ID), (SECOND, NATIVE_ID)} <= set(made.contexts)
    used = {(file, s.lib_name or s.lib_ref) for file, sheet in source().hierarchy.items()
            for s in sheet.symbols}  # fmt: skip
    assert set(made.contexts) == used
    assert made.contexts[(FIRST, NATIVE_ID)].node != made.contexts[(SECOND, NATIVE_ID)].node


def test_identical_split_files_keep_the_ordinary_global_path(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    original = definition((FIXTURE / FIRST).read_text(encoding="utf-8"))
    path = tmp_path / SECOND
    path.write_text(change(path.read_text(encoding="utf-8"), lambda _: original), encoding="utf-8")
    made = symbols(source(tmp_path), target=9)
    assert NATIVE_ID in made.definitions and len(made.refs) == 4
    assert not made.contexts


def assets(folder: Path, original_folder: Path = FIXTURE):
    original = source(original_folder)
    library = symbols(original, target=9)
    hierarchy = Hierarchy(original)
    text, _ = source_drawing(
        original, {ref: "/".join(hierarchy.paths.get(ref, (ref,))) for ref in library.refs}
    )
    assert text is not None
    value = read_drawn(text)
    files = contexts.write(
        library.contexts,
        {i.file: i.sha256 for i in original.inputs},
        value,
        root_file=next(iter(original.hierarchy)),
        target=9,
    )
    for name, body in {"schematic.toml": text, **files}.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return value, files


def load(folder: Path, value):
    loaded = contexts.read(
        folder / contexts.FILE, drawing_path=folder / "schematic.toml", drawn=value, project_folder=folder
    )
    by_file = {file: key for key, file in contexts.source_files(value, "drawn_repeat.kicad_sch").items()}
    loaded.validate_used({(by_file[file], lib_id) for file, lib_id in symbols(source(), target=9).contexts})
    return loaded


def test_closed_assets_roundtrip_complete_nodes_and_deterministic_bytes(tmp_path: Path) -> None:
    value, files = assets(tmp_path)
    loaded = load(tmp_path, value)
    assert len(loaded.symbols) == 4 and len(loaded.paths) == 4
    expected = symbols(source(), target=9)
    by_file = {key: file for key, file in contexts.source_files(value, "drawn_repeat.kicad_sch").items()}
    for (sheet, lib_id), embedded in loaded.symbols.items():
        assert embedded.node == expected.contexts[(by_file[sheet], lib_id)].node
    loaded.validate_used(set(loaded.symbols))
    _, again = assets(tmp_path / "again")
    assert files == again


def test_importer_emits_the_required_index_keyword_and_all_full_assets(tmp_path: Path) -> None:
    original = read_kicad(project(tmp_path / "original"))
    made = emit(original, Options("drawn_repeat", Provenance(date="2026-11-02"), target=9))
    assert b'symbol_contexts="symbol-contexts.toml"' in made.files["design.py"]
    data = tomllib.loads(made.files[contexts.FILE].decode("utf-8"))
    assert len(data["symbol"]) == 4
    for row in data["symbol"]:
        assert contexts.sha(made.files[row["asset"]]) == row["asset_sha256"]
        assert row["input_sha256"] == next(i.sha256 for i in original.inputs if i.file == row["input"])


def test_repeated_and_unknown_property_nodes_keep_complete_native_order(tmp_path: Path) -> None:
    original = tmp_path / "original"
    shutil.copytree(FIXTURE, original)
    path = original / SECOND
    extra = tuple(
        parse(
            f'(property "LocalReview" "{value}" (at 0 {index} 90) '
            "(effects (font (size 1 2)) (justify left)) "
            f'(future_property "{value}"))'
        )
        for index, value in enumerate(("first", "second"))
    )
    path.write_text(
        change(path.read_text(encoding="utf-8"), lambda n: n.with_children((*n.children, *extra))),
        encoding="utf-8",
    )
    value, _ = assets(tmp_path / "code", original)
    loaded = load(tmp_path / "code", value)
    full = next(
        v.node
        for (sheet, lib_id), v in loaded.symbols.items()
        if sheet.endswith("authored_second") and lib_id == NATIVE_ID
    )
    assert full.nodes("property") == definition(path.read_text(encoding="utf-8")).nodes("property")
    assert full.nodes("property")[-2:] == extra


def index_text(data) -> str:
    rows = data.pop("symbol")
    lines = [f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in data.items()]
    for row in rows:
        lines += [
            "",
            "[[symbol]]",
            *(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in row.items()),
        ]
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "unknown",
        "type",
        "duplicate",
        "unsorted",
        "sheet",
        "native",
        "input",
        "traversal",
        "digest",
        "wrong-context",
    ],
)
def test_closed_index_refuses_malformed_or_wrong_bindings(defect: str, tmp_path: Path) -> None:
    value, _ = assets(tmp_path)
    path = tmp_path / contexts.FILE
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    first, second = data["symbol"][0], data["symbol"][-1]
    if defect == "missing":
        data["symbol"].pop(0)
    elif defect == "unknown":
        first["unknown"] = "unreviewed"
    elif defect == "type":
        data["target"] = True
    elif defect == "duplicate":
        data["symbol"].insert(0, dict(first))
    elif defect == "unsorted":
        data["symbol"].reverse()
    elif defect == "sheet":
        first["sheet"] = "unknown"
    elif defect == "native":
        first["native_id"] = "Other:Unknown"
    elif defect == "input":
        first["input"] = second["input"]
    elif defect == "traversal":
        first["asset"] = "../elsewhere.kicad_sym"
    elif defect == "digest":
        first["definition_sha256"] = "0" * 64
    else:
        first["asset"], second["asset"] = second["asset"], first["asset"]
    path.write_text(index_text(data), encoding="utf-8")
    with pytest.raises(FormatError):
        load(tmp_path, value)


@pytest.mark.parametrize("which", range(4))
def test_every_asset_digest_including_first_is_checked(which: int, tmp_path: Path) -> None:
    value, _ = assets(tmp_path)
    data = tomllib.loads((tmp_path / contexts.FILE).read_text(encoding="utf-8"))
    asset = tmp_path / data["symbol"][which]["asset"]
    asset.write_bytes(asset.read_bytes() + b"\n")
    with pytest.raises(FormatError, match="digest is stale"):
        load(tmp_path, value)


@pytest.mark.parametrize("which", ["index", "asset", "ancestor"])
def test_symlinked_inputs_and_ancestors_refuse(which: str, tmp_path: Path) -> None:
    value, _ = assets(tmp_path)
    data = tomllib.loads((tmp_path / contexts.FILE).read_text(encoding="utf-8"))
    path = tmp_path / (contexts.FILE if which == "index" else data["symbol"][0]["asset"])
    if which == "ancestor":
        path = path.parent
    moved = path.with_name(path.name + ".owned")
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=moved.is_dir())
    with pytest.raises(FormatError, match="symlink"):
        load(tmp_path, value)


def test_missing_or_unknown_used_contexts_refuse_even_with_matching_pins(tmp_path: Path) -> None:
    value, _ = assets(tmp_path)
    loaded = load(tmp_path, value)
    first = next(iter(loaded.symbols))
    with pytest.raises(FormatError, match="missing="):
        replace(loaded, symbols={k: v for k, v in loaded.symbols.items() if k != first}).validate_used(
            set(loaded.symbols)
        )
    with pytest.raises(FormatError, match="unknown="):
        loaded.validate_used(set(loaded.symbols) - {first})


@pytest.mark.parametrize("control", ["\x00", "\n", "\x7f", "\x85", "\u200b"])
def test_original_context_paths_reject_ascii_and_unicode_controls(control: str, tmp_path: Path) -> None:
    value, _ = assets(tmp_path)
    root = value.sheets[0]
    first, *others = root.sheet_refs
    unsafe = replace(first, file="sheets/" + control + "channel.kicad_sch")
    changed = replace(value, sheets=(replace(root, sheet_refs=(unsafe, *others)), *value.sheets[1:]))
    with pytest.raises(FormatError, match="escapes the source folder"):
        contexts.source_files(changed, "drawn_repeat.kicad_sch")


def test_same_file_duplicate_native_definitions_refuse() -> None:
    found = source()
    sheet = found.hierarchy[FIRST]
    duplicate = replace(sheet, lib_symbols=(*sheet.lib_symbols, sheet.lib_symbols[0]))
    with pytest.raises(FormatError, match="duplicate embedded"):
        symbols(replace(found, hierarchy={**found.hierarchy, FIRST: duplicate}), target=9)


def test_contextual_inheritance_refuses_instead_of_flattening_property_nodes(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    path = tmp_path / SECOND
    root = parse(path.read_text(encoding="utf-8"))
    library = root.find("lib_symbols")
    assert library is not None
    child = definition(path.read_text(encoding="utf-8"))

    def parent(item):
        if isinstance(item, Atom):
            return item
        children = tuple(parent(c) for c in item.children)
        if item.name == "symbol":
            old = item.atoms()[0].value
            children = (Atom.string(old.replace("Mini_R", "AuthoredBase", 1)), *children[1:])
        return item.with_children(children)

    inherited = child.with_children(
        (child.children[0], parse('(extends "AuthoredBase")'), *child.nodes("property"))
    )
    library_new = library.with_children(
        (*(inherited if n == child else n for n in library.children), parent(child))
    )
    path.write_text(
        dumps(root.with_children(tuple(library_new if n is library else n for n in root.children))),
        encoding="utf-8",
    )
    with pytest.raises(FormatError, match="contextual inheritance"):
        symbols(source(tmp_path), target=9)


@pytest.mark.parametrize("nickname", ["Authored Local", "../outside", "CON", "trailing.", "trailing "])
def test_native_namespaces_preserve_safe_spaces_and_keep_path_guards(nickname: str, tmp_path: Path) -> None:
    path = project(tmp_path / "original")
    for file in path.parent.rglob("*.kicad_sch"):
        file.write_text(file.read_text(encoding="utf-8").replace("Mini:", nickname + ":"), encoding="utf-8")
    original = read_kicad(path)
    if nickname == "Authored Local":
        made = vendor(original.design, original.board_text, source=original, target=9)
        assert "lib/Authored Local.kicad_sym" in made.files
        assert all(key[1].startswith(nickname + ":") for key in made.source_symbols.contexts)
    else:
        with pytest.raises(FormatError, match="cannot name a vendored file"):
            vendor(original.design, original.board_text, source=original, target=9)


def mutation(node: Node, defect: str) -> Node:
    if defect in ("Reference", "Value", "Footprint"):
        return property_value(node, defect, "AUTHORED_DIFFERENT_DEFAULT")
    if defect in ("in_bom", "on_board", "exclude_from_sim"):
        flag = node.find(defect)
        assert flag is not None
        changed = flag.with_children((Atom.symbol("no" if flag.atoms()[0].value == "yes" else "yes"),))
        return node.with_children(tuple(changed if c is flag else c for c in node.children))
    if defect == "unknown":
        return node.with_children((*node.children, parse('(future_semantics "authored-negative")')))
    unit = next(s for s in node.nodes("symbol") if s.nodes("pin"))
    pin = unit.nodes("pin")[0]
    field = pin.find("number" if defect == "pin" else "at")
    assert field is not None
    atoms = (
        (Atom.string("99"), *field.children[1:])
        if defect == "pin"
        else (Atom.from_nm(123_450_000), *field.children[1:])
    )
    changed_pin = pin.with_children(
        tuple(field.with_children(atoms) if c is field else c for c in pin.children)
    )
    changed_unit = unit.with_children(tuple(changed_pin if c is pin else c for c in unit.children))
    return node.with_children(tuple(changed_unit if c is unit else c for c in node.children))


@pytest.mark.parametrize(
    "defect",
    [
        "Reference",
        "Value",
        "Footprint",
        "pin",
        "geometry",
        "in_bom",
        "on_board",
        "exclude_from_sim",
        "unknown",
    ],
)
def test_semantic_and_unknown_nonproperty_changes_remain_closed(defect: str, tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    path = tmp_path / SECOND
    path.write_text(change(path.read_text(encoding="utf-8"), lambda n: mutation(n, defect)), encoding="utf-8")
    with pytest.raises(FormatError, match="conflicting definitions"):
        symbols(source(tmp_path), target=9)


@pytest.mark.parametrize("target", (9, 10))
def test_ordinary_source_inheritance_binds_resolved_parent_pins(target: int, tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    expected = next(
        item for item in source(tmp_path).hierarchy[SECOND].lib_symbols if item.lib_id == NATIVE_ID
    )
    path = tmp_path / SECOND
    root = parse(path.read_text(encoding="utf-8"))
    library = root.find("lib_symbols")
    assert library is not None
    child = definition(path.read_text(encoding="utf-8"))

    def parent(item):
        if isinstance(item, Atom):
            return item
        children = tuple(parent(c) for c in item.children)
        if item.name == "symbol":
            old = item.atoms()[0].value
            children = (Atom.string(old.replace("Mini_R", "AuthoredBase", 1)), *children[1:])
        return item.with_children(children)

    inherited = child.with_children(
        (child.children[0], parse('(extends "AuthoredBase")'), *child.nodes("property"))
    )
    library_new = library.with_children(
        (*(inherited if node == child else node for node in library.children), parent(child))
    )
    path.write_text(
        dumps(root.with_children(tuple(library_new if node is library else node for node in root.children))),
        encoding="utf-8",
    )
    found = source(tmp_path)
    sheet = found.hierarchy[SECOND]
    raw_child = next(item for item in sheet.lib_symbols if item.lib_id == NATIVE_ID)
    assert raw_child.extends == "AuthoredBase" and raw_child.pins == ()
    # One physical sheet has no contextual variant; this is ordinary supported inheritance.
    result = symbols(replace(found, hierarchy={SECOND: sheet}), target=target)
    embedded = result.definitions[NATIVE_ID]
    assert embedded.definition.pins == expected.pins
    assert embedded.definition.units == expected.units
    assert embedded.definition.properties == expected.properties
    assert embedded.node.find("extends") is None and not result.contexts
