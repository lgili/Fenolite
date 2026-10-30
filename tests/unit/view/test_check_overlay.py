# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``check`` findings placed on a board or a sheet (capability check-overlay, scenario "Two findings";
change c0188). The replies are authored here."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fenolite.cli.cmd_view import scene_of
from fenolite.core.errors import FormatError
from fenolite.view.check_overlay import overlay, read_reply, summary

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _reply(*issues: dict[str, Any], stages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    full = [{"hint": "", "retryable": False, "where": ""} | issue for issue in issues]
    return {
        "command": "check",
        "result": {"stages": stages or []},
        "issues": full,
        "evidence": {"level": "INFERRED"},
    }


def test_two_findings() -> None:
    """Scenario "Two findings": one clearance error at a point, one finding without a position."""
    reply = _reply(
        {
            "code": "kicad.drc.clearance",
            "severity": "error",
            "message": "clearance: Clearance violation",
            "where": "@12.5,3.25, @13,-1",
        },
        {
            "code": "copper.clearance-unset",
            "severity": "info",
            "message": "1 item pair(s) judged for shorts only",
        },
        stages=[{"name": "drc.kicad", "evidence": {"level": "ORACLE-VERIFIED(kicad-cli)"}, "summary": {}}],
    )
    placed = overlay(read_reply(reply), {"prims": [], "pads": [], "comps": [], "nets": [], "meta": {}})
    first, second = placed["findings"]
    assert first["at"] == [12500.0, 3250.0] and first["box"] == [12500.0, -1000.0, 13000.0, 3250.0]
    assert first["stage"] == "drc.kicad" and first["evidence"] == "ORACLE-VERIFIED(kicad-cli)"
    assert second["at"] is None and second["evidence"] == "INFERRED"
    assert summary(placed) == {"error": 1, "warning": 0, "info": 1, "total": 2, "placed": 1}


def test_names_and_messages_on_a_board() -> None:
    scene = scene_of(BOARD)
    reply = _reply(
        {
            "code": "copper.short",
            "severity": "error",
            "message": "copper of A and B touches on F.Cu at (1.5, 2) mm",
        },
        {
            "code": "kicad.drc.unconnected_items",
            "severity": "error",
            "message": "x",
            "where": "R1-1, /kicad_pcb/segment[0]",
        },
        {
            "code": "model.single-pin-net",
            "severity": "warning",
            "message": "net connects a single pin",
            "where": "GND",
        },
        {"code": "kicad.erc.pin_not_connected", "severity": "error", "message": "x", "where": "/@10,20"},
        {"code": "kicad.erc.footprint-link-issues", "severity": "warning", "message": "x", "where": "R1"},
        {
            "code": "kicad.drc.starved-thermal",
            "severity": "error",
            "message": "x",
            "where": "/kicad_pcb/zone[0]",
        },
    )
    found = {f["code"]: f for f in overlay(reply, scene)["findings"]}
    assert found["copper.short"]["at"] == [1500.0, 2000.0] and found["copper.short"]["layer"] == "F.Cu"
    pad = next(p for p in scene["pads"] if p["label"] == "R1-1")
    unconnected = found["kicad.drc.unconnected_items"]
    assert unconnected["layer"] == "F.Cu" and unconnected["box"][0] <= pad["x"] <= unconnected["box"][2]
    assert found["model.single-pin-net"]["at"] is not None  # the net's own box
    assert found["kicad.erc.pin_not_connected"]["at"] is None  # a sheet's finding, listed only
    assert (
        found["kicad.erc.footprint-link-issues"]["at"] is None
    )  # an ERC finding names a symbol, not the part
    assert found["kicad.drc.starved-thermal"]["at"] is not None  # the zone, by its index among the zones


def test_sheet_findings() -> None:
    sheet = {
        "kind": "schematic",
        "meta": {"name": "power.kicad_sch", "backend": "kicad"},
        "comps": [],
        "objects": [],
    }
    reply = _reply(
        {"code": "kicad.erc.a", "severity": "error", "message": "x", "where": "/power/@10,20"},
        {"code": "kicad.erc.b", "severity": "error", "message": "x", "where": "/other/@1,2"},
    )
    a, b = overlay(reply, sheet)["findings"]
    assert a["at"] == [10000.0, 20000.0] and b["at"] is None


def test_not_a_check_reply() -> None:
    with pytest.raises(FormatError, match="analyze"):
        read_reply({"command": "analyze", "issues": []}, name="a.json")


def test_conflict_marked_on_its_footprint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "Conflict marked on its footprint" and "Command lines offered" (change c0250)."""
    import io  # noqa: PLC0415
    import json  # noqa: PLC0415

    from _edit_help import edit as edit_parts  # noqa: PLC0415
    from _project import Project, footprint  # noqa: PLC0415

    import fenolite.cli.main as cli_main  # noqa: PLC0415
    from fenolite.view.export import embedded  # noqa: PLC0415

    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    p = Project(tmp_path, monkeypatch)
    edit_parts(p, {"R1": {"value": "4k7"}})
    p.edit_script('value="330"', 'value="470"')
    code, env, _ = p.build("--dry-run")
    assert code == 5
    reply = tmp_path / "reply.json"
    reply.write_text(json.dumps(env), encoding="utf-8")
    page = tmp_path / "page.html"
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    args = ["view", str(p.board), "--check", str(reply), "--export", str(page), "--confirm", "--json"]
    assert cli_main.main(args) == 0
    data = embedded(page.read_text(encoding="utf-8"))
    assert data is not None
    (scene,) = data["scenes"].values()
    (conflict,) = [f for f in scene["check"]["findings"] if f["code"] == "sync.conflict"]
    assert conflict["severity"] == "error" and conflict["where"] == "R1#value"
    for text in ("both-changed", "'330'", "'470'", "'4k7'"):
        assert text in conflict["message"]
    fp, _ = footprint(p.read(), "R1")
    x, y = fp.position.x / 1000, fp.position.y / 1000  # type: ignore[attr-defined]
    box = conflict["box"]
    assert box[0] <= x <= box[2] and box[1] <= y <= box[3]
    code_line, cad_line = conflict["commands"]
    assert "--take code:R1#value --dry-run" in code_line and "--take cad:R1#value --dry-run" in cad_line
    assert code_line.startswith("fenolite build ") and f"--out {p.out}" in code_line


def test_build_and_sync_replies_are_read() -> None:
    for command in ("build", "sync"):
        assert read_reply({"command": command, "issues": []})["command"] == command
    placed = overlay(
        {
            "command": "sync",
            "issues": [
                {
                    "code": "sync.conflict",
                    "severity": "error",
                    "message": "U9#value: base 'a', script 'b', board 'c', schematic 'd' (sides-disagree)",
                    "where": "U9#value",
                    "hint": "",
                }
            ],
            "evidence": {"level": "INFERRED"},
        },
        {"prims": [], "pads": [], "comps": [], "nets": [], "meta": {}},
    )
    (conflict,) = placed["findings"]
    assert conflict["at"] is None  # no footprint of that path on the board: listed only
    assert [c.split("--take ")[1] for c in conflict["commands"]] == [
        "board:U9#value --dry-run",
        "schematic:U9#value --dry-run",
    ]
