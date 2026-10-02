# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout oracle runs (c0019 Decision 20): the blink built into a temporary folder, its board edited by
``tests/_layout_edit.py::edit_blink``, re-saved by ``pcb upgrade --force`` on 10.0.6 where the case says
so, and judged from ``kicad-cli`` runs on copies through c0009's runner. The ``lens-*`` probes of
``_probes.PROBES`` record the outcomes."""

from __future__ import annotations

import tempfile
from collections import Counter
from collections.abc import Mapping
from functools import cache
from pathlib import Path

from _buildcases import _folder
from _buildhelp import blink, build
from _layout_edit import EDIT_UUIDS, edit_blink

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.embed import PATH_PROPERTY, placement_uuid
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.dsl import moves, placements, to_model
from fenolite.lens.preserve import ExistingProject, prepare

BOARD = "blink.kicad_pcb"
Files = dict[str, str | bytes]


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


@cache
def built_files(target: int) -> Files:
    """The confirmed blink build of ``target`` (``.fenolite/`` left out)."""
    output = build(blink(), target)
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def text_of(files: Mapping[str, str | bytes]) -> str:
    data = files[BOARD]
    return data.decode("utf-8") if isinstance(data, bytes) else data


@cache
def edited_files(target: int) -> Files:
    """The build with its board edited by ``edit_blink``."""
    files = dict(built_files(target))
    files[BOARD] = edit_blink(text_of(files))
    return files


def resave(files: Mapping[str, str | bytes]) -> Files:
    """``files`` with the board re-saved by ``pcb upgrade --force`` (10.0 only)."""
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != BOARD}
        text = runner().upgrade_board(Path(tmp) / BOARD, files=extra).decode("utf-8")
    return {**files, BOARD: text}


@cache
def resaved_files(target: int) -> Files:
    return resave(edited_files(target))


def drc(files: Mapping[str, str | bytes]) -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != BOARD}
        return runner().drc(Path(tmp) / BOARD, files=extra).report


def drc_key(report: DrcReport) -> tuple[Counter[tuple[str, str]], int]:
    """The (type, severity) multiset of the violations and the number of unconnected items."""
    return Counter((v.type, v.severity) for v in report.violations), len(report.unconnected_items)


def _d1(text: str) -> tuple[str | None, str | None]:
    """``D1``'s footprint uuid and ``fenolite.path`` property in ``text``."""
    design = read_board(text)
    assert design.board is not None
    refs = {c.id: c for c in design.circuit.components}
    for fp in design.board.footprints:
        component = refs.get(fp.component_id or "")
        if component is not None and component.ref == "D1":
            return fp.native_ids.get("kicad"), component.properties.get(PATH_PROPERTY)
    return None, None


def edit_items_kept(text: str) -> bool:
    """Both segments and the via of the edit are in ``text`` with their uuids."""
    design = read_board(text)
    assert design.board is not None
    found = {t.native_ids.get("kicad") for t in design.board.tracks} | {
        v.native_ids.get("kicad") for v in design.board.vias
    }
    return set(EDIT_UUIDS) <= found


@cache
def resave_case() -> str:
    text = text_of(resaved_files(10))
    uuid, path = _d1(text)
    kept = uuid == placement_uuid("D1", "/footprint") and path == "D1" and edit_items_kept(text)
    return "present" if kept else "absent"


@cache
def rewrite_case(target: int) -> str:
    files = edited_files(target)
    rewritten = {**files, BOARD: write_board(read_board(text_of(files)), target=target).text}
    before, after = drc(files), drc(rewritten)
    if before is None or after is None:
        return "reject"
    return "equal" if drc_key(before) == drc_key(after) else "different"


# --- rebuilds (task 10.1) ---------------------------------------------------------------------------


def rebuild(files: Mapping[str, str | bytes], target: int) -> Files:
    """``build_design`` of the blink over the board, project and rules of ``files`` (the lens path)."""
    design = blink()

    def text(name: str) -> str | None:
        data = files.get(name)
        return None if data is None else data.decode("utf-8") if isinstance(data, bytes) else data

    existing = ExistingProject(text(BOARD), text("blink.kicad_pro"), text("blink.kicad_dru"))
    ready = prepare(to_model(design), placements(design), existing, name="blink", moves=moves(design))
    output = build(design, target, prepared=ready, placements_override=ready.placements)
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def input_files(target: int) -> Files:
    """The edited board, re-saved on 10.0 for target 10 (9.0 has no re-save; target 9 keeps the text)."""
    return resaved_files(10) if target == 10 else edited_files(target)


@cache
def rebuilt_files(target: int) -> Files:
    return rebuild(input_files(target), target)


def _items(text: str) -> set[tuple[object, ...]]:
    design = read_board(text)
    assert design.board is not None
    nets = {n.id: n.name for n in design.circuit.nets}
    tracks = {
        (t.native_ids.get("kicad"), t.start, t.end, t.width, t.layer, nets.get(t.net_id or ""))
        for t in design.board.tracks
    }
    vias = {
        (v.native_ids.get("kicad"), v.position, v.diameter, tuple(v.layers), nets.get(v.net_id or ""))
        for v in design.board.vias
    }
    return {i for i in tracks | vias if i[0] in EDIT_UUIDS}


def positions(text: str) -> dict[str, object]:
    design = read_board(text)
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    return {refs[fp.component_id]: (fp.position, fp.rotation, fp.side) for fp in design.board.footprints}


def pos_rows(files: Mapping[str, str | bytes]) -> dict[str, object]:
    """``pcb export pos`` of the board of ``files``: reference → (x, y) in the written frame (mm)."""
    from _frame import read_pos

    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != BOARD}
        rows = read_pos(runner().export_pos_csv(Path(tmp) / BOARD, files=extra))
    return {row.ref: row for row in rows}


@cache
def keep_case(target: int) -> str:
    edited, rebuilt = input_files(target), rebuilt_files(target)
    checks = [
        positions(text_of(rebuilt)) == positions(text_of(edited)),
        len(_items(text_of(rebuilt))) == 3 and _items(text_of(rebuilt)) == _items(text_of(edited)),
    ]
    before, after = drc(edited), drc(rebuilt)
    checks.append(before is not None and after is not None and drc_key(before) == drc_key(after))
    rows_before, rows_after = pos_rows(edited), pos_rows(rebuilt)
    checks.append(rows_before == rows_after and set(rows_after) == {"D1", "R1", "U1"})
    return "equal" if all(checks) else "different"


def lens_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """``probe id → (function, majors)``: target-10 cases on major 10, target-9 cases on both."""
    return {
        "lens-resave-t10": (resave_case, (10,)),
        "lens-rewrite-t9": (lambda: rewrite_case(9), (9, 10)),
        "lens-rewrite-t10": (lambda: rewrite_case(10), (10,)),
        "lens-keep-t9": (lambda: keep_case(9), (9, 10)),
        "lens-keep-t10": (lambda: keep_case(10), (10,)),
    }


__all__ = [
    "BOARD",
    "built_files",
    "drc",
    "drc_key",
    "edit_items_kept",
    "edited_files",
    "input_files",
    "keep_case",
    "lens_probes",
    "pos_rows",
    "positions",
    "rebuild",
    "rebuilt_files",
    "resave",
    "resave_case",
    "resaved_files",
    "rewrite_case",
    "text_of",
]
