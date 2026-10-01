# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored mini library (``tests/data/libs``) and helpers for library tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fenolite.backends.kicad.sexpr import Node, dumps, load

MINI = Path(__file__).resolve().parent / "data" / "libs"


def make_symdir(src: Path, dst: Path) -> Path:
    """Write every top-level symbol of the library file ``src`` to ``dst/<name>.kicad_sym``.

    Each file keeps the header of ``src`` (version, generator, generator_version) and holds one
    symbol, the layout of a ``.kicad_symdir`` folder. ``dst`` must not exist yet.
    """
    root = load(src)
    header = [c for c in root.children if not (isinstance(c, Node) and c.name == "symbol")]
    dst.mkdir(parents=True)
    for symbol in root.nodes("symbol"):
        name = symbol.atoms()[0].value
        (dst / f"{name}.kicad_sym").write_text(dumps(root.with_children([*header, symbol])), encoding="utf-8")
    return dst


def isolated_kicad_env(tmp_path: Path) -> dict[str, str]:
    """An environment for kicad-cli whose configuration folder is a new empty folder under ``tmp_path``.

    KiCad library variables of the caller's environment are removed, so user tables and paths cannot
    affect a run.
    """
    config = tmp_path / "kicad-config"
    config.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("KICAD", "KIPRJMOD"))}
    env.update({"KICAD_CONFIG_HOME": str(config), "LANG": "C", "LC_ALL": "C"})
    return env


def kicad(cli: str, env: dict[str, str], *args: str | Path) -> subprocess.CompletedProcess[str]:
    """Run kicad-cli with ``env`` and return the result whatever the exit code."""
    return subprocess.run(
        [cli, *map(str, args)], capture_output=True, text=True, check=False, timeout=600, env=env
    )


def make_install(root: Path, version: int = 20251024, *, template: dict[str, str] | None = None) -> Path:
    """A fake KiCad install folder: one symbol library header and the standard sub-folders."""
    for sub in ("footprints", "symbols", "3dmodels", "template"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    header = f'(kicad_symbol_lib\n\t(version {version})\n\t(generator "fenolite-tests")\n)\n'
    (root / "symbols" / "Fake.kicad_sym").write_text(header, encoding="utf-8")
    for name, text in (template or {}).items():
        (root / "template" / name).write_text(text, encoding="utf-8")
    return root
