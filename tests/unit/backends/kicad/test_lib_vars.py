# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path variables and configuration folders (kicad-library-resolution, "Path variable expansion")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _libs import make_install

from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver


def _resolver(tmp_path: Path, **overrides: object) -> LibraryResolver:
    settings: dict[str, object] = {
        "env": {},
        "install_dir": tmp_path / "no-install",
        "home": tmp_path / "home",
    }
    settings.update(overrides)
    return LibraryResolver(LibraryConfig(**settings))  # type: ignore[arg-type]


def test_kiprjmod_cannot_be_overridden(tmp_path: Path) -> None:
    project = tmp_path / "P"
    resolver = _resolver(tmp_path, project_dir=project, env={"KIPRJMOD": "/elsewhere"})
    assert Path(resolver.expand("${KIPRJMOD}/lib")) == project / "lib"
    assert resolver.variables()["KIPRJMOD"] == str(project)


def test_kiprjmod_without_a_project_is_unresolved(tmp_path: Path) -> None:
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path, env={"KIPRJMOD": "/elsewhere"}).expand("${KIPRJMOD}/lib")
    assert caught.value.issue.code == "kicad.lib.unresolved-variable" and "project_dir" in caught.value.hint


def test_environment_wins_over_the_source_default(tmp_path: Path) -> None:
    install = make_install(tmp_path / "install")
    resolver = _resolver(tmp_path, install_dir=install, env={"KICAD10_FOOTPRINT_DIR": "/env"})
    assert resolver.expand("${KICAD10_FOOTPRINT_DIR}") == "/env"
    assert Path(resolver.expand("${KICAD10_SYMBOL_DIR}")) == install / "symbols"
    assert Path(resolver.expand("${KICAD10_3DMODEL_DIR}")) == install / "3dmodels"
    assert Path(resolver.expand("${KICAD10_TEMPLATE_DIR}")) == install / "template"


def test_versioned_fallback(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path, env={"KICAD10_FOOTPRINT_DIR": "/libs"})
    assert resolver.expand("${KICAD9_FOOTPRINT_DIR}/Mini.pretty") == "/libs/Mini.pretty"
    assert resolver.expand("${KICAD8_FOOTPRINT_DIR}") == "/libs"
    explicit = _resolver(tmp_path, env={"KICAD10_FOOTPRINT_DIR": "/libs", "KICAD9_FOOTPRINT_DIR": "/nine"})
    assert explicit.expand("${KICAD9_FOOTPRINT_DIR}") == "/nine"


def test_no_fallback_upwards_from_the_target(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path, target_major=9, env={"KICAD9_FOOTPRINT_DIR": "/nine"})
    with pytest.raises(LibraryError) as caught:
        resolver.expand("${KICAD10_FOOTPRINT_DIR}")
    assert "KICAD10_FOOTPRINT_DIR" in caught.value.issue.message


def test_unresolved_variable_names_it(tmp_path: Path) -> None:
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path).expand("${MY_LIBS}/X.pretty")
    issue = caught.value.issue
    assert issue.code == "kicad.lib.unresolved-variable" and "MY_LIBS" in issue.message
    assert "MY_LIBS" in issue.hint and "preferences" in issue.hint


def test_a_10_install_is_not_used_for_target_9(tmp_path: Path) -> None:
    install = make_install(tmp_path / "install", 20251024)
    resolver = _resolver(tmp_path, target_major=9, install_dir=install)
    with pytest.raises(LibraryError) as caught:
        resolver.expand("${KICAD9_FOOTPRINT_DIR}/Device.pretty")
    assert caught.value.issue.code == "kicad.lib.unresolved-variable"
    assert "KICAD9_FOOTPRINT_DIR" in caught.value.hint


def test_other_syntaxes_are_not_expanded(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path, env={"NAME": "x"})
    assert resolver.expand("$(NAME)/%NAME%/$NAME") == "$(NAME)/%NAME%/$NAME"
    assert resolver.expand("${NAME}${NAME}") == "xx"


def test_relative_results_join_the_table_folder(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path)
    table = str(tmp_path / "project" / "nested" / "fp-lib-table")
    assert Path(resolver.expand("../../Lib.pretty", row_table=table)) == tmp_path / "Lib.pretty"
    assert resolver.expand("/abs/Lib.pretty", row_table=table) == "/abs/Lib.pretty"


def test_variables_lists_known_values(tmp_path: Path) -> None:
    install = make_install(tmp_path / "install")
    resolver = _resolver(tmp_path, install_dir=install, env={"A": "1"}, project_dir=tmp_path)
    known = resolver.variables()
    assert known["A"] == "1" and known["KIPRJMOD"] == str(tmp_path)
    assert known["KICAD10_FOOTPRINT_DIR"] == str(install / "footprints")


TABLE = '(fp_lib_table (version 7) (lib (name "G") (type "KiCad") (uri "/g.pretty")))'


@pytest.mark.parametrize(
    ("system", "relative"),
    [
        ("linux", ".config/kicad/10.0"),
        ("darwin", "Library/Preferences/kicad/10.0"),
        ("win32", "AppData/Roaming/kicad/10.0"),
    ],
)
def test_per_os_configuration_folders(tmp_path: Path, system: str, relative: str) -> None:
    home = tmp_path / "home"
    folder = home / relative
    folder.mkdir(parents=True)
    (folder / "fp-lib-table").write_text(TABLE, encoding="utf-8")
    resolver = _resolver(tmp_path, system=system, home=home)
    assert [(r.nickname, origin) for r, origin, _ in resolver.rows("footprint")] == [("G", "global")]


def test_appdata_and_kicad_config_home(tmp_path: Path) -> None:
    appdata = tmp_path / "appdata"
    (appdata / "kicad" / "10.0").mkdir(parents=True)
    (appdata / "kicad" / "10.0" / "fp-lib-table").write_text(TABLE, encoding="utf-8")
    windows = _resolver(tmp_path, system="win32", env={"APPDATA": str(appdata)})
    assert [r.nickname for r, _, _ in windows.rows("footprint")] == ["G"]
    base = tmp_path / "cfg"
    (base / "9.0").mkdir(parents=True)
    (base / "9.0" / "fp-lib-table").write_text(TABLE, encoding="utf-8")
    via_env = _resolver(tmp_path, target_major=9, env={"KICAD_CONFIG_HOME": str(base)})
    assert [r.nickname for r, _, _ in via_env.rows("footprint")] == ["G"]
    explicit = _resolver(tmp_path, config_home=tmp_path / "empty", env={"KICAD_CONFIG_HOME": str(base)})
    assert explicit.rows("footprint") == ()
