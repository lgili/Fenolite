# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0063 (capability kicad-oracle, "Schematic netlist through the package runner" and
"Own netlists equal kicad-cli's"): the ``netlist-*`` rows of ``_probes.PROBES``.

Every probe runs ``kicad-cli sch export netlist`` on a copy of a project that ``build`` wrote for the
running major. The ``netlist-shape``, ``netlist-power-symbols`` and ``netlist-pintype`` probes read the
export as a plain S-expression tree, so they measure KiCad and not Fenolite's reader. The
``netlist-own-*`` probes compare Fenolite's own netlist of a generated sheet with the export read by
``netlist.read_netlist`` (``H-K-NETLIST-OWN``).
"""

from __future__ import annotations

import runpy
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _erc
import _gencases as gen
import _gendesigns
from _buildhelp import ROOT, blink, build
from _schbuild import built_units, children_of, sheet_of

from fenolite.backends.kicad.cli import NETLIST, KicadCli
from fenolite.backends.kicad.netlist import differences, read_netlist
from fenolite.backends.kicad.sch_netlist import own_netlist
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.dsl import Design
from fenolite.lens.build import BuildOutput

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
NO_CONNECT = "+no_connect"
COMP_ATOMS = ("ref", "value", "footprint")
NODE_ATOMS = ("ref", "pin", "pintype")


def runner() -> KicadCli:
    return gen.runner()


def major() -> int:
    return runner().major()


def project_files(output: BuildOutput) -> dict[str, bytes]:
    """The files of a build without its ``.fenolite/`` cache."""
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def export_of(files: Mapping[str, bytes], schematic: str) -> str:
    """The text of ``sch export netlist`` for ``schematic``, one of ``files``, run on a copy."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        entries = _erc.tops(files, folder)
        others = {name: path for name, path in entries.items() if name != schematic}
        run = runner().export_netlist(folder / schematic, files=others)
    data = run.outputs.get(NETLIST)
    assert run.ok and data is not None, f"no netlist of {schematic}: {run.stderr.strip()}"
    return data.decode("utf-8")


@cache
def output(name: str) -> BuildOutput:
    """The blink or the units design built for the running major."""
    return build(blink(), major()) if name == "blink" else built_units(major())


@cache
def export(name: str) -> str:
    """KiCad's netlist of the built blink or units design."""
    return export_of(project_files(output(name)), f"{gen.stem(name)}.kicad_sch")


def text(node: Node, head: str) -> str | None:
    """The first atom of the child ``head`` of ``node``; ``None`` without the child or the atom."""
    child = node.find(head)
    atoms = child.atoms() if child is not None else ()
    return atoms[0].value if atoms else None


def nodes(root: Node) -> list[Node]:
    nets = root.find("nets")
    return [node for net in (nets.nodes("net") if nets is not None else ()) for node in net.nodes("node")]


def comps(root: Node) -> tuple[Node, ...]:
    listed = root.find("components")
    return listed.nodes("comp") if listed is not None else ()


def shape_outcome() -> str:
    """``equal`` when the export of the built blink holds every head the reader uses, with its atom."""
    root = parse(export("blink"))
    nets = root.find("nets")
    if root.name != "export" or nets is None or not comps(root) or not nets.nodes("net"):
        return "different"
    for comp in comps(root):
        fields = comp.find("fields")
        if any(text(comp, head) is None for head in COMP_ATOMS) or fields is None:
            return "different"
        if any(text(field, "name") is None for field in fields.nodes("field")):
            return "different"
    for net in nets.nodes("net"):
        if text(net, "name") is None or text(net, "class") is None or not net.nodes("node"):
            return "different"
        if any(text(node, head) is None for node in net.nodes("node") for head in NODE_ATOMS):
            return "different"
    return "equal"


def power_symbols_outcome() -> str:
    """``absent`` when no component and no node of the export has a ``#`` reference, although the sheet
    holds power flags."""
    sheet = project_files(output("blink"))["blink.kicad_sch"].decode("utf-8")
    if '"#FLG' not in sheet:
        return "inconclusive"
    root = parse(export("blink"))
    refs = [text(comp, "ref") or "" for comp in comps(root)] + [
        text(node, "ref") or "" for node in nodes(root)
    ]
    return "present" if any(ref.startswith("#") for ref in refs) else "absent"


