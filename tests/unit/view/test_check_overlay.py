# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``check`` findings placed on a board or a sheet (capability check-overlay, scenario "Two findings";
change c0188). The replies are authored here."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from _view_conflict import build_conflict

from fenolite.api import run
from fenolite.cli.cmd_view import scene_of
from fenolite.core.errors import FormatError
from fenolite.view.actions import ActionRefused, ActionRequest, Context, plan
from fenolite.view.check_overlay import overlay, read_reply, summary
from fenolite.view.conflicts import bind, current
from fenolite.view.export import embedded, template
from fenolite.view.project import load_tree

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


@pytest.mark.parametrize("major", [9, 10])
def test_workbench_conflict_properties_and_bound_take(tmp_path: Path, major: int) -> None:
    script, board, reply, _ = build_conflict(tmp_path / "authoring", major=major)
    page = tmp_path / "page.html"
    result = run("view", str(board), "--check", str(reply), "--export", str(page), "--confirm", cwd=tmp_path)
    assert result.exit_code == 0, result.error
    data = embedded(page.read_text(encoding="utf-8"))
    assert data is not None
    (scene,) = data["scenes"].values()
    placed = scene["check"]
    index = next(i for i, row in enumerate(placed["findings"]) if row["where"] == "R1#value")
    row = placed["findings"][index]
    assert row["conflict"] == {
        "key": "R1#value",
        "reason": "both-changed",
        "base": "330",
        "code": "470",
        "cad": {"board": "4k7"},
    }
    assert len(row["commands"]) == 2
    context = Context(findings=tuple(placed["findings"]), resolve=placed["resolve"])
    request = plan(
        {"action": "take", "doc": "doc1", "options": {"finding": index, "side": "cad"}},
        load_tree(board),
        context,
    )
    assert isinstance(request, ActionRequest), request
    assert request.words == (
        "build",
        f"--kicad-version={major}",
        f"--out={board.parent}",
        "--take=cad:R1#value",
        "--",
        str(script),
    )
    assert request.binding is not None and request.binding["root"] == str(script.parent)


def test_workbench_typescript_sends_only_finding_and_side() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    html = template()
    model = html[html.index("// ---- inspector model (c0301)") : html.index("// ---- end inspector model")]
    actions = html[html.index("function conflictChoices(") : html.index("function ConflictActions(")]
    script = (
        "const calls=[];const actPlan=(a,o)=>calls.push([a,o]);"
        + model
        + actions
        + 'const x={conflict:{key:"R1#value",reason:"both-changed",base:"330",code:"470",cad:{board:"4k7"}},'
        'commands:["copy code","copy cad"]};'
        'const empty={conflict:{key:"R1#property:x",base:"",code:null,cad:{board:""}}};'
        'conflictTake(3,"cad");console.log(JSON.stringify({rows:findingSection(x,null).rows,'
        "empty:findingSection(empty,null).rows,calls,choices:conflictChoices(x.conflict)}));"
    )
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=60)
    result = json.loads(done.stdout)
    values = {row["label"]: row["value"] for row in result["rows"]}
    assert values["Base"] == "330" and values["Code value"] == "470" and values["CAD board"] == "4k7"
    assert values["Resolve 1 (copy)"] == "copy code" and values["Resolve 2 (copy)"] == "copy cad"
    assert result["calls"] == [["take", {"finding": 3, "side": "cad"}]]
    assert result["choices"] == ["code", "cad"]
    empty = {row["label"]: row["value"] for row in result["empty"]}
    assert empty["Base"] == '""' and empty["CAD board"] == '""' and empty["Code value"] == "absent"


def test_workbench_real_child_plan_confirm_and_undo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The actual Live job/child/plan replay flow, independent of the HTTP listener's socket permission."""
    from fenolite.cli._viewrun import ChildRunner  # noqa: PLC0415
    from fenolite.cli.api import discover  # noqa: PLC0415
    from fenolite.view.server import Live  # noqa: PLC0415

    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    script, board, _, reply = build_conflict(tmp_path / "authoring", major=9)
    before, lock_before = board.read_bytes(), script.with_suffix(".lock").read_bytes()
    session = {"reply": reply}

    def build(path: Path) -> dict[str, Any]:
        scene = scene_of(path)
        placed = overlay(session["reply"], scene)
        placed["resolve"] = bind(
            session["reply"], board=path, cwd=script.parent, board_sha256=scene["meta"]["sha256"]
        )
        return scene | {"check": placed}

    def derive(path: Path, command: str, envelope: dict[str, Any]) -> dict[str, Any]:
        session["reply"] = envelope
        return {}

    tree = load_tree(board)
    runner = ChildRunner(discover(), root=tree.root, timeout=60)
    live = Live(tree, build, runner=runner, actions=runner, derive=derive)

    def finished(job: Any) -> dict[str, Any]:
        deadline = time.monotonic() + 60
        while job.state == "running" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert job.state != "running", "the real child job did not finish"
        return job.to_json()

    scene = build(board)
    index = next(i for i, row in enumerate(scene["check"]["findings"]) if row["where"] == "R1#value")
    planned = finished(
        live.start_plan(
            json.dumps(
                {"action": "take", "doc": "doc1", "options": {"finding": index, "side": "code"}}
            ).encode()
        )
    )
    assert planned["state"] == "done" and planned["plan"]["confirmable"], planned
    assert any(Path(row["path"]) == script.with_suffix(".lock") for row in planned["plan"]["writes"])
    assert board.read_bytes() == before and script.with_suffix(".lock").read_bytes() == lock_before
    done = finished(live.start_confirm(json.dumps({"job": planned["job"]}).encode()))
    assert done["state"] == "done" and done["exit"] == 0, done
    assert board.read_bytes() != before and script.with_suffix(".lock").read_bytes() != lock_before
    stored = json.loads(runner.receipt_file(done["receipt"]["id"]).read_text())
    assert stored["original_receipt"] == done["receipt"]
    assert stored["receipt_root"] == str(script.parent)
    assert all(not Path(row["path"]).is_absolute() for row in stored["receipt"]["written"])
    undo = finished(live.start_undo(json.dumps({"receipt": done["receipt"]["id"]}).encode()))
    assert "plan" in undo, undo
    assert undo["plan"]["confirmable"], undo
    restored = finished(live.start_confirm(json.dumps({"job": undo["job"]}).encode()))
    assert restored["state"] == "done" and restored["exit"] == 0, restored
    assert board.read_bytes() == before and script.with_suffix(".lock").read_bytes() == lock_before


