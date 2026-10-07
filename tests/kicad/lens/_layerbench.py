# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The layer-change and rebuild benches of change c0102 (capability kicad-oracle, "Outline and layer changes
pass the oracle"; hypothesis H-K-LAYER-CHANGE).

- **Layer facts.** A four-layer build of the blink with a segment and a blind via on ``In1.Cu`` and a zone
  on ``In2.Cu``, edited by token: the rows ``In3.Cu`` (8) and ``In4.Cu`` (10) added; the rows of the two
  inner layers removed with their items left in place; and a four-copper stack-up put under six rows. The
  stack-up text is authored here with round values, in the form KiCad writes.
- **Rebuilds** (KiCad 10). The same board rebuilt by Fenolite with six copper layers and then with two; and
  a blink with two added segments rebuilt on a narrower outline, which drops the one that no longer fits.
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _lenscases as lc
from _buildcases import _folder
from _layout_edit import add_items, net_ref
from _outlinebench import drc, target, types
from _outlinehelp import board_text, build_script, codes, rebuild_script, variant

from fenolite.backends.base import DrcReport
from fenolite.lens.build import BuildOutput

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Files = dict[str, str | bytes]
BOARD = "blink.kicad_pcb"
SETUP = "(pad_to_mask_clearance 0)"
STACKUP = (
    '(stackup (layer "F.Cu" (type "copper") (thickness 0.035)) '
    '(layer "dielectric 1" (type "core") (thickness 0.5) (epsilon_r 4.5) (loss_tangent 0.02)) '
    '(layer "In1.Cu" (type "copper") (thickness 0.035)) '
    '(layer "dielectric 2" (type "core") (thickness 0.5) (epsilon_r 4.5) (loss_tangent 0.02)) '
    '(layer "In2.Cu" (type "copper") (thickness 0.035)) '
    '(layer "dielectric 3" (type "core") (thickness 0.5) (epsilon_r 4.5) (loss_tangent 0.02)) '
    '(layer "B.Cu" (type "copper") (thickness 0.035)) (copper_finish "None") (dielectric_constraints no))'
)
IN2_ROW = '\t\t(6 "In2.Cu" signal)\n'
NARROW = "design.board(mm(44), mm(30))"


def layers(copper: int) -> str:
    return f"design.board(mm(50), mm(30), copper={copper})" if copper != 2 else "design.board(mm(50), mm(30))"


def inner_items(text: str) -> str:
    gnd, zone = net_ref(text, "GND"), net_ref(text, "GND", zone=True)
    return add_items(
        text,
        f'(segment (start 110 124) (end 120 124) (width 0.25) (layer "In1.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000d0001"))',
        f'(via blind (at 110 124) (size 0.6) (drill 0.3) (layers "F.Cu" "In1.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000d0002"))',
        f'(zone {zone} (layer "In2.Cu") (uuid "00000000-0000-4000-8000-0000000d0004") (name "inner") '
        "(hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) (filled_areas_thickness no) "
        "(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) "
        "(polygon (pts (xy 122 122) (xy 130 122) (xy 130 128) (xy 122 128))))",
    )


@cache
def four_layers() -> tuple[tuple[str, str | bytes], ...]:
    """The four-layer build with its inner items, as files."""
    output = build_script(variant(layers(4)), target())
    files: Files = {k: v for k, v in output.files.items() if not k.startswith(".fenolite/")}
    files[BOARD] = inner_items(board_text(output))
    return tuple(files.items())


def _text(files: Mapping[str, str | bytes]) -> str:
    data = files[BOARD]
    return data.decode("utf-8") if isinstance(data, bytes) else data


def edited(case: str) -> Files:
    """The four-layer board with rows ``added``, with its inner rows removed and their items ``left``, or
    with a ``stale`` four-copper stack-up under six rows."""
    files = dict(four_layers())
    text = _text(files)
    assert text.count(IN2_ROW) == 1 and text.count(SETUP) == 1
    more = IN2_ROW + '\t\t(8 "In3.Cu" signal)\n\t\t(10 "In4.Cu" signal)\n'
    if case == "added":
        text = text.replace(IN2_ROW, more)
    elif case == "left":
        text = text.replace('\t\t(4 "In1.Cu" signal)\n', "").replace(IN2_ROW, "")
    elif case == "stale":
        text = text.replace(IN2_ROW, more).replace(SETUP, f"{SETUP} {STACKUP}")
    else:
        raise ValueError(case)
    files[BOARD] = text
    return files


def job_file(files: Mapping[str, str | bytes]) -> dict[str, object] | None:
    """The Gerber job file of ``pcb export gerbers`` on the board of ``files``."""
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        args = ["pcb", "export", "gerbers", "--no-protel-ext", "-o", "gerbers/", BOARD]
        run = lc.runner().run(args, files=tops, folders=["gerbers"])
    for name, data in run.outputs.items():
        if name.endswith(".gbrjob"):
            return json.loads(data.decode("utf-8"))
    return None


