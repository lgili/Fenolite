# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stack-up benches (capability kicad-oracle, "Stack-up job file parity"; change c0101).

Created 50 × 30 mm boards with one track per copper layer, written by ``write_board`` for a major, with
the stack-up of each case written by the writer or, for a node Fenolite does not write, put into ``setup``
by token edit. A run exports ``F.Cu`` alone and reads the Gerber job file ``<stem>-job.gbrjob`` that
``kicad-cli pcb export gerbers`` writes beside the Gerbers (S-0020, S-0029; the job file format: S-0125).

``COUNTS`` holds the copper counts that ``created_layers`` gives today: six and eight join when change
c0100 is on the branch. The module lives beside the other benches that have a hermetic half
(``tests/unit/backends/kicad/test_stackbench.py``); the oracle half is
``tests/kicad/board/test_stackup_oracle.py``.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable, Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

from _boards import bare_board, four_layer_stackup, stack_entry, stack_of
from _buildhelp import BLINK, blink, blink_text, build

from fenolite.backends.kicad import stackup as stacklib
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse, tree_equal
from fenolite.core.errors import Issue
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import stack, to_model
from fenolite.exports.plan import run_kind
from fenolite.model.board import Layer, StackLayer, Stackup

PROJECT = "{}\n"
STEM = "bench"
JOB = f"{STEM}-job.gbrjob"
WANTED_COUNTS: tuple[int, ...] = (2, 4, 6, 8)
INCOMPLETE: tuple[str, ...] = ("physical", "nosilk", "fewer", "more", "names", "twodiel", "nopaste")
"""The node cases KiCad ignores (``pcb-stackup-incomplete-<case>``, expected ``absent``)."""
USED: tuple[str, ...] = ("order", "nopaste-table")
"""The node cases KiCad uses (``pcb-stackup-<case>``, expected ``present``)."""
GENERAL_MM = Fraction(16, 10)
"""The board thickness of a bench without a stack-up (``pcb.DEFAULT_THICKNESS``)."""


def _layers(count: int) -> tuple[Layer, ...] | None:
    try:
        return created_layers(count)  # type: ignore[arg-type]
    except ValueError:
        return None


COUNTS: tuple[int, ...] = tuple(n for n in WANTED_COUNTS if _layers(n) is not None)
"""The copper counts a bench exists for on this branch."""


def bench_stackup(count: int) -> Stackup:
    """The stack-up a job bench writes. Together they hold a dielectric of two sheets, a colour, a mask of
    thickness 0 (two layers: the stack-up names no mask), an empty finish and a named one."""
    if count == 2:
        return stack_of(
            stack_entry("F.Cu", "copper", 35_000),
            stack_entry("dielectric 1", "dielectric", 1_500_000, dielectric_kind="core", material="FR4"),
            stack_entry("B.Cu", "copper", 35_000),
        )
    if count == 4:
        return four_layer_stackup(outer=False)
    layers = _layers(count)
    assert layers is not None
    names = stacklib.copper_names(layers)
    entries: list[StackLayer] = [stack_entry("F.Mask", "soldermask", 10_000, color="Blue")]
    for k, name in enumerate(names):
        outer = k in (0, len(names) - 1)
        entries.append(stack_entry(name, "copper", 35_000 if outer else 17_500))
        if k < len(names) - 1:
            kind = "core" if k % 2 else "prepreg"
            thickness = 200_000 if kind == "core" else 110_000
            entries.append(
                stack_entry(f"dielectric {k + 1}", "dielectric", thickness, dielectric_kind=kind,
                            material="FR4", epsilon_r="4.5", loss_tangent="0.02")
            )  # fmt: skip
    entries.append(stack_entry("B.Mask", "soldermask", 10_000, color="Blue"))
    return stack_of(*entries, finish="HAL lead-free", impedance_controlled=count == 8)


def job_text(count: int, target: int) -> str:
    """The job bench of ``count`` copper layers, written for ``target``."""
    return write_board(bare_board(count, bench_stackup(count)), target=target).text  # type: ignore[arg-type]


def default_text(count: int, target: int) -> str:
    """The bench of ``count`` copper layers without a stack-up node (``general`` thickness 1.6 mm)."""
    return write_board(bare_board(count), target=target).text  # type: ignore[arg-type]


# -- token edits


def _name(row: Node) -> str:
    first = row.children[0]
    assert isinstance(first, Atom)
    return first.value


