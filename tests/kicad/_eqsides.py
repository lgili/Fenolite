# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic side of ``equivalent`` against ``kicad-cli`` (change c0158; hypothesis
``H-K-EQ-SCHSIDE``; capability design-equivalence, "Schematic sides" and "Fitted flag of a schematic
side").

A schematic side reads its netlist from Fenolite's own netlist when the sheets pass its grammar check, else
from ``kicad-cli sch export netlist``. For the projects ``build`` writes, both are available: the probe
``equiv-schside`` is ``equal`` when the two circuits that ``fenolite.api.sides.netlist_design`` builds from
them hold the same components (reference, value) and the same ``REF-PIN`` partition, and when KiCad's
export marks a do-not-populate symbol, and only that one, with a ``property`` named ``dnp`` without a
value (the field the side reads).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path

import _erc
import _gencases as gen
import _netlistcases as cases

from fenolite.api.sides import DNP, netlist_design
from fenolite.backends.kicad import oracle, parity_inputs
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.netlist import KicadNetlist
from fenolite.checks.equivalence import compare_designs

GENERATED = ("blink", "units")
FIELD = "dnp"
"""The name of the ``property`` that marks a do-not-populate component in the export (task 1.1)."""


def _runner() -> KicadCli:
    return cases.runner()


def sides(files: dict[str, bytes], schematic: str) -> tuple[KicadNetlist, KicadNetlist, frozenset[str]]:
    """The own netlist and ``kicad-cli``'s export of ``schematic`` (one of ``files``), and the references
    the export marks with ``dnp``."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        _erc.tops(files, folder)
        root = folder / schematic
        sheets = parity_inputs.read_sheets(root)
        assert not parity_inputs.grammar_issues(sheets), schematic
        own = parity_inputs.own_netlist(sheets, project=root.stem)
        export = oracle.export_netlist_of(_runner(), schematic, oracle.with_sheets(root, {}))
    assert export.netlist is not None, export.message
    marked = frozenset(c.ref for c in export.netlist.components if FIELD in c.flags)
    return own, export.netlist, marked


def circuit_differences(own: KicadNetlist, exported: KicadNetlist) -> list[str]:
    """What levels 1 and 2 report between the circuits of the two netlists."""
    report = compare_designs(netlist_design(own, "own"), netlist_design(exported, "export"), level=2)
    return [f"{d.kind} {d.where}: {d.a!r} / {d.b!r}" for d in report.differences]


@cache
def generated(name: str) -> tuple[list[str], frozenset[str]]:
    """For the built blink or units design: the circuit differences and the references marked ``dnp``."""
    files = cases.project_files(cases.output(name))
    own, exported, marked = sides(dict(files), f"{gen.stem(name)}.kicad_sch")
    return circuit_differences(own, exported), marked


@cache
def marked_blink() -> tuple[str, frozenset[str], frozenset[str]]:
    """The built blink with its first placed symbol turned ``(dnp yes)``: that symbol's reference, the
    references the export marks with ``dnp``, and those the own side reads as not fitted."""
    files = dict(cases.project_files(cases.output("blink")))
    text = files["blink.kicad_sch"].decode("utf-8")
    first = text.index("(dnp no)", text.index("(lib_id"))
    files["blink.kicad_sch"] = (text[:first] + "(dnp yes)" + text[first + len("(dnp no)") :]).encode("utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        _erc.tops(files, folder)
        sheets = parity_inputs.read_sheets(folder / "blink.kicad_sch")
        flags = parity_inputs.symbol_flags(sheets, "blink")
    own_marked = frozenset(ref for ref, held in flags.items() if DNP in held)
    _, _, marked = sides(files, "blink.kicad_sch")
    (ref,) = own_marked
    return ref, marked, own_marked


def schside_outcome() -> str:
    """``equal`` when both generated designs give the same circuit through either netlist, no component is
    marked without a ``(dnp yes)`` symbol, and the marked blink's one symbol is marked by both sides."""
    for name in GENERATED:
        found, marked = generated(name)
        if found or marked:
            return "different"
    ref, marked, own_marked = marked_blink()
    return "equal" if marked == own_marked == frozenset({ref}) else "different"


def eq_side_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    return {"equiv-schside": (schside_outcome, (9, 10))}


__all__ = ["FIELD", "circuit_differences", "eq_side_probes", "generated", "marked_blink", "schside_outcome"]
