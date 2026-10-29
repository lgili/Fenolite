# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Role writes from the served viewer and their undo (change c0245, decision 11; capability roles-workspace,
"Role writes from the page" and "Undo of role writes")."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli.api import Context
from fenolite.cli.cmd_view import roles_payload, roles_write
from fenolite.cli.main import invoke
from fenolite.view import server
from fenolite.view.project import load_tree

ROOT = Path(__file__).resolve().parents[3]
BUCK = ROOT / "examples" / "roles" / "buck_shunt" / "bad.py"
BOARD = "buck_shunt_bad.kicad_pcb"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("role_writes")
    code, _, error = invoke(["build", str(BUCK), "--out", str(root / "build"), "--confirm"], cwd=root)
    assert code == 0, error
    return root / "build"


@pytest.fixture
def project(built: Path, tmp_path: Path) -> Path:
    shutil.copytree(built, tmp_path / "project")
    return tmp_path / "project"


def _live(folder: Path, *, edit: bool = True) -> server.Live:
    board = folder / BOARD
    ctx = Context(
        mode="json", seed=None, timestamp=datetime.now(UTC), rng=random.Random(0), no_backup=False, cwd=folder
    )
    return server.Live(
        load_tree(board),
        lambda path: {},
        settings={"edit": True} if edit else {},
        roles=lambda path: roles_payload(path, None, ctx),
        roles_writer=lambda path, argv, plan_id: roles_write(path, argv, plan_id, None),
    )