def _is_row(child: Node | Atom, *names: str) -> bool:
    return isinstance(child, Node) and child.name == "layer" and (not names or _name(child) in names)


def _swap_node(root: Node, change: Callable[[Node], Node]) -> Node:
    setup = root.find("setup")
    assert setup is not None
    node = setup.find("stackup")
    assert node is not None
    new_setup = setup.with_children(change(node) if c is node else c for c in setup.children)
    return root.with_children(new_setup if c is setup else c for c in root.children)


def _without_rows(*suffixes: str) -> Callable[[Node], Node]:
    def change(node: Node) -> Node:
        return node.with_children(
            c
            for c in node.children
            if not (_is_row(c) and _name(c).split(".")[-1] in suffixes)  # type: ignore[arg-type]
        )

    return change


def _replace_row(name: str, fragment: str) -> Callable[[Node], Node]:
    new = parse(f"(x {fragment})").children

    def change(node: Node) -> Node:
        out: list[Node | Atom] = []
        for child in node.children:
            out.extend(new if _is_row(child, name) else [child])
        return node.with_children(out)

    return change


def _order(node: Node) -> Node:
    """Silkscreen after mask on the top side: the rows ``F.Paste``, ``F.Mask``, ``F.SilkS``."""
    children = list(node.children)
    at = {_name(c): k for k, c in enumerate(children) if _is_row(c)}  # type: ignore[arg-type]
    silk, paste, mask = children[at["F.SilkS"]], children[at["F.Paste"]], children[at["F.Mask"]]
    children[at["F.SilkS"]], children[at["F.Paste"]], children[at["F.Mask"]] = paste, mask, silk
    return node.with_children(children)


def _no_paste_table(root: Node) -> Node:
    table = root.find("layers")
    assert table is not None
    kept = [
        c
        for c in table.children
        if not (
            isinstance(c, Node)
            and any(isinstance(a, Atom) and a.value.endswith(".Paste") for a in c.children)
        )
    ]
    assert len(kept) == len(table.children) - 2
    return root.with_children(table.with_children(kept) if c is table else c for c in root.children)


COPPER_ROW = '(layer "{name}" (type "copper") (thickness 0.0175))'
MORE = (
    COPPER_ROW.format(name="In2.Cu")
    + ' (layer "dielectric 8" (type "core") (thickness 0.1)) '
    + COPPER_ROW.format(name="In3.Cu")
    + ' (layer "dielectric 9" (type "prepreg") (thickness 0.1)) '
    + COPPER_ROW.format(name="In4.Cu")
)
TWO_DIELECTRICS = (
    '(layer "dielectric 3" (type "prepreg") (thickness 0.1))'
    ' (layer "dielectric 4" (type "prepreg") (thickness 0.1))'
)


def _names(node: Node) -> Node:
    """The copper rows named ``Top``, ``Mid1``, ``Mid2`` and ``Bottom``."""
    renamed = {"F.Cu": "Top", "In1.Cu": "Mid1", "In2.Cu": "Mid2", "B.Cu": "Bottom"}
    return node.with_children(
        c.with_children([Atom.string(renamed[_name(c)]), *c.children[1:]]) if _is_row(c, *renamed) else c  # type: ignore[union-attr, arg-type]
        for c in node.children
    )


def case_text(case: str, target: int) -> str:
    """The four-layer job bench with the node of ``case`` (one of ``INCOMPLETE`` or ``USED``)."""
    root = parse(job_text(4, target))
    edits: Mapping[str, Callable[[Node], Node]] = {
        "physical": _without_rows("SilkS", "Paste", "Mask"),
        "nosilk": _without_rows("SilkS", "Paste"),
        "fewer": lambda node: node.with_children(
            c for c in node.children if not _is_row(c, "In1.Cu", "In2.Cu", "dielectric 2", "dielectric 3")
        ),
        "more": _replace_row("In2.Cu", MORE),
        "names": _names,
        "twodiel": _replace_row("dielectric 3", TWO_DIELECTRICS),
        "nopaste": lambda node: node,
        "order": _order,
        "nopaste-table": _without_rows("Paste"),
    }
    root = _swap_node(root, edits[case])
    if case in ("nopaste", "nopaste-table"):
        root = _no_paste_table(root)
    return dumps(root)


