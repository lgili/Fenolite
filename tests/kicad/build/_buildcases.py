# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build probes and build oracle cases (c0011 Decisions 25 and 26), each run once per session through
c0009's runner on temporary copies. The ``build-*`` probes of ``_probes.PROBES`` record the outcomes."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _rulebench as rb
from _build_judge import baseline_outcome, canary_outcome, class_outcome, libtable_outcome
from _buildhelp import LIBS, blink, build
from _probe_boards import probe_board

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.dsl import mm
from fenolite.lens.build import BuildOutput

PROJECT = "{}\n"
USED = ("Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603", "Mini_LED_THT_3mm")
BASELINE_EXCEPTIONS: frozenset[str] = frozenset()
"""Error-severity violation types a clean placement cannot avoid (Decision 25): none recorded."""


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


@dataclass(frozen=True)
class Run:
    run: CliRun
    report: DrcReport | None


def _folder(files: Mapping[str, str | bytes], tmp: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for rel, data in files.items():
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        top = rel.split("/", 1)[0]
        out[top] = tmp / top
    return out


def drc(files: Mapping[str, str | bytes], board: str) -> Run:
    """``pcb drc`` on ``board`` with every other top-level entry of ``files`` copied next to it."""
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != board}
        result = runner().drc(Path(tmp) / board, files=extra)
    return Run(result.run, result.report)


def loads(files: Mapping[str, str | bytes], board: str) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        args = ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", board]
        run = runner().run(args, files=tops)
    return run.ok and "out.svg" in run.outputs


def upgraded(files: Mapping[str, str | bytes], board: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != board}
        return runner().upgrade_board(Path(tmp) / board, files=extra).decode("utf-8")


# --- group 2: probes first --------------------------------------------------------------------------


def _with_property(text: str) -> str:
    """Every footprint of ``text`` with the hidden ``fenolite.path`` property after its last property."""
    root = parse(text)
    children: list[Node | Atom] = []
    for index, child in enumerate(root.children):
        if isinstance(child, Node) and child.name == "footprint":
            refs = [p for p in child.nodes("property") if p.atoms()[0].value == "Reference"]
            ref = refs[0].atoms()[1].value
            prop = parse(
                f'(property "{PATH_PROPERTY}" "{ref}" (at 0 0 0) (layer "F.Fab") (hide yes) '
                f'(uuid "00000000-0000-4000-8000-{index:012d}") '
                "(effects (font (size 1 1) (thickness 0.15))))"
            )
            kids = list(child.children)
            last = max(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "property")
            kids.insert(last + 1, prop)
            child = child.with_children(kids)
        children.append(child)
    return dumps(root.with_children(children), style="kicad")


@cache
def pathprop(target: int) -> str:
    text = _with_property(write_board(probe_board(target), target=target).text)
    files = {"blink.kicad_pcb": text, "blink.kicad_pro": PROJECT}
    if not loads(files, "blink.kicad_pcb"):
        return "reject"
    if major() < 10:
        return "load"
    back = read_board(upgraded(files, "blink.kicad_pcb"))
    root = parse(upgraded(files, "blink.kicad_pcb"))
    kept = all(c.properties.get(PATH_PROPERTY) == c.ref for c in back.circuit.components)
    hidden = all(
        p.find("hide") is not None
        for fp in root.nodes("footprint")
        for p in fp.nodes("property")
        if p.atoms()[0].value == PATH_PROPERTY
    )
    return "present" if kept and hidden and back.circuit.components else "absent"


def _vendored(target: int) -> dict[str, str | bytes]:
    files: dict[str, str | bytes] = {
        f"lib/Mini.pretty/{name}.kicad_mod": (LIBS / "Mini_v9.pretty" / f"{name}.kicad_mod").read_bytes()
        for name in USED
    }
    table = LibTable("footprint", (LibRow("Mini", "KiCad", "${KIPRJMOD}/lib/Mini.pretty"),))
    files["fp-lib-table"] = write_lib_table(table, target=target)
    return files


@cache
def libtable(target: int) -> str:
    board = {
        "blink.kicad_pcb": write_board(probe_board(target), target=target).text,
        "blink.kicad_pro": PROJECT,
    }
    with_table = drc({**board, **_vendored(target)}, "blink.kicad_pcb")
    without = drc(board, "blink.kicad_pcb")
    return libtable_outcome(with_table.report, without.report)