def _call(live: server.Live, route: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return live.role_write(route, json.dumps(body).encode("utf-8"))


def _write(live: server.Live, argv: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Plan ``argv`` and apply it, as Apply does: the plan reply and the receipt."""
    code, plan = _call(live, "/roles/plan", {"doc": "doc1", "argv": argv})
    assert code == 200, plan
    code, done = _call(live, "/roles/confirm", {"doc": "doc1", "plan_id": plan["plan_id"]})
    assert code == 200, done
    return plan, done["receipt"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cli(folder: Path, *argv: str) -> None:
    code, _, error = invoke(["roles", str(folder), *argv, "--confirm"], cwd=folder)
    assert code == 0, error


def test_confirm_from_the_page(project: Path) -> None:
    """Scenario "Confirm a role from the page": the plan writes nothing; Apply writes only the role document,
    with the bytes of the reviewed plan, and the receipt names it with its SHA-256; a second confirm of the
    same plan, or a plan the server did not stage, is refused (FEN-4002) and writes nothing."""
    rules = project / ".fenolite" / "rules.json"
    board_bytes, before = (project / BOARD).read_bytes(), rules.read_bytes()
    live = _live(project)
    code, plan = _call(live, "/roles/plan", {"doc": "doc1", "argv": ["--accept", "GH"]})
    assert code == 200 and rules.read_bytes() == before
    assert [f["path"] for f in plan["result"]["plan"]] == [".fenolite/rules.json"]
    assert plan["current"] == [{"path": ".fenolite/rules.json", "sha256": hashlib.sha256(before).hexdigest()}]
    assert plan["inverse"] == [["--forget", "GH"]]
    code, reply = _call(live, "/roles/confirm", {"doc": "doc1", "plan_id": "0" * 16})
    assert code == 409 and reply["code"] == "FEN-4002" and rules.read_bytes() == before
    code, done = _call(live, "/roles/confirm", {"doc": "doc1", "plan_id": plan["plan_id"]})
    assert code == 200, done
    written = done["receipt"]["written"]
    assert [w["path"] for w in written] == [".fenolite/rules.json"] and written[0]["sha256"] == _sha(rules)
    assert (project / BOARD).read_bytes() == board_bytes
    rows = {r["net"]: r for r in json.loads(live.roles("doc1")[1])["roles"]}
    assert rows["GH"]["state"] == "confirmed"
    code, reply = _call(live, "/roles/confirm", {"doc": "doc1", "plan_id": plan["plan_id"]})
    assert code == 409 and reply["code"] == "FEN-4002"
    code, reply = _call(live, "/roles/plan", {"doc": "doc1", "argv": ["--accept", "GH", "--out", "x"]})
    assert code == 400  # only the role options
    code, reply = _call(live, "/roles/plan", {"doc": "doc1", "argv": ["--forget", "SW"]})
    assert code == 422 and reply["code"] == "FEN-2001"  # a declared role names its script


def test_confirm_needs_the_review_header(project: Path) -> None:
    """The write routes take the review header, JSON and the server's own host, as marks do."""
    live = _live(project)
    httpd = server.serve(live, 0)
    port = httpd.server_address[1]
    stop = threading.Event()
    thread = threading.Thread(target=server.run, args=(live, httpd), kwargs={"until": stop}, daemon=True)
    thread.start()
    try:
        body = json.dumps({"doc": "doc1", "argv": ["--accept", "GH"]}).encode("utf-8")
        for headers, status in (
            ({"Content-Type": "application/json"}, 403),
            ({"Content-Type": "application/json", server.REVIEW_HEADER: "1"}, 200),
        ):
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/roles/plan", data=body, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as reply:
                    code = reply.status
            except urllib.error.HTTPError as error:
                code = error.code
            assert code == status
    finally:
        stop.set()
        thread.join(timeout=10)
        httpd.server_close()


def test_readonly_without_edit(project: Path) -> None:
    """Scenario "Read-only without edit": without --edit every write route is refused and nothing is
    written; the data route still serves the workspace."""
    rules = project / ".fenolite" / "rules.json"
    before = rules.read_bytes()
    live = _live(project, edit=False)
    for route, body in (
        ("/roles/plan", {"doc": "doc1", "argv": ["--accept", "GH"]}),
        ("/roles/confirm", {"doc": "doc1", "plan_id": "0" * 16}),
    ):
        code, reply = _call(live, route, body)
        assert code == 403 and "--edit" in reply["error"]
    assert rules.read_bytes() == before
    assert live.roles("doc1")[0] == 200


WRITES: list[tuple[str, list[str], list[str]]] = [
    # (kind, options set up first from the command line, the write from the page)
    ("accept", [], ["--accept", "GH"]),
    ("accept-all", [], ["--accept-all", "--min-confidence", "high"]),
    ("set", ["--accept", "VB"], ["--set", "VB=signal"]),
    ("reject", [], ["--reject", "GL"]),
    ("forget", ["--accept", "VDRV", "--current", "VDRV=0.25"], ["--forget", "VDRV"]),
    ("current", [], ["--current", "VB=1.5"]),
    ("accept-group", [], ["--accept-group", "gate_Q1"]),
    ("reject-group", ["--accept-group", "hot_SW"], ["--reject-group", "hot_SW"]),
    ("forget-group", ["--reject-group", "kelvin_R12"], ["--forget-group", "kelvin_R12"]),
]


@pytest.mark.parametrize(("kind", "setup", "argv"), WRITES, ids=[w[0] for w in WRITES])
def test_undo_restores_the_bytes(project: Path, kind: str, setup: list[str], argv: list[str]) -> None:
    """Scenario "Undo restores the bytes": each of the nine write kinds, undone by the inverse the server gave
    with its plan, leaves the role document with the bytes it had before the write; redo writes the same
    bytes as the write."""
    rules = project / ".fenolite" / "rules.json"
    if setup:
        _cli(project, *setup)
    before = rules.read_bytes()
    live = _live(project)
    plan, receipt = _write(live, argv)
    after = rules.read_bytes()
    assert after != before, kind
    assert receipt["written"][0]["sha256"] == hashlib.sha256(after).hexdigest()
    assert plan["inverse"], kind
    for step in plan["inverse"]:
        _write(live, step)
    assert rules.read_bytes() == before, kind
    _write(live, argv)  # redo
    assert rules.read_bytes() == after, kind


def test_undo_stops_on_a_changed_file(project: Path) -> None:
    """Scenario "Changed file stops undo": after a command line changed the role document, the inverse plan
    names a file whose SHA-256 is no longer the receipt's, so the page keeps it in Pending; planning writes
    nothing."""
    rules = project / ".fenolite" / "rules.json"
    live = _live(project)
    plan, receipt = _write(live, ["--accept", "GH"])
    _cli(project, "--accept", "GL")
    changed = rules.read_bytes()
    code, undo = _call(live, "/roles/plan", {"doc": "doc1", "argv": plan["inverse"][0]})
    assert code == 200
    assert undo["current"][0]["sha256"] != receipt["written"][0]["sha256"]
    assert rules.read_bytes() == changed
    rows = {r["net"]: r for r in json.loads(live.roles("doc1")[1])["roles"]}
    assert rows["GL"]["state"] == "confirmed"  # the page reads the command line's write