RESAVE_DEFAULTS = (
    '(stackup (layer "F.SilkS" (type "Top Silk Screen")) (layer "F.Paste" (type "Top Solder Paste"))'
    ' (layer "F.Mask" (type "Top Solder Mask")) (layer "F.Cu" (type "copper"))'
    ' (layer "dielectric 1" (thickness 1.51)) (layer "B.Cu" (type "copper") (thickness 0.035))'
    ' (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))'
    ' (layer "B.Paste" (type "Bottom Solder Paste")) (layer "B.SilkS" (type "Bottom Silk Screen")))'
)
"""A node whose top mask and top copper rows hold no thickness, whose dielectric row holds a thickness
alone (no type, material or decimals), and that has no tail."""


def resave_defaults_text(target: int) -> str:
    root = parse(job_text(2, target))
    return dumps(_swap_node(root, lambda node: parse(RESAVE_DEFAULTS)))


def thin_general_text(target: int) -> str:
    """The four-layer job bench with ``general`` thickness 1.6 mm, where its rows sum to 2.025 mm."""
    text = job_text(4, target)
    assert text.count("(thickness 2.025)") == 1
    return text.replace("(thickness 2.025)", "(thickness 1.6)")


def reader_verdict(text: str) -> tuple[bool, list[str]]:
    """Whether ``read_board`` gives the board a stack-up, and the ``kicad.board.stackup-*`` codes."""
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    assert design.board is not None
    codes = [i.code for i in issues if i.code.startswith("kicad.board.stackup-")]
    return design.board.stackup is not None, codes


# -- the job file


