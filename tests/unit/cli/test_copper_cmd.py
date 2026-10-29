# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite copper`` (change c0243; capability cli-contract, "Copper command"; ``docs/cli-contract.md``,
"copper")."""

from __future__ import annotations

import sys
from pathlib import Path

ROLES = Path(__file__).resolve().parents[1] / "roles"
if str(ROLES) not in sys.path:
    sys.path.insert(0, str(ROLES))

from _rolecopper import bare_buck, cli  # noqa: E402

from fenolite.roles import rolemanifest  # noqa: E402


def test_plan_then_write(tmp_path: Path) -> None:
    """Scenario "Plan, then write"."""
    out = bare_buck(tmp_path)
    board = out / "buck_bare.kicad_pcb"
    before = board.read_bytes()
    code, envelope = cli("copper", str(out), "--dry-run")
    assert code == 0, envelope
    result = envelope["result"]
    assert {n["net"] for n in result["nets"] if n["zones"]} >= {"VIN", "SW", "VL", "VOUT", "GND"}
    assert result["changed"] and result["plan_id"] and board.read_bytes() == before
    assert not (out / rolemanifest.FILE).exists()
    assert result["next"] == ["fenolite fill", "fenolite check"]
    code, envelope = cli("copper", str(out), "--confirm", "--plan", result["plan_id"])
    assert code == 0, envelope
    written = {Path(w["path"]).name for w in envelope["receipt"]["written"]}
    assert {"buck_bare.kicad_pcb", "role-copper.json"} <= written
    assert board.read_bytes() != before
    manifest = rolemanifest.loads((out / rolemanifest.FILE).read_text(encoding="utf-8"))
    assert any(key.startswith("role.power.VIN.") for key in manifest.items)


def test_confirmation_and_refusals(tmp_path: Path) -> None:
    """Scenario "Confirmation and refusals"."""
    out = bare_buck(tmp_path)
    code, envelope = cli("copper", str(out))
    assert code == 4, envelope
    pcbdoc = tmp_path / "board.PcbDoc"
    pcbdoc.write_bytes(b"")
    code, envelope = cli("copper", str(pcbdoc), "--dry-run")
    assert code == 2 and "design.role_copper()" in envelope["stderr"], envelope
    for bad in (("--kinds", "motor"), ("--connection", "ground=spokes"), ("--widen", "500")):
        code, envelope = cli("copper", str(out), "--dry-run", *bad)
        assert code == 2, (bad, envelope)


def test_gate_needs_kicad_cli(tmp_path: Path) -> None:
    out = bare_buck(tmp_path)
    code, envelope = cli(
        "copper", str(out), "--dry-run", "--gate", "drc", "--kicad-cli", str(tmp_path / "nope")
    )
    assert code == 6, envelope
