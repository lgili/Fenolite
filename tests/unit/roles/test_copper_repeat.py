# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Repeat runs and kept copper (change c0243, decision 12; capability net-roles, "Kept copper and repeat
runs", scenario "Second run and a user edit"; hypothesis ``H-G-ROLE-COPPER-IDEMPOTENT``)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from _rolecopper import bare_buck, cli

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.roles import rolemanifest


def _write(out: Path) -> dict[str, object]:
    code, envelope = cli("copper", str(out), "--dry-run")
    assert code == 0, envelope
    result = envelope["result"]
    if result.get("plan_id"):
        code, written = cli("copper", str(out), "--confirm", "--plan", result["plan_id"])
        assert code == 0, written
    return envelope


def test_second_run_and_a_user_edit(tmp_path: Path) -> None:
    out = bare_buck(tmp_path)
    board = out / "buck_bare.kicad_pcb"
    _write(out)
    first = board.read_bytes()
    second = _write(out)
    assert not second["result"]["changed"] and not second["result"].get("plan_id")  # type: ignore[index, union-attr]
    assert board.read_bytes() == first
    # move one corner of the VIN zone by 0.2 mm, as a user would in KiCad
    text = board.read_text(encoding="utf-8")
    design = read_board(text, file=board.name)
    assert design.board is not None
    (vin,) = [z for z in design.board.zones if z.name.startswith("role.power.VIN.")]
    corner = vin.outline[0]
    moved = (Point(corner.x - 200_000, corner.y), *vin.outline[1:])
    zones = tuple(dataclasses.replace(z, outline=moved) if z.id == vin.id else z for z in design.board.zones)
    edited = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=zones))
    board.write_text(write_board(edited, target=10).text, encoding="utf-8")
    third = _write(out)
    issues = [i for i in third["issues"] if i["code"] == "roles.copper-kept"]  # type: ignore[union-attr]
    assert [i["where"] for i in issues] == [vin.name]
    after = read_board(board.read_text(encoding="utf-8"), file=board.name)
    assert after.board is not None
    (kept,) = [z for z in after.board.zones if z.name == vin.name]
    assert kept.outline[0] == moved[0]
    manifest = rolemanifest.loads((out / rolemanifest.FILE).read_text(encoding="utf-8"))
    assert vin.name not in manifest.items  # the user's now
    # --regenerate brings it back
    code, envelope = cli("copper", str(out), "--dry-run", "--regenerate", vin.name)
    assert code == 0 and not [i for i in envelope["issues"] if i["code"] == "roles.copper-kept"]
