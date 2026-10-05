# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Oracle runs of the lens acceptance fixture (capability kicad-oracle, "Renamed footprints pass the oracle";
hypothesis H-K-LENS-RENAME; change c0069).

The fixture is built, its board edited by ``tests/_lensfix.py::edit_board`` (re-saved by ``pcb upgrade
--force`` for target 10), and rebuilt from the script whose module ``power`` is renamed ``supply`` through
``moved()``. ``kicad-cli`` then judges the rebuilt board: every footprint of the edited board at its
placement (``pcb export pos``), the same DRC report, and, on 10.0, the group and the renamed uuids kept by
a re-save. The ``lens-rename-*`` probes record the outcomes."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import _lenscases as lc
from _buildcases import _folder
from _buildhelp import build
from _layout_edit import footprint_node, group_members, node_uuid
from _lensfix import FOLDER, GROUP, GROUPED, NAME, PATHS, edit_board, edit_script, renamed

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.sexpr import walk
from fenolite.dsl import Design, module_moves, moves, net_moves, placements, to_model
from fenolite.lens.preserve import ExistingProject, footprint_uuid, prepare

ROOT = Path(__file__).resolve().parents[3]
BOARD = f"{NAME}.kicad_pcb"
Files = dict[str, str | bytes]


def script() -> str:
    return (ROOT / FOLDER / "design.py").read_text(encoding="utf-8")


def design(text: str) -> Design:
    namespace: dict[str, object] = {}
    exec(compile(text, "design.py", "exec"), namespace)  # noqa: S102
    found = namespace["design"]
    assert isinstance(found, Design)
    return found


def _outside_cache(files: Mapping[str, bytes]) -> Files:
    return {rel: data for rel, data in files.items() if not rel.startswith(".fenolite/")}


def text_of(files: Mapping[str, str | bytes]) -> str:
    data = files[BOARD]
    return data.decode("utf-8") if isinstance(data, bytes) else data


@cache
def built_files(target: int) -> Files:
    return _outside_cache(build(design(script()), target).files)


@cache
def edited_files(target: int) -> Files:
    files = dict(built_files(target))
    files[BOARD] = edit_board(text_of(files))
    return files


def _in_folder(files: Mapping[str, str | bytes]) -> tuple[tempfile.TemporaryDirectory[str], dict[str, Path]]:
    tmp = tempfile.TemporaryDirectory()
    tops = _folder(files, Path(tmp.name))
    return tmp, {k: v for k, v in tops.items() if k != BOARD}


def resave(files: Mapping[str, str | bytes]) -> Files:
    """``files`` with the board re-saved by ``pcb upgrade --force`` (10.0 only)."""
    tmp, extra = _in_folder(files)
    with tmp:
        text = lc.runner().upgrade_board(Path(tmp.name) / BOARD, files=extra).decode("utf-8")
    return {**files, BOARD: text}


@cache
def input_files(target: int) -> Files:
    """The edited board, re-saved on 10.0 for target 10 (9.0 has no re-save)."""
    return resave(edited_files(10)) if target == 10 else edited_files(target)


def rebuild(files: Mapping[str, str | bytes], target: int, text: str) -> Files:
    """``build_design`` of the script ``text`` over the board, project and rules of ``files``."""
    made = design(text)

    def held(name: str) -> str | None:
        data = files.get(name)
        return None if data is None else data.decode("utf-8") if isinstance(data, bytes) else data

    existing = ExistingProject(held(BOARD), held(f"{NAME}.kicad_pro"), held(f"{NAME}.kicad_dru"))
    ready = prepare(
        to_model(made),
        placements(made),
        existing,
        name=NAME,
        moves=moves(made),
        module_moves=module_moves(made),
        net_moves=net_moves(made),
    )
    output = build(made, target, prepared=ready, placements_override=ready.placements)
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return _outside_cache(output.files)


@cache
def rebuilt_files(target: int) -> Files:
    return rebuild(input_files(target), target, edit_script(script()))


def drc(files: Mapping[str, str | bytes]) -> DrcReport | None:
    tmp, extra = _in_folder(files)
    with tmp:
        return lc.runner().drc(Path(tmp.name) / BOARD, files=extra).report


def pos_rows(files: Mapping[str, str | bytes]) -> dict[str, object]:
    from _frame import read_pos

    tmp, extra = _in_folder(files)
    with tmp:
        rows = read_pos(lc.runner().export_pos_csv(Path(tmp.name) / BOARD, files=extra))
    return {row.ref: row for row in rows}


def loads_at_its_placements(target: int) -> bool:
    """``pcb export pos`` lists every footprint of the edited board, in the rebuilt board, at the same
    position, rotation and side."""
    before, after = pos_rows(input_files(target)), pos_rows(rebuilt_files(target))
    return set(before) == set(PATHS) and all(after.get(ref) == row for ref, row in before.items())


def same_drc(target: int) -> bool:
    before, after = drc(input_files(target)), drc(rebuilt_files(target))
    return before is not None and after is not None and lc.drc_key(before) == lc.drc_key(after)


def renamed_uuids(text: str) -> set[str]:
    """Every uuid inside the footprints of the renamed module."""
    found: set[str] = set()
    for ref, path in PATHS.items():
        if path.startswith("power/"):
            fp = footprint_node(text, ref)
            found |= {node_uuid(node) for _, node in walk(fp) if node.find("uuid") is not None}
    return found


def group_is_renamed(text: str, *, ordered: bool = True) -> bool:
    """Whether the group lists the two renamed footprints by their new uuids, and nothing else. A rebuild
    keeps the order of the edited group; a re-save by KiCad 10.0.6 writes the members sorted by uuid, so
    ``ordered=False`` compares them as a set."""
    wanted = [footprint_uuid(renamed(PATHS[ref])) for ref in GROUPED]
    found = group_members(text, GROUP)
    return found == wanted if ordered else sorted(found) == sorted(wanted)


@cache
def resave_keeps_identity() -> bool:
    """On 10.0: a re-save of the rebuilt target-10 board keeps the group by the new uuids and every uuid
    of the renamed footprints."""
    rebuilt = text_of(rebuilt_files(10))
    saved = text_of(resave(rebuilt_files(10)))
    return group_is_renamed(saved, ordered=False) and renamed_uuids(saved) == renamed_uuids(rebuilt)


@cache
def rename_case(target: int) -> str:
    checks = [
        group_is_renamed(text_of(rebuilt_files(target))),
        loads_at_its_placements(target),
        same_drc(target),
    ]
    if target == 10:
        checks.append(resave_keeps_identity())
    return "equal" if all(checks) else "different"


def rename_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """``probe id → (function, majors)``: the target-10 case on major 10, the target-9 case on both."""
    return {
        "lens-rename-t9": (lambda: rename_case(9), (9, 10)),
        "lens-rename-t10": (lambda: rename_case(10), (10,)),
    }


__all__ = [
    "BOARD",
    "built_files",
    "drc",
    "edited_files",
    "group_is_renamed",
    "input_files",
    "loads_at_its_placements",
    "pos_rows",
    "rebuild",
    "rebuilt_files",
    "rename_case",
    "rename_probes",
    "renamed_uuids",
    "resave",
    "resave_keeps_identity",
    "same_drc",
    "script",
    "text_of",
]
