# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where optional external resources live on this machine (KiCad, its libraries, the corpus)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from functools import cache
from pathlib import Path

import pytest

MACOS_KICAD = Path("/Applications/KiCad/KiCad.app/Contents")
LINUX_KICAD = Path("/usr/share/kicad")
LIB_ENV = ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR")
MODEL_ENV = ("KICAD10_3DMODEL_DIR", "KICAD9_3DMODEL_DIR")
CORPUS_HINT = "run: uv run python tools/corpus_fetch.py"
LIBS_HINT = (
    "official KiCad libraries not found: set KICAD10_FOOTPRINT_DIR and KICAD10_SYMBOL_DIR, "
    "install KiCad (FENOLITE_KICAD_INSTALL_DIR names an install outside the default location), "
    "or run: uv run python tools/kicad_libs_fetch.py"
)

posix_tools = pytest.mark.skipif(sys.platform == "win32", reason="posix-only fake tool")
"""The one way to skip, on Windows, a test whose fake tool is a ``#!/bin/sh`` script (capability
ci-baseline, "Unit CI job on two operating systems"). The count of these skips is part of the release
record (``H-G-REL-WINDOWS``)."""


def fake_tool(script: Path, program: Path) -> Path:
    """Write the launcher of a fake tool: ``script`` runs ``program`` with this interpreter. On Windows
    the launcher is ``<script>.cmd``, which a process can start by its path as it starts the shell
    script elsewhere. Returns the path to run."""
    if sys.platform == "win32":
        launcher = script.with_name(script.name + ".cmd")
        launcher.write_text(f'@"{sys.executable}" "{program}" %*\r\n', encoding="utf-8")
        return launcher
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{program}" "$@"\n', encoding="utf-8")
    script.chmod(0o755)
    return script


def corpus_cache_dir() -> Path:
    override = os.environ.get("FENOLITE_CORPUS_CACHE")
    return Path(override) if override else Path.home() / ".cache" / "fenolite" / "corpus"


def _default_installs() -> list[Path]:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "KiCad"
        return [base / f"{major}.0" / "share" / "kicad" for major in (10, 9)]
    return [MACOS_KICAD / "SharedSupport"] if sys.platform == "darwin" else [LINUX_KICAD]


def kicad_install_dir() -> Path | None:
    """The local KiCad share folder: ``FENOLITE_KICAD_INSTALL_DIR`` when set (``None`` if that path is
    missing), else the per-OS default location."""
    override = os.environ.get("FENOLITE_KICAD_INSTALL_DIR")
    if override:
        return Path(override) if Path(override).is_dir() else None
    return next((d for d in _default_installs() if d.is_dir()), None)


def libs_cache_dir() -> Path:
    """The library cache of the tests and of the fetch tool: ``FENOLITE_LIBS_CACHE``, else
    ``~/.cache/fenolite/libs``."""
    from fenolite.backends.kicad.libcache import default_cache_dir

    return default_cache_dir()


def verified_cache_dirs() -> list[Path]:
    """The ``kicad-footprints`` and ``kicad-symbols`` folders of the cache whose stamp equals their pin."""
    from fenolite.backends.kicad.libcache import verified_folders

    cache = libs_cache_dir()
    return [folder for _, folder in verified_folders(cache)] if cache.is_dir() else []


def kicad_library_dirs() -> list[Path]:
    """Official KiCad library folders: ``KICAD9_*``/``KICAD10_*`` footprint and symbol folders, else the
    ``footprints``, ``symbols`` and ``3dmodels`` folders of the local install; then the verified folders
    of the library cache."""
    named = [Path(os.environ[v]) for v in LIB_ENV if os.environ.get(v)]
    named = [d for d in named if d.is_dir()]
    if named:
        found = named + [
            Path(os.environ[v]) for v in MODEL_ENV if os.environ.get(v) and Path(os.environ[v]).is_dir()
        ]
    else:
        install = kicad_install_dir()
        folders = (
            () if install is None else (install / "footprints", install / "symbols", install / "3dmodels")
        )
        found = [d for d in folders if d.is_dir()]
    return found + verified_cache_dirs()


FREEROUTING_ENV = "FENOLITE_FREEROUTING_JAR"
FREEROUTING_HINT = (
    f"Freerouting jar not found: set {FREEROUTING_ENV} to the pinned freerouting jar "
    "(installed outside the repository; docs/evidence/routing.md)"
)


def freerouting_jar() -> Path | None:
    """The Freerouting jar named by ``FENOLITE_FREEROUTING_JAR``, or ``None`` when the variable is unset or
    names no file. The suites download nothing: ``fenolite fetch freerouting --confirm`` installs the jar,
    and the gate reads it through this variable."""
    named = os.environ.get(FREEROUTING_ENV, "")
    return Path(named) if named and Path(named).is_file() else None


def required_resources() -> set[str]:
    """Resources listed in ``FENOLITE_REQUIRE`` (``kicad``, ``corpus``, ``libs``, ``freerouting``;
    comma-separated)."""
    return {r.strip() for r in os.environ.get("FENOLITE_REQUIRE", "").split(",") if r.strip()}


def kicad_cli() -> str | None:
    """``FENOLITE_KICAD_CLI`` when set (``None`` if that file is missing), else PATH, else the macOS app
    (``fenolite.backends.kicad.cli.find_kicad_cli``)."""
    from fenolite.backends.kicad.cli import find_kicad_cli

    found = find_kicad_cli()
    return None if found is None else str(found)


@cache
def _version_of(cli: str) -> tuple[int, int, int] | None:
    try:
        out = subprocess.run(
            [cli, "version"], capture_output=True, text=True, timeout=120, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None


def kicad_cli_version() -> tuple[int, int, int] | None:
    """The running kicad-cli version as (major, minor, patch), parsed once; None without kicad-cli."""
    cli = kicad_cli()
    return None if cli is None else _version_of(cli)


def kicad_cli_major() -> int | None:
    """The major version of the running kicad-cli (``kicad_cli_version()[0]``), or None without one."""
    version = kicad_cli_version()
    return None if version is None else version[0]
