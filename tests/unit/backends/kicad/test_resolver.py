# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lookups, the parse cache, missing 3D models and the closed issue set (kicad-library-resolution)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _libs import MINI, make_symdir

from fenolite.backends.kicad import libs
from fenolite.backends.kicad.liberrors import ISSUE_CODES, LibraryError, lib_issue
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.core.errors import Issue

ROOT = Path(__file__).resolve().parents[4]
PROJECT = MINI / "project"
R0603 = "Mini:Mini_R_0603"


def _resolver(tmp_path: Path, **overrides: object) -> LibraryResolver:
    empty = tmp_path / "empty-config"
    empty.mkdir(exist_ok=True)
    settings: dict[str, object] = {
        "env": {},
        "install_dir": tmp_path / "no-install",
        "config_home": empty,
        "project_dir": PROJECT,
    }
    settings.update(overrides)
    return LibraryResolver(LibraryConfig(**settings))  # type: ignore[arg-type]


def _project(tmp_path: Path, kind: str, *rows: tuple[str, str]) -> Path:
    project = tmp_path / "proj"
    project.mkdir(exist_ok=True)
    root, name = (
        ("fp_lib_table", "fp-lib-table") if kind == "footprint" else ("sym_lib_table", "sym-lib-table")
    )
    body = " ".join(
        f'(lib (name "{n}") (type "KiCad") (uri "{str(u).replace(chr(92), "/")}") (options "") (descr ""))'
        for n, u in rows
    )
    (project / name).write_text(f"({root} (version 7) {body})", encoding="utf-8")
    return project


def _code(exc: pytest.ExceptionInfo[LibraryError]) -> str:
    return exc.value.issue.code


# --- lookups --------------------------------------------------------------------------------------


def test_footprint_through_the_project_table(tmp_path: Path) -> None:
    fp = _resolver(tmp_path).footprint("Mini:Mini_QFP-32_7x7mm_P0.8mm")
    assert len(fp.pads) == 32 and fp.library == "Mini" and fp.lib_id == "Mini:Mini_QFP-32_7x7mm_P0.8mm"
    assert fp == read_footprint(MINI / "Mini.pretty" / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod", library="Mini")


def test_hidden_rows_resolve(tmp_path: Path) -> None:
    assert _resolver(tmp_path).footprint("MiniHidden:Mini_R_0603").library == "MiniHidden"


def test_symbol_from_a_file_is_flattened(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path)
    red, led = resolver.symbol("Mini:Mini_LED_Red"), resolver.symbol("Mini:Mini_LED")
    assert red.pins == led.pins and red.library == "Mini" and red.extends == "Mini_LED"
    assert resolver.symbol("NestedMini:Mini_GND").power == "global"


def test_derived_symbol_through_a_folder_library(tmp_path: Path) -> None:
    folder = make_symdir(MINI / "Mini.kicad_sym", tmp_path / "Mini.kicad_symdir")
    project = _project(tmp_path, "symbol", ("MiniDir", str(folder)))
    resolver = _resolver(tmp_path, project_dir=project)
    location = resolver.locate("MiniDir:Mini_LED_Red", "symbol")
    assert location.item_path == folder / "Mini_LED_Red.kicad_sym" and location.library_path == folder
    red = resolver.symbol("MiniDir:Mini_LED_Red")
    expected = {s.name: s for s in resolve_extends(read_symbol_library(MINI / "Mini.kicad_sym"))}["Mini_LED"]
    assert red.pins == expected.pins and len(red.pins) == 2


def test_folder_scan_when_the_file_name_differs(tmp_path: Path) -> None:
    folder = make_symdir(MINI / "Mini.kicad_sym", tmp_path / "Mini.kicad_symdir")
    (folder / "Mini_LED.kicad_sym").rename(folder / "zz_parent.kicad_sym")
    (folder / "Mini_R.kicad_sym").rename(folder / "Resistors.kicad_sym")
    project = _project(tmp_path, "symbol", ("MiniDir", str(folder)))
    resolver = _resolver(tmp_path, project_dir=project)
    assert resolver.locate("MiniDir:Mini_R", "symbol").item_path == folder / "Resistors.kicad_sym"
    assert len(resolver.symbol("MiniDir:Mini_LED_Red").pins) == 2


def test_missing_parent_in_a_folder(tmp_path: Path) -> None:
    folder = make_symdir(MINI / "Mini.kicad_sym", tmp_path / "Mini.kicad_symdir")
    (folder / "Mini_LED.kicad_sym").unlink()
    project = _project(tmp_path, "symbol", ("MiniDir", str(folder)))
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path, project_dir=project).symbol("MiniDir:Mini_LED_Red")
    assert _code(caught) == "kicad.lib.missing-parent"


