# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path variables and configuration folders (kicad-library-resolution, "Path variable expansion"), with
KiCad's own configured variables read only on request (c0021)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _libs import make_install, verified_cache

from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import COMMON_FILE, LibraryConfig, LibraryResolver
from fenolite.core.errors import FormatError


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
    assert "MY_LIBS" in issue.hint and "LibraryConfig.read_common" in issue.hint


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


def test_relative_results_join_the_project_folder(tmp_path: Path) -> None:
    """``kicad-cli`` resolves a relative uri against its working directory, whatever table holds the row
    (``H-K-LIB-RELPATH-2``). The resolver uses the project folder for it, and leaves the path relative
    when no project folder is known."""
    project = tmp_path / "project"
    nested = str(project / "nested" / "fp-lib-table")
    elsewhere = str(tmp_path / "config" / "10.0" / "fp-lib-table")
    resolver = _resolver(tmp_path, project_dir=project)
    for table in (str(project / "fp-lib-table"), nested, elsewhere):
        assert Path(resolver.expand("../Lib.pretty", row_table=table)) == tmp_path / "Lib.pretty"
        assert Path(resolver.expand("Lib.pretty", row_table=table)) == project / "Lib.pretty"
    assert resolver.expand("/abs/Lib.pretty", row_table=nested) == "/abs/Lib.pretty"
    without = _resolver(tmp_path)
    assert without.expand("sub/../Lib.pretty", row_table=nested) == "Lib.pretty"


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


# -- KiCad's configured path variables (c0021)


def _common(tmp_path: Path, content: object, major: str = "10.0") -> Path:
    config = tmp_path / "cfg"
    (config / major).mkdir(parents=True, exist_ok=True)
    text = content if isinstance(content, str) else json.dumps(content)
    (config / major / COMMON_FILE).write_text(text, encoding="utf-8")
    return config


def _vars(**values: str) -> dict[str, object]:
    return {"environment": {"vars": values}}


def test_kicads_configuration_is_read_only_on_request(tmp_path: Path) -> None:
    config = _common(tmp_path, _vars(MY_LIBS="/common"))
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path, config_home=config).expand("${MY_LIBS}/X.pretty")
    assert caught.value.issue.code == "kicad.lib.unresolved-variable"
    assert "LibraryConfig.read_common" in caught.value.hint
    on = _resolver(tmp_path, config_home=config, read_common=True)
    assert on.expand("${MY_LIBS}/X.pretty") == "/common/X.pretty"
    assert on.variables()["MY_LIBS"] == "/common"


def test_process_environment_wins_over_kicads_configuration(tmp_path: Path) -> None:
    config = _common(tmp_path, _vars(MY_LIBS="/common"))
    resolver = _resolver(tmp_path, config_home=config, read_common=True, env={"MY_LIBS": "/env"})
    assert resolver.expand("${MY_LIBS}") == "/env" and resolver.variables()["MY_LIBS"] == "/env"


def test_kicads_configuration_wins_over_the_source_default(tmp_path: Path) -> None:
    install = make_install(tmp_path / "install")
    config = _common(tmp_path, _vars(KICAD10_FOOTPRINT_DIR="/common"))
    resolver = _resolver(tmp_path, config_home=config, read_common=True, install_dir=install)
    assert resolver.expand("${KICAD10_FOOTPRINT_DIR}") == "/common"
    assert Path(resolver.expand("${KICAD10_SYMBOL_DIR}")) == install / "symbols"


def test_only_the_target_majors_file_is_read(tmp_path: Path) -> None:
    config = _common(tmp_path, _vars(MY_LIBS="/nine"), major="9.0")
    with pytest.raises(LibraryError) as caught:
        _resolver(tmp_path, config_home=config, read_common=True).expand("${MY_LIBS}")
    assert caught.value.issue.code == "kicad.lib.unresolved-variable"
    assert "read_common" not in caught.value.hint  # the file was asked for; the name is simply not set
    nine = _resolver(tmp_path, config_home=config, read_common=True, target_major=9)
    assert nine.expand("${MY_LIBS}") == "/nine"


@pytest.mark.parametrize(
    ("content", "pointer"),
    [
        ({"environment": {"vars": ["x"]}}, "/environment/vars"),
        ({"environment": {"vars": {"A": 1}}}, "/environment/vars/A"),
        ({"environment": []}, "/environment"),
        ([1], "/"),
        ("{not json", "/"),
    ],
)
def test_malformed_configuration_file(tmp_path: Path, content: object, pointer: str) -> None:
    config = _common(tmp_path, content)
    with pytest.raises(FormatError) as caught:
        _resolver(tmp_path, config_home=config, read_common=True).expand("${MY_LIBS}")
    assert caught.value.file == str(config / "10.0" / COMMON_FILE) and caught.value.locator == pointer
    # a name that the environment defines never reaches the file
    env = _resolver(tmp_path, config_home=config, read_common=True, env={"MY_LIBS": "/env"})
    assert env.expand("${MY_LIBS}") == "/env"


@pytest.mark.parametrize("content", [{}, {"environment": {}}, {"environment": {"vars": None}}, None])
def test_no_variables_without_content(tmp_path: Path, content: object) -> None:
    config = tmp_path / "cfg" if content is None else _common(tmp_path, content)
    with pytest.raises(LibraryError):
        _resolver(tmp_path, config_home=config, read_common=True).expand("${MY_LIBS}")


def test_values_are_used_as_written_and_the_file_is_read_once(tmp_path: Path) -> None:
    config = _common(tmp_path, _vars(A="${B}/x", B="/b"))
    resolver = _resolver(tmp_path, config_home=config, read_common=True)
    assert resolver.expand("${A}") == "${B}/x"  # no expansion inside a value
    (config / "10.0" / COMMON_FILE).write_text(json.dumps(_vars(A="/changed")), encoding="utf-8")
    assert resolver.expand("${A}") == "${B}/x"


def test_cache_defaults_rank_between_environment_and_install(tmp_path: Path) -> None:
    install = make_install(tmp_path / "install")
    cache = verified_cache(tmp_path / "cache", "10.0.6", "kicad-footprints")
    resolver = _resolver(tmp_path, cache_dir=cache, install_dir=install)
    assert Path(resolver.expand("${KICAD10_FOOTPRINT_DIR}")) == cache / "10.0.6" / "kicad-footprints"
    for name in ("KICAD10_3DMODEL_DIR", "KICAD10_TEMPLATE_DIR", "KICAD10_SYMBOL_DIR"):
        with pytest.raises(LibraryError) as caught:  # only verified subfolders; no models, no templates
            resolver.expand(f"${{{name}}}")
        assert caught.value.issue.code == "kicad.lib.unresolved-variable"
    env = _resolver(tmp_path, cache_dir=cache, env={"KICAD10_FOOTPRINT_DIR": "/env"})
    assert env.expand("${KICAD10_FOOTPRINT_DIR}") == "/env"