def export_job(cli: KicadCli, text: str) -> dict[str, Any] | None:
    """The job file of ``pcb export gerbers -l F.Cu`` on a copy of the board ``text``, or ``None``."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / f"{STEM}.kicad_pcb"
        board.write_text(text, encoding="utf-8", newline="\n")
        project = board.with_suffix(".kicad_pro")
        project.write_text(PROJECT, encoding="utf-8")
        run = cli.export(
            ["pcb", "export", "gerbers", "-l", "F.Cu", "-o", "out/"], board, files={project.name: project},
            out="out",
        )  # fmt: skip
    data = next((d for name, d in run.outputs.items() if name.endswith(JOB)), None)
    return json.loads(data.decode("utf-8")) if data is not None else None


def _mm(nm: int) -> Fraction:
    return Fraction(nm, 1_000_000)


def _close(found: object, wanted: Fraction, tolerance: Fraction = Fraction(1, 10**7)) -> bool:
    return isinstance(found, (int, float)) and abs(Fraction(str(found)) - wanted) <= tolerance


JOB_TYPES = {"silkscreen": "Legend", "solderpaste": "SolderPaste", "soldermask": "SolderMask",
             "copper": "Copper", "dielectric": "Dielectric"}  # fmt: skip


def job_differences(job: Mapping[str, Any], stackup: Stackup, layers: tuple[Layer, ...]) -> list[str]:
    """What the job file states otherwise than ``complete(stackup, layers)`` (empty: ``equal``): one
    ``MaterialStackup`` entry per row and sheet with its thickness, material and colour, the dielectric
    constant and loss tangent exactly under ``impedance_controlled``, and in ``GeneralSpecs`` the board
    thickness, the finish and the impedance flag."""
    done = stacklib.complete(stackup, layers)
    found: list[Mapping[str, Any]] = list(job.get("MaterialStackup", ()))
    if len(found) != len(done.layers):
        return [f"{len(found)} entries for {len(done.layers)} rows and sheets"]
    out: list[str] = []
    for k, (entry, stated) in enumerate(zip(done.layers, found, strict=True)):
        where = f"entry {k} ({entry.name})"
        if stated.get("Type") != JOB_TYPES[entry.kind]:
            out.append(f"{where}: type {stated.get('Type')!r}")
        thick = entry.kind in ("copper", "dielectric", "soldermask")
        if thick and not _close(stated.get("Thickness"), _mm(entry.thickness)):
            out.append(f"{where}: thickness {stated.get('Thickness')!r}, not {float(_mm(entry.thickness))}")
        if not thick and "Thickness" in stated:
            out.append(f"{where}: a thickness on a row without one")
        if stated.get("Material", "") != entry.material and entry.kind == "dielectric":
            out.append(f"{where}: material {stated.get('Material')!r}, not {entry.material!r}")
        if entry.color and stated.get("Color") != entry.color:
            out.append(f"{where}: colour {stated.get('Color')!r}, not {entry.color!r}")
        constants = entry.kind == "dielectric" and done.impedance_controlled
        for key, value in (("DielectricConstant", entry.epsilon_r), ("LossTangent", entry.loss_tangent)):
            wanted = value if constants and value else None
            if (None if stated.get(key) is None else str(stated[key])) != wanted:
                out.append(f"{where}: {key} {stated.get(key)!r}, not {wanted!r}")
    general: Mapping[str, Any] = job.get("GeneralSpecs", {})
    if not _close(general.get("BoardThickness"), _mm(done.thickness())):
        out.append(f"BoardThickness {general.get('BoardThickness')!r}, not {float(_mm(done.thickness()))}")
    if general.get("Finish") != (done.finish or "None"):
        out.append(f"Finish {general.get('Finish')!r}, not {done.finish or 'None'!r}")
    if bool(general.get("ImpedanceControlled", False)) != done.impedance_controlled:
        out.append(f"ImpedanceControlled {general.get('ImpedanceControlled')!r}")
    return out


def thickness_verdict(job: Mapping[str, Any] | None) -> str:
    """``absent`` when no ``MaterialStackup`` entry holds a thickness, ``present`` when every copper and
    dielectric entry holds one, ``different`` for a mix, ``inconclusive`` without a job file."""
    if job is None:
        return "inconclusive"
    entries: list[Mapping[str, Any]] = list(job.get("MaterialStackup", ()))
    physical = [e for e in entries if e.get("Type") in ("Copper", "Dielectric")]
    if not any("Thickness" in e for e in entries):
        return "absent"
    return "present" if physical and all("Thickness" in e for e in physical) else "different"


def default_differences(job: Mapping[str, Any], count: int, general: Fraction = GENERAL_MM) -> list[str]:
    """What the job file of a board without a node states otherwise than KiCad's default
    (``H-K-STACKUP-DEFAULT``): copper 0.035 mm, masks 0.01 mm, ``count`` − 1 FR4 dielectrics that fill
    ``general``, and the finish ``None``."""
    entries: list[Mapping[str, Any]] = list(job.get("MaterialStackup", ()))
    out: list[str] = []
    copper = [e for e in entries if e.get("Type") == "Copper"]
    masks = [e for e in entries if e.get("Type") == "SolderMask"]
    dielectrics = [e for e in entries if e.get("Type") == "Dielectric"]
    each = (general - Fraction(2, 100) - Fraction(35, 1000) * count) / (count - 1)
    if len(copper) != count or not all(_close(e.get("Thickness"), Fraction(35, 1000)) for e in copper):
        out.append(f"copper {[e.get('Thickness') for e in copper]}")
    if len(masks) != 2 or not all(_close(e.get("Thickness"), Fraction(1, 100)) for e in masks):
        out.append(f"masks {[e.get('Thickness') for e in masks]}")
    if len(dielectrics) != count - 1 or not all(
        _close(e.get("Thickness"), each, Fraction(1, 10**4)) and e.get("Material") == "FR4"
        for e in dielectrics
    ):
        out.append(f"dielectrics {[(e.get('Thickness'), e.get('Material')) for e in dielectrics]}")
    finish = job.get("GeneralSpecs", {}).get("Finish")
    if finish != "None":
        out.append(f"Finish {finish!r}")
    return out


# -- 10.0 only: re-save and IPC-2581


def resaved(cli: KicadCli, text: str) -> Node:
    """The board ``text`` after ``pcb upgrade --force`` (10.0 only)."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / f"{STEM}.kicad_pcb"
        board.write_text(text, encoding="utf-8", newline="\n")
        return parse(cli.upgrade_board(board).decode("utf-8"))


def _part(root: Node, *heads: str) -> Node:
    node = root
    for head in heads:
        found = node.find(head)
        assert found is not None, head
        node = found
    return node


def with_kicad_defaults(stackup: Stackup) -> Stackup:
    """``stackup`` with KiCad's values for what a dielectric sheet leaves out: the material ``FR4``, the
    dielectric constant 4.5 and the loss tangent 0.02 (measured on 10.0.6, ``pcb-stackup-resave``)."""
    import dataclasses

    filled = tuple(
        dataclasses.replace(
            entry,
            material=entry.material or "FR4",
            epsilon_r=entry.epsilon_r or "4.5",
            loss_tangent=entry.loss_tangent or "0.02",
        )
        if entry.kind == "dielectric"
        else entry
        for entry in stackup.layers
    )
    return dataclasses.replace(stackup, layers=filled)


