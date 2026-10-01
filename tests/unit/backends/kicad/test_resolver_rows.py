# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Effective rows of the resolver (kicad-library-resolution: "Table discovery and precedence",
"Path variable expansion"). Every test injects its folders and an empty environment."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _libs import MINI, make_install

from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver

PROJECT = MINI / "project"


def _row(name: str, uri: str, kind: str = "KiCad", extra: str = "") -> str:
    return f'(lib (name "{name}") (type "{kind}") (uri "{uri}") (options "") (descr ""){extra})'


def _table(path: Path, *rows: str, root: str = "fp_lib_table") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"({root} (version 7) {' '.join(rows)})", encoding="utf-8")
    return path


def _resolver(tmp_path: Path, **overrides: object) -> LibraryResolver:
    empty = tmp_path / "empty-config"
    empty.mkdir(exist_ok=True)
    settings: dict[str, object] = {"env": {}, "install_dir": tmp_path / "no-install", "config_home": empty}
    settings.update(overrides)
    return LibraryResolver(LibraryConfig(**settings))  # type: ignore[arg-type]


def _codes(resolver: LibraryResolver) -> list[tuple[str, str]]:
    return [(i.code, i.severity) for i in resolver.issues]


def test_project_table_wins(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(MINI / "Mini.pretty", project / "Mini.pretty")
    _table(project / "fp-lib-table", _row("Mini", "${KIPRJMOD}/Mini.pretty"))
    config = tmp_path / "cfg"
    _table(config / "10.0" / "fp-lib-table", _row("Mini", str(MINI / "Mini.pretty")), _row("Other", "/o"))
    resolver = _resolver(tmp_path, project_dir=project, config_home=config)
    location = resolver.locate("Mini:Mini_R_0603", "footprint")
    assert location.origin == "project" and location.library_path == project / "Mini.pretty"
    assert location.table == str(project / "fp-lib-table")
    assert [(r.nickname, o) for r, o, _ in resolver.rows("footprint")] == [
        ("Mini", "project"),
        ("Other", "global"),
    ]


def test_nested_relative_row_resolves_against_the_nested_table(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path, project_dir=PROJECT)
    location = resolver.locate("NestedMini:Mini_R_0603", "footprint")
    assert location.item_path == MINI / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod"
    assert location.table == str(PROJECT / "nested" / "fp-lib-table") and location.origin == "project"
    assert resolver.issues == []


def test_project_rows_in_order(tmp_path: Path) -> None:
    rows = _resolver(tmp_path, project_dir=PROJECT).rows("footprint")
    assert [r.nickname for r, _, _ in rows] == [
        "Mini",
        "MiniRel",
        "MiniDisabled",
        "MiniHidden",
        "MiniLegacy",
        "NestedMini",
    ]


def test_nested_cycle(tmp_path: Path) -> None:
    a, b = tmp_path / "a" / "fp-lib-table", tmp_path / "b" / "fp-lib-table"
    _table(a, _row("A1", "/a1"), _row("ToB", str(b), "Table"))
    _table(b, _row("B1", "/b1"), _row("ToA", str(a), "Table"))
    project = tmp_path / "p"
    _table(project / "fp-lib-table", _row("Top", str(a), "Table"))
    resolver = _resolver(tmp_path, project_dir=project)
    assert [r.nickname for r, _, _ in resolver.rows("footprint")] == ["A1", "B1"]
    assert _codes(resolver) == [("kicad.lib.table-cycle", "warning")]


def test_missing_nested_table(tmp_path: Path) -> None:
    project = tmp_path / "p"
    _table(project / "fp-lib-table", _row("Gone", "${KIPRJMOD}/nowhere/fp-lib-table", "Table"))
    resolver = _resolver(tmp_path, project_dir=project)
    assert resolver.rows("footprint") == ()
    assert _codes(resolver) == [("kicad.lib.missing-table", "warning")]


def test_nested_table_with_an_unresolved_variable(tmp_path: Path) -> None:
    project = tmp_path / "p"
    _table(project / "fp-lib-table", _row("Shared", "${TEAM_TABLES}/fp-lib-table", "Table"))
    resolver = _resolver(tmp_path, project_dir=project)
    assert resolver.rows("footprint") == ()
    assert _codes(resolver) == [("kicad.lib.missing-table", "warning")]
    assert "TEAM_TABLES" in resolver.issues[0].message


def test_nested_rows_with_target_9(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path, project_dir=PROJECT, target_major=9)
    assert "NestedMini" in [r.nickname for r, _, _ in resolver.rows("footprint")]
    assert _codes(resolver) == [("kicad.lib.nested-table-target", "info")]


def test_missing_global_table_falls_back_to_the_template(tmp_path: Path) -> None:
    template = "(fp_lib_table (version 7) " + _row("Mini", "${KICAD10_FOOTPRINT_DIR}/Mini.pretty") + ")"
    install = make_install(tmp_path / "install", template={"fp-lib-table": template})
    shutil.copytree(MINI / "Mini.pretty", install / "footprints" / "Mini.pretty")
    resolver = _resolver(tmp_path, install_dir=install)
    assert [(r.nickname, o) for r, o, _ in resolver.rows("footprint")] == [("Mini", "template")]
    location = resolver.locate("Mini:Mini_R_0603", "footprint")
    assert location.library_path == install / "footprints" / "Mini.pretty"
    assert location.table == str(install / "template" / "fp-lib-table")


def test_template_from_the_library_folder_of_an_env_source(tmp_path: Path) -> None:
    folder = tmp_path / "kicad-footprints"
    shutil.copytree(MINI / "Mini.pretty", folder / "Mini.pretty")
    _table(folder / "fp-lib-table", _row("Mini", "${KICAD10_FOOTPRINT_DIR}/Mini.pretty"))
    resolver = _resolver(tmp_path, env={"KICAD10_FOOTPRINT_DIR": str(folder)})
    assert [(r.nickname, o) for r, o, _ in resolver.rows("footprint")] == [("Mini", "template")]
    assert resolver.footprint("Mini:Mini_R_0603").library == "Mini"


def test_template_dir_variable(tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    _table(templates / "sym-lib-table", _row("Mini", str(MINI / "Mini.kicad_sym")), root="sym_lib_table")
    resolver = _resolver(tmp_path, env={"KICAD10_TEMPLATE_DIR": str(templates)})
    assert [(r.nickname, o) for r, o, _ in resolver.rows("symbol")] == [("Mini", "template")]


def test_global_table_can_be_switched_off(tmp_path: Path) -> None:
    config = tmp_path / "cfg"
    _table(config / "10.0" / "fp-lib-table", _row("G", "/g"))
    assert _resolver(tmp_path, config_home=config, use_global_table=False).rows("footprint") == ()
    assert len(_resolver(tmp_path, config_home=config).rows("footprint")) == 1


def test_disabled_project_row_hides_nothing(tmp_path: Path) -> None:
    project = tmp_path / "p"
    _table(project / "fp-lib-table", _row("Mini", "/off", extra=" (disabled)"))
    config = tmp_path / "cfg"
    _table(config / "10.0" / "fp-lib-table", _row("Mini", str(MINI / "Mini.pretty")))
    location = _resolver(tmp_path, project_dir=project, config_home=config).locate(
        "Mini:Mini_R_0603", "footprint"
    )
    assert location.origin == "global"


def test_relative_uri_in_the_project_table(tmp_path: Path) -> None:
    location = _resolver(tmp_path, project_dir=PROJECT).locate("MiniRel:Mini_R_0603", "footprint")
    assert location.library_path == MINI / "Mini.pretty"


def test_unresolved_variable_in_a_needed_row(tmp_path: Path) -> None:
    project = tmp_path / "p"
    _table(project / "fp-lib-table", _row("X", "${MY_LIBS}/X.pretty"), _row("Ok", "/ok"))
    resolver = _resolver(tmp_path, project_dir=project)
    assert len(resolver.rows("footprint")) == 2
    with pytest.raises(LibraryError) as caught:
        resolver.locate("X:Item", "footprint")
    assert (
        caught.value.issue.code == "kicad.lib.unresolved-variable" and "MY_LIBS" in caught.value.issue.message
    )


def test_tables_load_lazily(tmp_path: Path) -> None:
    project = tmp_path / "p"
    _table(project / "fp-lib-table", _row("Gone", "/nowhere/fp-lib-table", "Table"))
    resolver = _resolver(tmp_path, project_dir=project)
    assert resolver.issues == []
    resolver.rows("footprint")
    resolver.rows("footprint")
    assert len(resolver.issues) == 1