def copper_layers(job: Mapping[str, object]) -> int:
    specs = job.get("GeneralSpecs")
    return int(specs.get("LayerNumber", 0)) if isinstance(specs, dict) else 0


def thicknesses(job: Mapping[str, object]) -> int:
    """The number of stack-up entries of the job file that hold a thickness."""
    stack = job.get("MaterialStackup")
    if not isinstance(stack, list):
        return 0
    return sum(1 for row in stack if isinstance(row, dict) and "Thickness" in row)


def kinds(report: DrcReport) -> Counter[tuple[str, str, str]]:
    """The findings of ``report`` by ``(group, type, severity)``, with their counts."""
    return Counter((entry[0], entry[1], entry[2]) for entry in report.entries())


@cache
def layers_added() -> str:
    """``absent`` when the added rows give no DRC finding that the unedited board lacks, and the job file
    lists six copper layers with KiCad's default thicknesses."""
    control, added = drc(dict(four_layers())), drc(edited("added"))
    job = job_file(edited("added"))
    if control is None or added is None or job is None:
        return "inconclusive"
    if copper_layers(job) != 6 or thicknesses(job) == 0:
        return "inconclusive"
    # KiCad's ratsnest names either of two items at one point from run to run (the blind via or the track
    # it ends), so the findings are compared by group, type and severity, with their counts
    return "absent" if not kinds(added) - kinds(control) else "present"


@cache
def layers_left_items() -> str:
    """``present`` when the items left on removed rows give ``item_on_disabled_layer``."""
    report = drc(edited("left"))
    if report is None:
        return "inconclusive"
    return "present" if "item_on_disabled_layer" in types(report) else "absent"


@cache
def layers_stale_stackup() -> str:
    """``present`` when a four-copper stack-up under six rows leaves the job file without thicknesses."""
    job = job_file(edited("stale"))
    if job is None or copper_layers(job) != 6:
        return "inconclusive"
    return "present" if thicknesses(job) == 0 else "absent"


def _files(output: BuildOutput) -> Files:
    return {k: v for k, v in output.files.items() if not k.startswith(".fenolite/")}


@cache
def rebuild_layers() -> str:
    """``absent`` when the four-layer board, rebuilt with six copper layers and then with two, gives no
    ``item_on_disabled_layer`` and a job file with thicknesses each time (KiCad 10)."""
    text = _text(dict(four_layers()))
    for count in (6, 2):
        output = rebuild_script(variant(layers(count)), text, target())
        if not output.files:
            return "inconclusive"
        report, job = drc(_files(output)), job_file(_files(output))
        if report is None or job is None or copper_layers(job) != count:
            return "inconclusive"
        if "item_on_disabled_layer" in types(report) or thicknesses(job) == 0:
            return "present"
        text = board_text(output)
    return "absent"


def routed(text: str, *, outside: bool) -> str:
    """The blink with a segment that fits a 44 mm board and, with ``outside``, one that does not."""
    gnd = net_ref(text, "GND")
    items = [
        f'(segment (start 110 127) (end 120 127) (width 0.25) (layer "F.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000c0001"))'
    ]
    if outside:
        items.append(
            f'(segment (start 145 105) (end 148 105) (width 0.25) (layer "F.Cu") {gnd} '
            '(uuid "00000000-0000-4000-8000-0000000c0002"))'
        )
    return add_items(text, *items)


@cache
def rebuild_outline() -> str:
    """``absent`` when a routed blink rebuilt on a narrower outline, its copper that no longer fits
    dropped, gives no ``invalid_outline`` and no ``copper_edge_clearance``, and the unconnected items of a
    board that never held the dropped track (KiCad 10)."""
    first = board_text(build_script(variant(), target()))
    rebuilt = rebuild_script(variant(NARROW), routed(first, outside=True), target())
    control = rebuild_script(variant(NARROW), routed(first, outside=False), target())
    if not rebuilt.files or "kicad.outline.copper-dropped" not in codes(rebuilt):
        return "inconclusive"
    if "kicad.outline.copper-dropped" in codes(control):
        return "inconclusive"
    report, wanted = drc(_files(rebuilt)), drc(_files(control))
    if report is None or wanted is None:
        return "inconclusive"
    found = types(report)
    if "invalid_outline" in found or "copper_edge_clearance" in found:
        return "present"
    left, right = (sorted(v.type for v in found.unconnected_items) for found in (report, wanted))
    return "absent" if left == right else "present"


def layer_change_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    return {
        "layers-added": (layers_added, both),
        "layers-left-items": (layers_left_items, both),
        "layers-stale-stackup": (layers_stale_stackup, both),
        "rebuild-layers": (rebuild_layers, (10,)),
        "rebuild-outline": (rebuild_outline, (10,)),
    }


__all__ = [
    "edited",
    "four_layers",
    "job_file",
    "layer_change_probes",
    "layers_added",
    "layers_left_items",
    "layers_stale_stackup",
    "rebuild_layers",
    "rebuild_outline",
]