def resave_kept(cli: KicadCli, text: str) -> bool:
    """True when the re-save keeps ``general`` tree-equal and the ``stackup`` node as written, a dielectric
    sheet without a material, a dielectric constant or a loss tangent taking KiCad's defaults."""
    design = read_board(text)
    assert design.board is not None and design.board.stackup is not None
    expected = stacklib.stackup_node(with_kicad_defaults(design.board.stackup), design.board.layers)
    before, after = parse(text), resaved(cli, text)
    return tree_equal(expected, _part(after, "setup", "stackup")) and tree_equal(
        _part(before, "general"), _part(after, "general")
    )


def resave_defaults(cli: KicadCli, target: int) -> list[str]:
    """What the re-save of ``resave_defaults_text`` holds otherwise than KiCad's defaults (none:
    ``equal``)."""
    node = _part(resaved(cli, resave_defaults_text(target)), "setup", "stackup")
    rows = {_name(r): dumps(r, style="compact") for r in node.nodes("layer")}
    wanted = {
        "F.Cu": '(layer "F.Cu" (type "copper") (thickness 0.035))',
        "F.Mask": '(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))',
        "dielectric 1": (
            '(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5)'
            " (loss_tangent 0.02))"
        ),
    }
    out = [f"{name}: {rows.get(name)}" for name, row in wanted.items() if rows.get(name) != row]
    tail = [dumps(c, style="compact") for c in node.nodes() if c.name != "layer"]
    if tail != ['(copper_finish "None")', "(dielectric_constraints no)"]:
        out.append(f"tail {tail}")
    return out


