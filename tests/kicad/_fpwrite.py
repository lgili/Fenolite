# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Written footprint libraries against ``kicad-cli`` (capability kicad-library-read, "Footprint files
written by Fenolite read back equal"; change c0018).

Every run goes through the package runner (``KicadCli.run`` with ``files``) on copies, and results are
read from ``CliRun.outputs``. The functions here back the ``fp-write-*`` ids of ``_probes.PROBES``.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.mod import read_footprint, write_pretty
from fenolite.core.errors import Issue
from fenolite.model.library import FootprintDef

ROOT = Path(__file__).resolve().parents[2]
LIBS = ROOT / "tests" / "data" / "libs"
ESCAPES = LIBS / "Escapes_v9.pretty" / "Mini_Escapes.kicad_mod"
ENCODER_VALUES = ['quote " here', "back\\slash", "line\nfeed", "carriage\rreturn", "tab\there", "vt\x0bhere",
                  "ctrl\x01here", "non-ASCII éü 日本 Ω"]  # fmt: skip
"""The encoder values of ``tests/kicad/test_sexpr_oracle.py`` (the 10.0 proof of H-K-SEXPR-ESCAPES)."""


def plain(entity: Any) -> Any:
    """``entity`` without provenance and ``ext``, recursively for pads, padstacks and graphics."""
    changes: dict[str, Any] = {"provenance": None, "ext": {}}
    for name in ("pads", "graphics"):
        if hasattr(entity, name):
            changes[name] = tuple(plain(e) for e in getattr(entity, name))
    if getattr(entity, "padstack", None) is not None:
        changes["padstack"] = plain(entity.padstack)
    return dataclasses.replace(entity, **changes)


def definitions(folder: str, library: str = "Mini") -> tuple[FootprintDef, ...]:
    return tuple(read_footprint(p, library=library) for p in sorted((LIBS / folder).glob("*.kicad_mod")))


def escapes() -> FootprintDef:
    """``Mini_Escapes`` with its description set through the model to the eight encoder values."""
    defn = read_footprint(ESCAPES, library="Escapes")
    return dataclasses.replace(defn, description="".join(ENCODER_VALUES))


@dataclass(frozen=True)
class LibraryRun:
    """A written library after ``fp export svg`` and ``fp upgrade --force``."""

    loaded: bool
    svgs: int
    upgraded: dict[str, FootprintDef]
    issues: tuple[Issue, ...]


def check(
    runner: KicadCli, defs: Sequence[FootprintDef], target: int, *, allow_lossy: bool = False
) -> LibraryRun:
    """Write ``defs`` as ``<library>.pretty`` for ``target``, load it, re-save it and read it back."""
    library = defs[0].library
    name = f"{library}.pretty"
    issues: list[Issue] = []
    texts = write_pretty(defs, target=target, allow_lossy=allow_lossy, issues=issues)
    with tempfile.TemporaryDirectory() as tmp:
        folder, empty = Path(tmp) / name, Path(tmp) / "empty"
        folder.mkdir()
        empty.mkdir()
        for file, text in texts.items():
            (folder / file).write_text(text, encoding="utf-8")
        files = {name: folder, "svg": empty, "up": empty}
        shown = runner.run(["fp", "export", "svg", name, "-o", "svg"], files=files)
        upgrade = runner.run(["fp", "upgrade", "--force", name, "-o", f"up/{name}"], files=files)
    svgs = sum(1 for rel in shown.outputs if rel.startswith("svg/") and rel.endswith(".svg"))
    prefix = f"up/{name}/"
    upgraded = {
        rel[len(prefix) : -len(".kicad_mod")]: read_footprint(data.decode("utf-8"), library=library)
        for rel, data in upgrade.outputs.items()
        if rel.startswith(prefix) and rel.endswith(".kicad_mod")
    }
    return LibraryRun(shown.ok and svgs == len(texts), svgs, upgraded, tuple(issues))


def equal_after_upgrade(result: LibraryRun, defs: Sequence[FootprintDef]) -> bool:
    if set(result.upgraded) != {d.name for d in defs}:
        return False
    return all(plain(result.upgraded[d.name]) == plain(d) for d in defs)


@cache
def mini(runner: KicadCli, folder: str, target: int, allow_lossy: bool = False) -> LibraryRun:
    return check(runner, definitions(folder), target, allow_lossy=allow_lossy)


@cache
def escapes_run(runner: KicadCli) -> LibraryRun:
    return check(runner, [escapes()], 9)


def escapes_equal(runner: KicadCli) -> bool:
    defn = escapes()
    again = escapes_run(runner).upgraded.get(defn.name)
    return again is not None and again.properties == defn.properties and again.description == defn.description


__all__ = [
    "ENCODER_VALUES",
    "LibraryRun",
    "check",
    "definitions",
    "equal_after_upgrade",
    "escapes",
    "escapes_equal",
    "escapes_run",
    "mini",
    "plain",
]