@cache
def baseline_run(target: int, offboard: bool) -> Run:
    text = write_board(probe_board(target, offboard=offboard), target=target).text
    return drc({"blink.kicad_pcb": text, "blink.kicad_pro": PROJECT}, "blink.kicad_pcb")


def baseline(target: int) -> str:
    return baseline_outcome(baseline_run(target, False).report, excepted=BASELINE_EXCEPTIONS)


def offboard(target: int) -> str:
    clean, moved = baseline_run(target, False).report, baseline_run(target, True).report
    if clean is None or moved is None:
        return "reject"
    return "present" if {v.type for v in moved.violations} - {v.type for v in clean.violations} else "absent"


def violation_types(target: int, offboard_board: bool) -> list[tuple[str, str]]:
    report = baseline_run(target, offboard_board).report
    return sorted({(v.type, v.severity) for v in report.violations}) if report is not None else []


# --- group 11: the built blink ---------------------------------------------------------------------


@cache
def built(target: int, variant: str = "") -> BuildOutput:
    design = blink()
    if variant == "class":
        spec = design.rules.netclasses["PWR"]
        import dataclasses

        design.rules.netclasses["PWR"] = dataclasses.replace(spec, clearance=mm(2).nm)
    return build(design, target)


def _files(output: BuildOutput, *, project: bool = True, table: bool = True) -> dict[str, str | bytes]:
    out: dict[str, str | bytes] = {}
    for rel, data in output.files.items():
        if rel.startswith(".fenolite/"):
            continue
        if (rel.endswith(".kicad_pro") and not project) or (rel == "fp-lib-table" and not table):
            continue
        out[rel] = data
    return out


@cache
def clean(target: int) -> tuple[Run, Run]:
    output = built(target)
    files = _files(output)
    canary = dict(files)
    canary["blink.kicad_dru"] = rb.with_canary(output.files["blink.kicad_dru"].decode("utf-8"))
    return drc(files, "blink.kicad_pcb"), drc(canary, "blink.kicad_pcb")


def canary(target: int) -> str:
    plain, with_canary = clean(target)
    if plain.report is None:
        return "reject"
    return canary_outcome(plain.report, with_canary.report)


def u1_pads(output: BuildOutput) -> tuple[str, str]:
    assert output.design.board is not None
    u1 = next(fp for fp in output.design.board.footprints if fp.lib_ref.endswith("QFP-32_7x7mm_P0.8mm"))
    by_number = {p.number: p.native_ids["kicad"] for p in u1.pads}
    return by_number["9"], by_number["10"]


@cache
def class_case(target: int) -> str:
    variant = built(target, "class")
    runs = (
        drc(_files(variant), "blink.kicad_pcb").report,
        drc(_files(variant, project=False), "blink.kicad_pcb").report,
        drc(_files(built(target)), "blink.kicad_pcb").report,
    )
    if any(r is None for r in runs):
        return "reject"
    v, n, a = runs
    assert v is not None and n is not None and a is not None
    return class_outcome(v, n, a, pads=u1_pads(variant))


@cache
def vendored_table(target: int) -> str:
    output = built(target)
    return libtable_outcome(
        drc(_files(output), "blink.kicad_pcb").report,
        drc(_files(output, table=False), "blink.kicad_pcb").report,
    )


def build_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """``probe id → (function, majors)``: target-10 cases on major 10, target-9 cases on both."""
    probes: dict[str, tuple[object, tuple[int, ...]]] = {}
    for target, majors in ((9, (9, 10)), (10, (10,))):
        probes[f"build-pathprop-t{target}"] = (lambda t=target: pathprop(t), majors)
        probes[f"build-libtable-t{target}"] = (lambda t=target: libtable(t), majors)
        probes[f"build-baseline-t{target}"] = (lambda t=target: baseline(t), majors)
        probes[f"build-offboard-t{target}"] = (lambda t=target: offboard(t), majors)
        probes[f"build-canary-t{target}"] = (lambda t=target: canary(t), majors)
        probes[f"build-class-t{target}"] = (lambda t=target: class_case(t), majors)
    return probes


__all__ = [
    "BASELINE_EXCEPTIONS",
    "baseline",
    "build_probes",
    "built",
    "canary",
    "class_case",
    "clean",
    "libtable",
    "offboard",
    "pathprop",
    "u1_pads",
    "vendored_table",
    "violation_types",
]
