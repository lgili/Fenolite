# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0368 authored local-process CLI proposals, no write until reviewed confirmation."""

import shlex
import sys
from pathlib import Path

import pytest
from _fakerouter import create_fake_router

from tests.unit.cli.test_route_search import cli, subject_bench


def tool(tmp_path: Path, monkeypatch):
    checkout = create_fake_router(tmp_path)
    script = checkout / "py_router" / "route.py"
    text = script.read_text().replace(
        "from fenolite.core.coords import Point",
        "from fenolite.core.coords import Point\nfrom fenolite.backends.kicad.frame import board_pads",
    )
    text = text.replace(
        "start=Point(x, row), end=Point(x + 100_000, row + 100_000),",
        "start=held[0].position, end=held[1].position,",
    )
    text = text.replace(
        "track = Track(",
        "held = sorted((p for p in board_pads(design) if p.net == net.name), key=lambda p:p.ref)\n"
        "        track = Track(",
    )
    script.write_text(text)
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(Path(__file__).resolve().parents[3] / "src"))
    monkeypatch.setenv("FENOLITE_KRT", str(checkout))
    monkeypatch.setenv("FENOLITE_KRT_PYTHON", sys.executable)
    return checkout


def words(board):
    return (
        "route",
        str(board),
        "--router",
        "octilinear",
        "--propose-with",
        "kicadroutingtools",
        "--nets",
        "SIG",
    )


def external_rows(reply):
    return [
        candidate
        for proposal in reply["result"]["proposals"]
        for candidate in proposal["candidates"]
        if candidate["source"].startswith("external:")
    ]


@pytest.mark.parametrize("flags", [("--replay",), (), ("--roles", "critical")])
def test_bad_mode_is_usage_error_before_reading_input(tmp_path, flags):
    code, _, err = cli(*words(tmp_path / "missing.kicad_pcb"), *flags)
    assert code == 2 and "FEN-2001" in err


def test_unknown_adapter_is_usage_error_before_reading_input(tmp_path):
    code, _, err = cli(
        "route", str(tmp_path / "missing"), "--router", "octilinear", "--propose", "--propose-with", "cloud"
    )
    assert code == 2 and "FEN-2001" in err


def test_explicit_missing_tool_is_exit_six_and_does_not_change_board(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FENOLITE_KRT", str(tmp_path / "missing-tool"))
    built = subject_bench(tmp_path)
    before = built.board.read_bytes()
    code, _, err = cli(*words(built.board), "--propose")
    assert code == 6 and "FEN-6001" in err
    assert built.board.read_bytes() == before


def test_local_external_proposal_provenance_and_reviewed_acceptance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool(tmp_path, monkeypatch)
    built = subject_bench(tmp_path)
    before = built.board.read_bytes()
    request = (*words(built.board), "--candidates", "1")
    code, reply, err = cli(*request, "--propose")
    assert code == 0, err
    candidates = external_rows(reply)
    assert len(candidates) == 1, reply
    candidate = candidates[0]
    assert candidate["tool"]["router"] == "kicadroutingtools"
    assert candidate["tool"]["version"] == "0.22.1"
    assert candidate["tool"]["deterministic"] is False
    assert len(candidate["tool"]["inputs"]) == 64 and len(candidate["tool"]["job"]) == 64
    assert not {"score", "rank", "cost"} & candidate["facts"].keys()
    assert built.board.read_bytes() == before
    next_command = next(cmd for cmd in reply["result"]["next"] if "--accept " + candidate["id"] in cmd)
    assert "--candidates 1" in next_command
    code, planned, err = cli(*shlex.split(next_command)[1:])
    assert code == 0, err
    assert built.board.read_bytes() == before
    assert planned["result"]["accepted"][0]["tool"] == candidate["tool"]
    plan = planned["result"]["plan_id"]
    monkeypatch.setattr(
        "fenolite.routing.plugins.kicad.routingtools.KicadRoutingToolsRouter.route",
        lambda *_: pytest.fail("confirmation reran external router"),
    )
    code, _, err = cli(*request, "--accept", candidate["id"], "--confirm", "--plan", plan)
    assert code == 0, err
    assert built.board.read_bytes() != before


def test_review_refuses_changed_tool_bytes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    checkout = tool(tmp_path, monkeypatch)
    built = subject_bench(tmp_path)
    code, reply, err = cli(*words(built.board), "--propose")
    assert code == 0, err
    candidate = external_rows(reply)[0]
    code, planned, err = cli(*words(built.board), "--accept", candidate["id"], "--dry-run")
    assert code == 0, err
    before = built.board.read_bytes()
    script = checkout / "py_router" / "route.py"
    script.write_text(script.read_text() + "\n# modified tool bytes\n")
    code, _, err = cli(
        *words(built.board), "--accept", candidate["id"], "--confirm", "--plan", planned["result"]["plan_id"]
    )
    assert code == 4 and "FEN-4002" in err
    assert built.board.read_bytes() == before


def test_capabilities_describe_supported_local_candidate_scope_without_processes(monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("--no-tools started a process"))
    code, reply, err = cli("capabilities", "--brief", "--no-tools")
    assert code == 0, err
    by_name = {r["name"]: r for r in reply["result"]["routers"]}
    for name in ("kicadroutingtools", "freerouting"):
        caps = by_name[name]["external_candidates"]
        assert caps["supported"] and caps["available"] is None
        assert caps["local_only"] and not caps["groups"] and not caps["arcs"]


def test_disconnected_same_net_addition_refuses_whole_external_candidate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    checkout = tool(tmp_path, monkeypatch)
    script = checkout / "py_router" / "route.py"
    needle = "output.write_text(write_board(dataclasses.replace(design, board=board), target=10).text)"
    addition = (
        "stray = dataclasses.replace(board.tracks[-1], id=new_id('trk', random.Random(333)), "
        "start=Point(2000000,2000000), end=Point(3000000,2000000))\n"
        "board = dataclasses.replace(board, tracks=(*board.tracks, stray))\n"
    )
    text = script.read_text()
    assert needle in text
    script.write_text(text.replace(needle, addition + needle))
    built = subject_bench(tmp_path)
    before = built.board.read_bytes()
    code, reply, err = cli(*words(built.board), "--propose")
    assert code == 0, err
    assert not external_rows(reply)
    assert reply["result"]["external"]["refusals"][0]["reason"] == "external-scope"
    assert built.board.read_bytes() == before


def test_repeatable_request_is_deduplicated_and_dispatch_is_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool(tmp_path, monkeypatch)
    runs = tmp_path / "tool-runs.jsonl"
    monkeypatch.setenv("FAKE_ROUTER_RUNS", str(runs))
    built = subject_bench(tmp_path)
    code, reply, err = cli(*words(built.board), "--propose", "--propose-with", "kicadroutingtools")
    assert code == 0, err
    assert len(external_rows(reply)) == 1 and len(runs.read_text().splitlines()) == 1
    assert reply["result"]["external"]["requested"] == ["kicadroutingtools"]