def test_workbench_refuses_unbound_options_stale_and_escaped_inputs(tmp_path: Path) -> None:
    script, board, _, reply = build_conflict(tmp_path / "authoring")
    scene = scene_of(board)
    placed = overlay(reply, scene)
    binding = bind(reply, board=board, cwd=script.parent, board_sha256=scene["meta"]["sha256"])
    context = Context(findings=tuple(placed["findings"]), resolve=binding)
    index = next(i for i, row in enumerate(placed["findings"]) if row["where"] == "R1#value")
    tree = load_tree(board)
    for options in (
        {"finding": True, "side": "cad"},
        {"finding": 1000, "side": "cad"},
        {"finding": index, "side": "mine"},
        {"finding": index, "side": "cad", "root": "/"},
        {"finding": index, "side": "cad", "script": "other.py"},
    ):
        assert isinstance(
            plan({"action": "take", "doc": "doc1", "options": options}, tree, context), ActionRefused
        )
    source_before = script.read_bytes()
    script.write_text(script.read_text() + "\n# Authored stale source.\n")
    assert "changed" in (current(binding, board) or "")
    script.write_bytes(source_before)
    outside = tmp_path / "outside.toml"
    outside.write_text("authored = true\n")
    (script.parent / "edits.toml").symlink_to(outside)
    refused = bind(reply, board=board, cwd=script.parent, board_sha256=scene["meta"]["sha256"])
    assert refused is not None and "outside" in refused["why"]


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


def test_subjects_resolve_id_before_name_with_empty_where():
    scene = {
        "comps": [{"id": "cmp_target", "ref": "C1", "bbox": [1, 2, 3, 4]}],
        "pads": [],
        "prims": [],
        "nets": [],
    }
    reply = _reply({"code": "circuit.rating-voltage", "severity": "error", "message": "rating"})
    reply["result"]["subjects"] = [
        {
            "issue": 0,
            "items": [
                {"kind": "component", "id": "cmp_target", "name": "OLD"},
                {"kind": "net", "id": "net_test", "name": "V12"},
            ],
        }
    ]
    finding = overlay(reply, scene)["findings"][0]
    assert finding["box"] == [1, 2, 3, 4]
    assert finding["stage"] == "circuit.rules"
    assert [s["name"] for s in finding["subjects"]] == ["OLD", "V12"]
    reply["result"]["subjects"][0]["items"][0] = {"kind": "component", "id": "stale", "name": "C1"}
    assert overlay(reply, scene)["placed"] == 1
    reply["result"]["subjects"] = []
    assert overlay(reply, scene)["placed"] == 0


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
    words = shlex.split(code_line)
    assert words[:2] == ["fenolite", "build"]
    assert words[words.index("--out") + 1] == str(p.out)


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


def test_roles_findings_through_group_aliases() -> None:
    """Scenario "A Kelvin finding located" (c0305): ``roles.*`` codes belong to the stage ``roles.rules``, and
    a ``where`` that names a role group, or one pad of it, is placed through the groups given as aliases."""
    pads = [
        {"label": label, "x": x, "y": y}
        for label, x, y in (
            ("R12-1", 1000, 2000),
            ("R12-2", 3000, 2000),
            ("C1-1", 0, 0),
            ("Q1-3", 4000, 5000),
        )
    ]
    scene = {"prims": [], "pads": pads, "comps": [], "nets": [], "meta": {}}
    reply = _reply(
        {
            "code": "roles.kelvin-outer",
            "severity": "warning",
            "message": "outer half",
            "where": "kelvin_R12:R12-1",
        },
        {"code": "roles.loop-area", "severity": "warning", "message": "too large", "where": "hot_SW"},
        {"code": "roles.unconfirmed", "severity": "info", "message": "not confirmed", "where": "roles"},
    )
    groups = {"kelvin_R12": ["R12-1", "R12-2"], "hot_SW": ["C1-1", "Q1-3"]}
    placed = {f["code"]: f for f in overlay(reply, scene, aliases=groups)["findings"]}
    kelvin, loop = placed["roles.kelvin-outer"], placed["roles.loop-area"]
    assert {f["stage"] for f in placed.values()} == {"roles.rules"}
    assert kelvin["at"] == [1000, 2000] and kelvin["where"] == "kelvin_R12:R12-1"
    assert loop["box"] == [0, 0, 4000, 5000] and loop["at"] == [2000.0, 2500.0]
    assert placed["roles.unconfirmed"]["at"] is None
    bare = {f["code"]: f for f in overlay(reply, scene)["findings"]}
    assert bare["roles.kelvin-outer"]["at"] is None and bare["roles.loop-area"]["stage"] == "roles.rules"
