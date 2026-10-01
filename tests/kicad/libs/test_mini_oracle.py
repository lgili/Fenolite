# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored mini library against kicad-cli (capability kicad-library-read, "Reading evidence").

Fixtures follow the running major: on 10.0 the 10.0 and 9.0 variants, on 9.0 only the ``Mini_v9``
variants. Every run uses an isolated configuration folder, and every output path is a child of
``tmp_path`` that does not exist before the call.
"""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path
from typing import Any

import pytest
from _kicad import cli, major
from _libs import MINI, isolated_kicad_env, kicad

from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.sexpr import load
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends

pytestmark = pytest.mark.needs_kicad


def footprint_libraries(running: int) -> list[str]:
    return ["Mini.pretty", "Mini_v9.pretty"] if running >= 10 else ["Mini_v9.pretty"]


def symbol_libraries(running: int) -> list[str]:
    return ["Mini.kicad_sym", "Mini_v9.kicad_sym"] if running >= 10 else ["Mini_v9.kicad_sym"]


def _copy(name: str, tmp_path: Path) -> Path:
    src, dst = MINI / name, tmp_path / "in" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copyfile(src, dst)
    return dst


def test_footprints_load(tmp_path: Path) -> None:
    env = isolated_kicad_env(tmp_path)
    for name in footprint_libraries(major()):
        lib = _copy(name, tmp_path)
        out = tmp_path / "svg" / name
        out.mkdir(parents=True)
        result = kicad(cli(), env, "fp", "export", "svg", lib, "-o", out)
        assert result.returncode == 0, result.stdout + result.stderr
        expected = sorted(p.stem for p in lib.glob("*.kicad_mod"))
        assert sorted(p.stem for p in out.glob("*.svg")) == expected, name


def test_symbols_load(tmp_path: Path) -> None:
    env = isolated_kicad_env(tmp_path)
    for name in symbol_libraries(major()):
        lib = _copy(name, tmp_path)
        out = tmp_path / "svg" / name
        out.mkdir(parents=True)
        result = kicad(cli(), env, "sym", "export", "svg", lib, "-o", out)
        assert result.returncode == 0, result.stdout + result.stderr
        names = {s.atoms()[0].value for s in load(lib).nodes("symbol")}
        plotted = {p.stem.split("_unit")[0] for p in out.glob("*.svg")}
        assert plotted == names, name


def _plain(entity: Any) -> Any:
    """``entity`` without provenance and ``ext``, recursively for pads, padstacks and graphics."""
    changes: dict[str, Any] = {"provenance": None, "ext": {}}
    for name in ("pads", "graphics"):
        if hasattr(entity, name):
            changes[name] = tuple(_plain(e) for e in getattr(entity, name))
    if getattr(entity, "padstack", None) is not None:
        changes["padstack"] = _plain(entity.padstack)
    return dataclasses.replace(entity, **changes)


def _footprints(folder: Path, library: str) -> dict[str, Any]:
    return {p.stem: _plain(read_footprint(p, library=library)) for p in sorted(folder.glob("*.kicad_mod"))}


def _symbols(path: Path, library: str) -> dict[str, Any]:
    return {s.name: _plain(s) for s in resolve_extends(read_symbol_library(path, library=library))}


def _upgrade(kind: str, src: Path, tmp_path: Path, env: dict[str, str]) -> Path:
    out_dir = tmp_path / "up"
    out_dir.mkdir()
    target = out_dir / src.name
    result = kicad(cli(), env, kind, "upgrade", "--force", src, "-o", target)
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.exists()
    return target


@pytest.mark.parametrize("name", ["Mini.pretty", "Mini_v9.pretty", "Mini.kicad_sym", "Mini_v9.kicad_sym"])
def test_reread_after_upgrade(name: str, tmp_path: Path) -> None:
    running = major()
    if name not in footprint_libraries(running) + symbol_libraries(running):
        pytest.skip(f"{name} is not a fixture of KiCad {running}")
    if name == "Mini_v9.kicad_sym" and running >= 10:
        pytest.skip("covered by test_tilde_after_upgrade")
    env = isolated_kicad_env(tmp_path)
    src = _copy(name, tmp_path)
    if name.endswith(".pretty"):
        upgraded = _upgrade("fp", src, tmp_path, env)
        assert _footprints(upgraded, "Mini") == _footprints(src, "Mini")
    else:
        upgraded = _upgrade("sym", src, tmp_path, env)
        assert _symbols(upgraded, "Mini") == _symbols(src, "Mini")


@pytest.mark.kicad_min_major(10)
def test_tilde_after_upgrade(tmp_path: Path) -> None:
    env = isolated_kicad_env(tmp_path)
    src = _copy("Mini_v9.kicad_sym", tmp_path)
    upgraded = _upgrade("sym", src, tmp_path, env)
    assert '"~"' in src.read_text(encoding="utf-8") and '"~"' not in upgraded.read_text(encoding="utf-8")
    assert _symbols(upgraded, "Mini") == _symbols(src, "Mini")


def test_newer_fixtures_refused(tmp_path: Path) -> None:
    if major() >= 10:
        pytest.skip("the 10.0 fixtures load on KiCad 10; this checks the 9.0 refusal")
    env = isolated_kicad_env(tmp_path)
    for kind, name in (("fp", "Mini.pretty"), ("sym", "Mini.kicad_sym")):
        out = tmp_path / "svg" / name
        out.mkdir(parents=True)
        result = kicad(cli(), env, kind, "export", "svg", _copy(name, tmp_path), "-o", out)
        assert result.returncode != 0, f"KiCad 9 loaded {name}: {result.stdout}"