def test_unsupported_library_type(tmp_path: Path) -> None:
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path).locate("MiniLegacy:X", "symbol")
    assert _code(caught) == "kicad.lib.unsupported-type"


def test_disabled_library(tmp_path: Path) -> None:
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path).footprint("MiniDisabled:Mini_R_0603")
    assert _code(caught) == "kicad.lib.disabled"


def test_missing_entry(tmp_path: Path) -> None:
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path).footprint("Mini:Does_Not_Exist")
    assert _code(caught) == "kicad.lib.missing-entry"
    assert Path(caught.value.issue.where) == MINI / "Mini.pretty"
    with pytest.raises(LibraryError) as symbol:
        _resolver(tmp_path).symbol("Mini:Does_Not_Exist")
    assert _code(symbol) == "kicad.lib.missing-entry"


def test_missing_library_folder(tmp_path: Path) -> None:
    project = _project(
        tmp_path, "footprint", ("Gone", "${KIPRJMOD}/Gone.pretty"), ("File", str(MINI / "Mini.kicad_sym"))
    )
    resolver = _resolver(tmp_path, project_dir=project)
    for lib_id in ("Gone:X", "File:X"):
        with pytest.raises(LibraryError) as caught:
            resolver.footprint(lib_id)
        assert _code(caught) == "kicad.lib.missing-library"
    symbols = _project(tmp_path, "symbol", ("Gone", "${KIPRJMOD}/Gone.kicad_sym"))
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path, project_dir=symbols).symbol("Gone:X")
    assert _code(caught) == "kicad.lib.missing-library"


def test_invalid_identifier_through_the_resolver(tmp_path: Path) -> None:
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path).footprint("Mini_R_0603")
    assert _code(caught) == "kicad.lib.invalid-id"


def test_unknown_nickname(tmp_path: Path) -> None:
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path).footprint("Nope:X")
    assert _code(caught) == "kicad.lib.unknown-nickname" and "fp-lib-table" in caught.value.hint


def test_reader_issues_go_to_the_lookup_list(tmp_path: Path) -> None:
    folder = tmp_path / "Odd.pretty"
    folder.mkdir()
    shutil.copyfile(MINI / "Mini.pretty" / "Mini_R_0603.kicad_mod", folder / "Renamed.kicad_mod")
    project = _project(tmp_path, "footprint", ("Odd", str(folder)))
    issues: list[Issue] = []
    fp = _resolver(tmp_path, project_dir=project).footprint("Odd:Renamed", issues=issues)
    assert fp.name == "Renamed" and [i.code for i in issues] == ["kicad.lib.name-mismatch"]


# --- the parse cache ------------------------------------------------------------------------------


def test_parsed_files_are_cached_while_unchanged(tmp_path: Path) -> None:
    folder = tmp_path / "Mini.pretty"
    shutil.copytree(MINI / "Mini.pretty", folder)
    project = _project(tmp_path, "footprint", ("Mini", str(folder)))
    resolver = _resolver(tmp_path, project_dir=project)
    item = folder / "Mini_R_0603.kicad_mod"
    first = resolver._load(item)  # pyright: ignore[reportPrivateUsage]
    assert resolver._load(item) is first  # pyright: ignore[reportPrivateUsage]
    item.write_text(
        item.read_text(encoding="utf-8").replace("Mini 0603", "Mini 0603 changed"), encoding="utf-8"
    )
    os.utime(item, ns=(1, 1))
    changed = resolver.footprint("Mini:Mini_R_0603")
    assert changed.description.startswith("Mini 0603 changed")


def test_cache_is_bounded(tmp_path: Path) -> None:
    folder = tmp_path / "Many.pretty"
    folder.mkdir()
    source = (MINI / "Mini.pretty" / "Mini_R_0603.kicad_mod").read_text(encoding="utf-8")
    resolver = _resolver(tmp_path)
    for index in range(libs.CACHE_SIZE + 4):
        path = folder / f"R{index}.kicad_mod"
        path.write_text(source, encoding="utf-8")
        resolver._load(path)  # pyright: ignore[reportPrivateUsage]
    assert len(resolver._cache) == libs.CACHE_SIZE  # pyright: ignore[reportPrivateUsage]