def expected_pintypes(name: str) -> dict[tuple[str, str], str]:
    """(reference, pad number) → the electrical type of the pin in the built design, with the flag suffix
    for a pin the design marks as not connected."""
    design = output(name).design
    marks = {(m.component_id, m.pin) for m in design.circuit.no_connects}
    found: dict[tuple[str, str], str] = {}
    for component in design.circuit.components:
        pads = dict(component.pin_pad_map)
        for pin in component.pins:
            suffix = NO_CONNECT if (component.id, pin.number) in marks else ""
            found[(component.ref, pads.get(pin.number, pin.number))] = f"{pin.etype}{suffix}"
    return found


def pintypes(name: str) -> dict[tuple[str, str], str]:
    """(reference, pin number) → ``pintype`` in KiCad's export."""
    return {
        (text(node, "ref") or "", text(node, "pin") or ""): text(node, "pintype") or ""
        for node in nodes(parse(export(name)))
    }


@cache
def pintype_outcome() -> str:
    for name in ("blink", "units"):
        if pintypes(name) != expected_pintypes(name):
            return "different"
    return "equal"


# -- the own netlist against the export (H-K-NETLIST-OWN)

EXAMPLES = ROOT / "examples"


def schematic_of(output: BuildOutput) -> str:
    return next(rel for rel in output.files if rel.endswith(".kicad_sch") and "/" not in rel)


def own_differences(output: BuildOutput) -> tuple[str, ...]:
    """What differs between Fenolite's own netlist of the sheet a build generated and KiCad's export of
    the written project; the sheet read back from the written file must give the same own netlist. Pin
    types are compared on a major whose ``netlist-pintype`` probe is ``equal``."""
    assert output.schematic is not None
    name = schematic_of(output)
    project = name.removesuffix(".kicad_sch")
    theirs = read_netlist(export_of(project_files(output), name), file=name)
    ours = own_netlist(output.schematic.sheet, project=project, children=output.schematic.children)
    found = differences(ours, theirs, pintypes=pintype_outcome() == "equal")
    if own_netlist(sheet_of(output), project=project, children=children_of(output)) != ours:
        found = (*found, "the sheets read back from the files give another own netlist")
    return found


def example_scripts() -> list[str]:
    """The folder names under ``examples/`` that hold a ``design.py``."""
    return sorted(path.parent.name for path in EXAMPLES.glob("*/design.py"))


@cache
def example(name: str) -> BuildOutput | None:
    """The example ``name`` built for the running major from its own folder, or ``None`` when it does not
    build for the KiCad target with the libraries of the repository (an example on KiCad's official
    libraries, or one that is only an Altium target)."""
    try:
        made = runpy.run_path(str(EXAMPLES / name / "design.py"))["design"]
        assert isinstance(made, Design)
        output = build(made, major(), project_dir=EXAMPLES / name)
    except Exception:  # noqa: BLE001 - any refusal means "not an example of this set"
        return None
    return output if output.files and output.schematic is not None else None


@cache
def generated(index: int) -> BuildOutput:
    """Design ``index`` of the acceptance sequence, built for the running major."""
    output = build(_gendesigns.design(_gendesigns.SEED, index), major())
    assert output.files, (index, [i.message for i in output.issues if i.severity == "error"])
    return output


def own_outcome(name: str) -> str:
    return "equal" if not own_differences(output(name)) else "different"


def own_generated_outcome() -> str:
    for index in range(_gendesigns.COUNT):
        if own_differences(generated(index)):
            return "different"
    return "equal"


def netlist_probes() -> Probes:
    both = (9, 10)
    return {
        "netlist-shape": (shape_outcome, both),
        "netlist-power-symbols": (power_symbols_outcome, both),
        "netlist-pintype": (pintype_outcome, both),
        "netlist-own-blink": (lambda: own_outcome("blink"), both),
        "netlist-own-units": (lambda: own_outcome("units"), both),
        "netlist-own-generated": (own_generated_outcome, both),
    }


__all__ = [
    "NO_CONNECT",
    "example",
    "example_scripts",
    "expected_pintypes",
    "export",
    "export_of",
    "generated",
    "netlist_probes",
    "own_differences",
    "output",
    "pintypes",
    "project_files",
]
