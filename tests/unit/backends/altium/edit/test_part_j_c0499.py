# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Case J34 of Part J, a part added to a project (change c0499; ``docs/evidence/altium-edit.md``): the folder
``phase-c/J34/``, a copy of the kit project whose sheet gets a part copied, annotated, wired to a power port
and labelled, and whose board gets that component, with a body in the smaller key set, linked to the part.
Each gate is forced on for the kit only. ``FENOLITE_ALTIUM_PART_J=<folder outside the repository>`` writes
them there; without it they are written under the test's own folder. No file Altium wrote is in the
repository."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium import pcbrecords as pcbrec
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.read.pcb import read_pcbdoc
from tests.unit.backends.altium.edit.conftest import OPEN, mm

ROOT = Path(__file__).resolve().parents[5]
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_J")
SCH_OPEN = dict.fromkeys(("add_part", "annotate", "create"), True)
MIL = 25_400
MECHANICAL_13 = 69


def older_body(data: bytes) -> bytes:
    """The kit board with an extruded body of the smaller key set (``body_record(form="short")``) on R1."""
    state = State.of(data)
    [index] = [
        n for n, c in enumerate(read_pcbdoc(data).components) if c.record.get("SOURCEDESIGNATOR") == "R1"
    ]
    x, y = (round(float((state.properties("Components6")[index].get(k) or "0").removesuffix("mil")) * 10_000)
            for k in ("X", "Y"))  # fmt: skip
    ring = [
        (x - 200_000, y - 100_000),
        (x + 200_000, y - 100_000),
        (x + 200_000, y + 100_000),
        (x - 200_000, y + 100_000),
    ]
    for storage, based in (("ComponentBodies6", False), ("ShapeBasedComponentBodies6", True)):
        raw = pcbrec.body_record(
            MECHANICAL_13,
            ring,
            component=index,
            standoff=0,
            overall=200_000,
            bottom=False,
            form="short",
            shape_based=based,
        )
        state.append(storage, raw)
    return state.data()


def j34(folder: Path, kit: Path) -> dict[str, str]:
    """Write ``phase-c/J34/`` into ``folder``; the SHA-256 of each written file by name."""
    target = folder / "phase-c" / "J34"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(kit, target)
    source = folder / "phase-c" / "older-body.PcbDoc"
    source.write_bytes(older_body((kit / "edit.PcbDoc").read_bytes()))
    sheet, board, project = target / "edit.SchDoc", target / "edit.PcbDoc", target / "edit.PrjPcb"
    pin, left = (2900 * MIL, 6450 * MIL), (2700 * MIL, 6450 * MIL)
    schematic = edit.open(sheet, gates=SCH_OPEN, project=project)
    assert isinstance(schematic, edit.SchematicSession)
    schematic.add_part(sheet, "R1", at=(500 * MIL, 0)).annotate(edit.Part("R?"), "R9", old="R?")
    schematic.add_wire([pin, left]).add_power_port("GND", left).add_net_label("GND", (2800 * MIL, 6450 * MIL))
    receipt = schematic.declare_connectivity().commit(sheet, backup=False)
    assert receipt.written, receipt.issues
    pcb = edit.open(board, gates=OPEN)
    assert isinstance(pcb, edit.Session)
    pcb.add_component(source, "R1", designator="R9", at=(mm(32), mm(22))).link(
        "R9", project=project, part="R9"
    )
    receipt = pcb.commit(board, backup=False)
    assert receipt.written, receipt.issues
    sums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (sheet, board, source)}
    (target / "SHA256SUMS").write_text("".join(f"{d}  {n}\n" for n, d in sums.items()), encoding="utf-8")
    return sums


def test_j34_kit(kit_board: Path, tmp_path: Path) -> None:
    folder = Path(HANDOVER).expanduser() if HANDOVER else tmp_path / "J-edit"
    if HANDOVER:
        assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    sums = j34(folder, kit_board)
    assert set(sums) == {"edit.SchDoc", "edit.PcbDoc", "older-body.PcbDoc"}
    written = State.of((folder / "phase-c" / "J34" / "edit.PcbDoc").read_bytes())
    assert len(written.get("ComponentBodies6")) == 1
