# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0060 (capability kicad-oracle, "Schematic components agree with kicad-cli"): the
``sch-components-*`` rows of ``_probes.PROBES``.

Each probe reads a hierarchy with ``sch.sheet_files`` and ``sch.read_schematic``, asks ``kicad-cli`` for
the netlist of a copy, and compares the two sets of ``(ref, value, footprint)``. Only the ``components``
of the netlist are read, and no netlist is stored.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from pathlib import Path

import _netlist
import _schfix

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.cli import NETLIST, KicadCli

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Components = set[tuple[str, str, str]]
FIXTURES: dict[str, tuple[str, str]] = {
    "flat": ("flat.kicad_sch", "flat_v9.kicad_sch"),
    "units": ("units.kicad_sch", "units_v9.kicad_sch"),
    "hier": ("hier/top.kicad_sch", "hier_v9/top.kicad_sch"),
}
"""Probe name → the root file at the 10.0 format and at the 9.0 format."""


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def fixture(name: str) -> Path:
    """The root file of ``name`` in the format of the running major."""
    ten, nine = FIXTURES[name]
    return _schfix.SCHEMATICS / (ten if runner().major() >= 10 else nine)


def exported(root: Path) -> Components | None:
    """The components ``kicad-cli`` lists for the hierarchy under ``root`` (``None`` when it did not load)."""
    tree = sch.sheet_files(root)
    files = {name: root.parent / name for name in tree.files[1:] if not name.startswith("../")}
    run = runner().export_netlist(root, files=files)
    data = run.outputs.get(NETLIST)
    if not run.ok or data is None:
        return None
    return _netlist.components(data.decode("utf-8"))


def read(root: Path, *, on_board_only: bool) -> Components:
    """The components Fenolite reads for the hierarchy under ``root``."""
    found = sch.hierarchy_components(root, on_board_only=on_board_only)
    return {(c.ref, c.value, c.footprint) for c in found}


def by_project(root: Path, *, on_board_only: bool) -> Components:
    """The components of the uses filed under the project named after ``root`` (``sch.components``)."""
    tree = sch.sheet_files(root)
    sheets = [sch.read_schematic(root.parent / name) for name in tree.files if not name.startswith("../")]
    found = sch.components(sheets, project=root.stem, on_board_only=on_board_only)
    return {(c.ref, c.value, c.footprint) for c in found}


def same(ours: Components, theirs: Components) -> bool:
    """Equal sets, a text with a variable (``${…}``) matching any text: ``kicad-cli`` resolves variables
    in the netlist, and the reader keeps them as written."""
    if ours == theirs:
        return True
    listed = {ref: (value, footprint) for ref, value, footprint in theirs}
    if len(listed) != len(theirs) or {ref for ref, _, _ in ours} != set(listed):
        return False
    return all(
        ("${" in value or value == listed[ref][0]) and ("${" in footprint or footprint == listed[ref][1])
        for ref, value, footprint in ours
    )


@cache
def on_board_outcome() -> str:
    """Whether the netlist lists the symbol of the flat sheet that is left off the board (``R3``)."""
    listed = exported(fixture("flat"))
    if listed is None:
        return "inconclusive"
    return "present" if any(ref == "R3" for ref, _, _ in listed) else "absent"


def on_board_only() -> bool:
    """The fallback of design Decision 14: leave such symbols out when the running major does."""
    return on_board_outcome() == "absent"


def compare(root: Path) -> tuple[Components, Components] | None:
    listed = exported(root)
    if listed is None:
        return None
    return read(root, on_board_only=on_board_only()), listed


def components_outcome(name: str) -> str:
    found = compare(fixture(name))
    if found is None:
        return "inconclusive"
    ours, theirs = found
    if by_project(fixture(name), on_board_only=on_board_only()) != ours:
        return "different"
    return "equal" if ours == theirs else "different"


def sch_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {
        f"sch-components-{name}": (lambda name=name: components_outcome(name), both) for name in FIXTURES
    }
    probes["sch-components-on-board"] = (on_board_outcome, both)
    return probes


__all__ = [
    "FIXTURES",
    "by_project",
    "compare",
    "components_outcome",
    "fixture",
    "on_board_only",
    "on_board_outcome",
    "same",
    "sch_probes",
]
