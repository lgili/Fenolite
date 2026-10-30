# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Writing actions from the viewer, end to end: ``fenolite view --serve --allow-actions`` with the real
child-process runner on copies of ``two_layer.kicad_pcb`` (capability board-viewer, "Plan review before a
write", "Confirm by plan", "Receipt and undo"; capability cli-contract, "View command allows writing
actions"; change c0303)."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli import cmd_view
from fenolite.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _Served:
    """``fenolite view BOARD --serve --allow-actions`` in a thread, stopped by the test's event, with its own
    state folder."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        source: Path | None = None,
        extra: tuple[str, ...] = (),
    ) -> None:
        self.folder = tmp_path / "project"
        if source is None:
            self.folder.mkdir()
            self.board = self.folder / BOARD.name
            shutil.copy(BOARD, self.board)
        else:  # a built project: its folder, its model and its project file (change c0280)
            shutil.copytree(source.parent, self.folder)
            self.board = self.folder / source.name
        monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
        self.stop = threading.Event()
        monkeypatch.setattr(cmd_view, "SERVE_STOP", self.stop)
        self.served: list[Any] = []
        original = cmd_view.server.serve

        def serve(live: Any, port: int) -> Any:
            self.served.append(original(live, port))
            return self.served[-1]

        monkeypatch.setattr(cmd_view.server, "serve", serve)
        monkeypatch.chdir(self.folder)
        self.out = io.StringIO()
        self.monkeypatch = monkeypatch
        self.codes: list[int] = []
        argv = [
            "view",
            self.board.name,
            *extra,
            "--serve",
            "--allow-actions",
            "--no-browser",
            "--port",
            "0",
            "--no-models",
        ]
        self.thread = threading.Thread(target=lambda: self.codes.append(cli_main.main([*argv, "--json"])))
        self.thread.daemon = True
        self.token = ""

    def __enter__(self) -> _Served:
        self.monkeypatch.setattr("sys.stdout", self.out)  # here: pytest sets its own capture after setup
        self.monkeypatch.setattr("sys.stderr", io.StringIO())
        self.thread.start()
        deadline = time.monotonic() + 60
        while not self.served and time.monotonic() < deadline:
            time.sleep(0.02)
        self.port = int(self.served[0].server_address[1])
        self.token = self.get("/actions?doc=doc1", {"X-Fenolite-Action": "1"})["token"]
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop.set()
        self.thread.join(60)

    def reply(self) -> dict[str, Any]:
        assert self.codes == [0]
        return json.loads(self.out.getvalue())

    def get(self, route: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{route}", headers=headers or {})
        with urllib.request.urlopen(request, timeout=60) as reply:
            return json.loads(reply.read())

    def post(self, route: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        headers = {
            "Content-Type": "application/json",
            "X-Fenolite-Action": "1",
            "X-Fenolite-Token": self.token,
        }
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{route}",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as reply:
                return reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def job(self, job: str, seconds: float = 300) -> dict[str, Any]:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = self.get(f"/run/{job}")
            if state["state"] != "running":
                return state
            time.sleep(0.05)
        raise AssertionError(f"job {job} did not end")

    def plan(self, action: str, **options: Any) -> dict[str, Any]:
        code, started = self.post("/action/plan", {"action": action, "doc": "doc1", "options": options})
        assert code == 202, started
        return self.job(started["job"])

    def confirm(self, plan: dict[str, Any]) -> dict[str, Any]:
        code, started = self.post("/action/confirm", {"job": plan["job"]})
        assert code == 202, started
        return self.job(started["job"])


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Served:
    return _Served(monkeypatch, tmp_path)


def test_silk_plan_previewed(served: _Served) -> None:
    """Scenario "A designator plan previewed": one write of the board with its digests, a preview, and the
    board unchanged."""
    before = _sha(served.board)
    with served:
        plan = served.plan("silk", designators=True)
    assert plan["state"] == "done", plan
    writes = plan["plan"]["writes"]
    assert [w["path"] for w in writes] == [BOARD.name]
    assert writes[0]["replaces"] == before and len(writes[0]["sha256"]) == 64
    assert plan["plan"]["confirmable"] is True and plan["plan"]["evidence"]["level"]
    preview = plan["preview"]
    assert preview["kind"] == "board" and isinstance(preview["changes"], list)
    assert _sha(served.board) == before


def test_confirm_undo_reply_and_evidence(served: _Served) -> None:
    """Scenario "Write and undo"; scenario "Receipts in the reply"; and the evidence of the command kept."""
    original = _sha(served.board)
    with served:
        plan = served.plan("silk", designators=True)
        done = served.confirm(plan)
        assert done["state"] == "done" and done["exit"] == 0, done
        receipt = done["receipt"]
        assert [w["path"] for w in receipt["written"]] == [BOARD.name] and receipt["backup"]
        assert done["envelope"]["evidence"] == plan["envelope"]["evidence"]
        assert _sha(served.board) != original
        assert served.post("/action/confirm", {"job": plan["job"]})[0] == 400  # a plan is written once
        offer = served.get("/actions?doc=doc1")
        assert offer["receipts"][0]["id"] == receipt["id"]
        code, started = served.post("/action/undo", {"receipt": receipt["id"]})
        assert code == 202, started
        undo = served.job(started["job"])
        assert undo["kind"] == "undo" and undo["plan"]["confirmable"], undo
        restored = served.confirm(undo)
        assert restored["state"] == "done", restored
        assert _sha(served.board) == original
    writes = served.reply()["result"]["serve"]["writes"]
    assert [w["action"] for w in writes] == ["silk", "undo"] and writes[0]["files"] == [BOARD.name]


def test_file_changed_after_the_review(served: _Served) -> None:
    """Scenario "The file changed after the review"."""
    with served:
        plan = served.plan("silk", designators=True)
        text = served.board.read_text(encoding="utf-8")
        start = text.index("(segment")
        depth, end = 0, start
        for end in range(start, len(text)):
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            if depth == 0:
                break
        served.board.write_text(text[:start] + text[end + 1 :], encoding="utf-8")
        rewritten = _sha(served.board)
        done = served.confirm(plan)
    assert done["exit"] == 4 and done["error"]["code"] == "FEN-4002", done
    assert done["review_again"] is True
    assert _sha(served.board) == rewritten


def test_move_shift_and_turn_preview_one_moved_part(served: _Served) -> None:
    with served:
        scene = served.get("/scene/doc1.json")
        r1 = next(c for c in scene["comps"] if c["ref"] == "R1")
        x, y = r1["x"] / 1000 + 1, r1["y"] / 1000
        move = served.plan("move", ref="R1", x=f"{x:.3f}mm", y=f"{y:.3f}mm")
        shift = served.plan("shift", refs=["R1"], dx="1mm", dy="0mm")
        turn = served.plan("turn", refs=["R1"], about_x=f"{x - 1:.3f}mm", about_y=f"{y:.3f}mm", angle="90")
    assert move["state"] == "done", move
    assert "preview" in move, (move.get("preview_note"), move["plan"], move["envelope"]["issues"])
    assert [m["ref"] for m in move["preview"]["moved"]] == ["R1"], move["preview"]["changes"]
    assert move["plan"]["confirmable"] is True
    for plan in (shift, turn):  # on this small board the group moves meet copper, or the part has no library
        assert plan["state"] == "done" and plan["command"] == "place", plan
        errors = [i for i in plan["envelope"]["issues"] if i["severity"] == "error"]
        assert errors and not (plan["plan"] or {}).get("confirmable"), "an error finding plans no write"


def test_bom_and_export_write_under_fab_only(served: _Served) -> None:
    with served:
        bom = served.plan("bom", source="model")
        refused = served.post("/action/plan", {"action": "export", "doc": "doc1", "options": {"out": "../x"}})
    assert bom["state"] == "done", bom
    assert [w["path"] for w in bom["plan"]["writes"]] == ["fab/bom.csv"]
    assert refused[0] == 400 and "leaves the project" in refused[1]["error"]


@pytest.mark.needs_kicad
def test_export_plans_files_under_fab(served: _Served) -> None:
    with served:
        plan = served.plan("export", kinds=["gerbers", "drill"])
    assert plan["state"] == "done", plan
    paths = [w["path"] for w in plan["plan"]["writes"]]
    assert paths and all(p.startswith("fab/") for p in paths)


def test_testpoints_plan(served: _Served) -> None:
    with served:
        plan = served.plan("testpoints", grid="2.54mm")
    assert plan["state"] in ("done", "failed"), plan
    assert plan["command"] == "testpoints"


@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
def test_fill_plan(served: _Served) -> None:
    with served:
        plan = served.plan("fill")
    assert plan["state"] == "done", plan
    assert plan["plan"] is None or all(w["path"] == BOARD.name for w in plan["plan"]["writes"])


@pytest.mark.needs_kicad
def test_tidy_with_the_drc_gate(served: _Served) -> None:
    with served:
        plan = served.plan("tidy", prune=True)
    assert plan["state"] == "done", plan
    assert "--gate" not in json.dumps(plan.get("error") or {})


def test_route_accept_from_the_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Accept a candidate from the page" (c0280): over a copy of the buck role-copper variant and its
    proposal data, ``route-accept`` with a candidate id of the data plans ``route --router octilinear
    --accept=<id> -- <board>`` (the board and the decision record), and an id the data lacks is refused with
    400 naming it."""
    import _roles  # noqa: F401, PLC0415  (puts tests/unit/roles on the path)
    from _proposals import phase2  # noqa: PLC0415  (builds a role-copper board through phase 2)

    built = phase2("buck_shunt", "bad", tmp_path / "p2")
    args = ["route", built.board.name, "--router", "octilinear", "--propose", "--candidates", "1", "--json"]
    code, envelope, error = cli_main.invoke(args, cwd=built.out)
    assert code == 0 and envelope is not None, error
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(envelope), encoding="utf-8")
    chosen = next(
        c["id"]
        for p in envelope["result"]["proposals"]
        if p["subject"] == "fanout:GND:C3-2"
        for c in p["candidates"]
    )
    served = _Served(monkeypatch, tmp_path, built.board, ("--proposals", str(saved)))
    before = _sha(served.board)
    with served:
        plan = served.plan("route-accept", candidates=[chosen])
        refused = served.post(
            "/action/plan",
            {"action": "route-accept", "doc": "doc1", "options": {"candidates": ["c-0000000000000000"]}},
        )
    assert plan["state"] == "done", plan
    assert sorted(Path(w["path"]).name for w in plan["plan"]["writes"]) == sorted(
        [built.board.name, "route-decisions.json"]
    )
    assert refused[0] == 400 and "c-0000000000000000" in json.dumps(refused[1])
    assert _sha(served.board) == before