# --- missing 3D models ----------------------------------------------------------------------------


def test_mini_resistor_model_absent(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    resolver = _resolver(tmp_path, env={"KICAD10_3DMODEL_DIR": str(models)})
    found = resolver.missing_models(resolver.footprint(R0603))
    assert [(i.code, i.severity) for i in found] == [("kicad.lib.missing-3d-model", "warning")]
    (models / "Mini.3dshapes").mkdir()
    (models / "Mini.3dshapes" / "Mini_R_0603.step").write_text("ISO-10303-21;", encoding="utf-8")
    assert resolver.missing_models(resolver.footprint(R0603)) == ()


def test_model_variable_without_a_value(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path)
    found = resolver.missing_models(resolver.footprint(R0603))
    assert len(found) == 1 and found[0].code == "kicad.lib.missing-3d-model"
    assert "KICAD10_3DMODEL_DIR" in found[0].message


# --- issue codes, CLI mapping and import order ----------------------------------------------------


def _collect(tmp_path: Path) -> list[Issue]:
    """Run the operations of this capability and of kicad-library-read that report issues."""
    issues: list[Issue] = []
    resolver = _resolver(tmp_path, target_major=9)
    resolver.rows("footprint")
    resolver.rows("symbol")
    issues += resolver.issues
    for lib_id in ("Mini_R_0603", "Nope:X", "MiniDisabled:X", "MiniLegacy:X", "Mini:Does_Not_Exist"):
        try:
            resolver.footprint(lib_id)
        except LibraryError as exc:
            issues.append(exc.issue)
    ten = _resolver(tmp_path)
    issues += ten.missing_models(ten.footprint(R0603))
    copy = tmp_path / "Other.kicad_mod"
    shutil.copyfile(MINI / "Mini.pretty" / "Mini_Edge_Cases.kicad_mod", copy)
    read_footprint(copy, issues=issues)
    duplicate = (
        '(fp_lib_table (lib (name "A") (type "KiCad") (uri "/a")) (lib (name "A") (type "KiCad") (uri "/b")))'
    )
    libs.read_lib_table(duplicate, issues=issues)
    for body in ('(symbol "A" (extends "B"))', '(symbol "A" (extends "A"))'):
        try:
            resolve_extends(read_symbol_library(f"(kicad_symbol_lib (version 20251024) {body})"))
        except LibraryError as exc:
            issues.append(exc.issue)
    return issues


def test_closed_set(tmp_path: Path) -> None:
    issues = _collect(tmp_path)
    produced = {i.code for i in issues}
    assert len(produced) >= 12, produced
    for issue in issues:
        if issue.code.startswith("kicad.version."):
            continue
        assert ISSUE_CODES.get(issue.code) == issue.severity, issue
    literals: set[str] = set()
    for path in sorted((ROOT / "src" / "fenolite" / "backends" / "kicad").glob("*.py")):
        literals |= set(re.findall(r'"(kicad\.lib\.[a-z0-9-]+)"', path.read_text(encoding="utf-8")))
    assert literals == set(ISSUE_CODES)


def test_closed_set_is_enforced_by_the_helpers() -> None:
    with pytest.raises(ValueError, match="not a KiCad library issue code"):
        lib_issue("kicad.lib.made-up", "x")
    with pytest.raises(ValueError, match="error code"):
        LibraryError(lib_issue("kicad.lib.kept-opaque", "x"))


def test_library_error_maps_to_fen_3001() -> None:
    from fenolite.cli.errors import from_exception

    error = libs.LibraryError(lib_issue("kicad.lib.unresolved-variable", "no value", hint="set X"))
    failure = from_exception(error, "here")
    assert failure.code == "FEN-3001" and failure.hint == "set X"


def test_no_import_cycle() -> None:
    code = (
        "import fenolite.backends.kicad.sym, fenolite.backends.kicad.libs as l, "
        "fenolite.backends.kicad.liberrors as e; assert l.LibraryError is e.LibraryError"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False, timeout=120
    )
    assert result.returncode == 0, result.stderr