def ipc_thickness(cli: KicadCli, text: str) -> str | None:
    """``overallThickness`` of ``pcb export ipc2581`` for the board ``text`` (10.0), or ``None``."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / f"{STEM}.kicad_pcb"
        board.write_text(text, encoding="utf-8", newline="\n")
        project = board.with_suffix(".kicad_pro")
        project.write_text(PROJECT, encoding="utf-8")
        run = cli.export(
            ["pcb", "export", "ipc2581", "-o", "out/bench.xml"],
            board,
            files={project.name: project},
            out="out",
        )
    data = next((d for name, d in run.outputs.items() if name.endswith(".xml")), None)
    if data is None:
        return None
    match = re.search(r'overallThickness="([^"]+)"', data.decode("utf-8", "replace"))
    return match.group(1) if match else None


# -- the stack-up blink, built and exported


def stackup_blink() -> DslDesign:
    """The stack-up variant of the blink (design-dsl, "Stack-up in a build"): masks of 10 µm, 35 µm copper,
    a 1.5 mm FR4 core and the finish ``ENIG``."""
    design = blink()
    design.stackup(
        stack.mask("10um"),
        stack.copper("35um"),
        stack.core("1.5mm", material="FR4"),
        stack.copper("35um"),
        stack.mask("10um"),
        finish="ENIG",
    )
    return design


SIX_BOARD = ("design.board(mm(50), mm(30))", "design.board(mm(50), mm(30), copper=6)")


def stackup_blink_six() -> DslDesign:
    """The six-layer variant of the stack-up blink (c0100's counts): masks, 35 and 17.5 µm copper, prepregs
    of 0.1 mm around two cores of 0.4 mm, a prepreg of two sheets in the middle, ``ENIG``, constraints."""
    assert blink_text().count(SIX_BOARD[0]) == 1
    scope: dict[str, object] = {"__name__": "design"}
    exec(compile(blink_text().replace(*SIX_BOARD), str(BLINK), "exec"), scope)  # noqa: S102 - our own example
    design = scope["design"]
    assert isinstance(design, DslDesign) and design.copper == 6
    fr4 = {"material": "FR4", "epsilon_r": "4.5", "loss_tangent": "0.02"}
    design.stackup(
        stack.mask("10um", color="Green"),
        stack.copper("35um"),
        stack.prepreg("0.1mm", **fr4),
        stack.copper("17.5um"),
        stack.core("0.4mm", **fr4),
        stack.copper("17.5um"),
        stack.prepreg("0.1mm", **fr4),
        stack.prepreg("0.1mm", **fr4),
        stack.copper("17.5um"),
        stack.core("0.4mm", **fr4),
        stack.copper("17.5um"),
        stack.prepreg("0.1mm", **fr4),
        stack.copper("35um"),
        stack.mask("10um"),
        finish="ENIG",
        impedance_controlled=True,
    )
    return design


def build_job(cli: KicadCli, design: DslDesign | None = None) -> list[str] | None:
    """The stack-up blink (or ``design``) built for the major of ``cli`` and exported as
    ``fenolite export --gerbers`` exports it (``exports.plan.run_kind``): what its job file states
    otherwise than the declared stack-up, or ``None`` without a job file."""
    design = design or stackup_blink()
    major = cli.major()
    output = build(design, major)
    name = f"{design.name}.kicad_pcb"
    with tempfile.TemporaryDirectory() as tmp:
        others: dict[str, Path] = {}
        for rel, data in output.files.items():
            if rel.startswith(".fenolite/"):
                continue
            target = Path(tmp) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if rel != name and "/" not in rel:
                others[rel] = target
        board = Path(tmp) / name
        read = read_board(board)
        found = run_kind(cli, "gerbers", board, others, major=major, design=read)
    data = next((a.data for a in found.artifacts if a.path.endswith("-job.gbrjob")), None)
    declared = to_model(design).board
    assert declared is not None and declared.stackup is not None and read.board is not None
    if data is None:
        return None
    return job_differences(json.loads(data.decode("utf-8")), declared.stackup, read.board.layers)


# -- probes

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]


def stackup_probes(runner: Callable[[], KicadCli]) -> Probes:
    """The ``pcb-stackup-*`` probes and ``build-stackup-job`` of the running ``kicad-cli``. A bench is
    written for the running major: KiCad 9 reads a target-9 board."""
    both = (9, 10)

    def target() -> int:
        return runner().major()

    def job(count: int) -> str:
        found = export_job(runner(), job_text(count, target()))
        if found is None:
            return "inconclusive"
        layers = _layers(count)
        assert layers is not None
        return "equal" if not job_differences(found, bench_stackup(count), layers) else "different"

    def default(count: int) -> str:
        found = export_job(runner(), default_text(count, target()))
        if found is None:
            return "inconclusive"
        return "equal" if not default_differences(found, count) else "different"

    def case(name: str) -> str:
        return thickness_verdict(export_job(runner(), case_text(name, target())))

    def resave() -> str:
        return "equal" if all(resave_kept(runner(), job_text(n, 10)) for n in COUNTS) else "different"

    def ipc() -> str:
        found = ipc_thickness(runner(), thin_general_text(10))
        if found is None:
            return "inconclusive"
        return "equal" if Fraction(found) == Fraction(2025, 1000) else "different"

    probes: Probes = {}
    for count in COUNTS:
        probes[f"pcb-stackup-job-{count}"] = (lambda count=count: job(count), both)
        probes[f"pcb-stackup-default-{count}"] = (lambda count=count: default(count), both)
    for name in INCOMPLETE:
        probes[f"pcb-stackup-incomplete-{name}"] = (lambda name=name: case(name), both)
    for name in USED:
        probes[f"pcb-stackup-{name}"] = (lambda name=name: case(name), both)
    probes["pcb-stackup-resave"] = (resave, (10,))
    probes["pcb-stackup-resave-defaults"] = (
        lambda: "equal" if not resave_defaults(runner(), 10) else "different",
        (10,),
    )
    probes["pcb-stackup-ipc-thickness"] = (ipc, (10,))

    def built() -> str:
        """The two-layer stack-up blink and, with c0100's counts, its six-layer variant."""
        designs = [stackup_blink(), *([stackup_blink_six()] if 6 in COUNTS else [])]
        found = [build_job(runner(), design) for design in designs]
        if any(f is None for f in found):
            return "inconclusive"
        return "equal" if not any(found) else "different"

    probes["build-stackup-job"] = (built, both)
    return probes


__all__ = [
    "COUNTS",
    "INCOMPLETE",
    "USED",
    "bench_stackup",
    "build_job",
    "case_text",
    "default_differences",
    "default_text",
    "export_job",
    "ipc_thickness",
    "job_differences",
    "job_text",
    "reader_verdict",
    "resave_defaults",
    "resave_defaults_text",
    "resave_kept",
    "stackup_blink",
    "stackup_blink_six",
    "stackup_probes",
    "thickness_verdict",
    "thin_general_text",
    "with_kicad_defaults",
]
