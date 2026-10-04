# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCadRoutingTools adapter lifts new copper and turns process failures into issues."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from _fakerouter import create_fake_router

from fenolite.core.evidence import Level
from fenolite.routing.merge import apply
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.protocol import JobNet, JobPad, RoutingJob
from tests.unit.routing._designs import routing_design


@pytest.fixture(autouse=True)
def fake_process_import_path(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Path(__file__).resolve().parents[3] / "src"
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(source))


def _job():
    design = routing_design()
    net = next(item for item in design.circuit.nets if item.name == "B")
    pads = design.by_net[net.name]
    job_net = JobNet(
        net.name,
        net.id,
        tuple(JobPad("J1", pad.number, net.name, pad.position, pad.layers, pad.drill) for pad in pads),
        250_000,
        200_000,
        600_000,
        300_000,
    )
    return RoutingJob(design, (job_net,), ("F.Cu", "B.Cu"))


def test_lifts_new_copper_and_runs_in_a_temporary_folder(tmp_path, monkeypatch) -> None:
    checkout = create_fake_router(tmp_path)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_ROUTER_RECORD", str(record))
    router = KicadRoutingToolsRouter(checkout, sys.executable)

    result = router.route(_job())

    assert router.available().available
    assert result.routed == ("B",) and len(result.tracks) == 1, result
    assert result.tracks[0].net_id == _job().nets[0].net_id
    assert result.evidence.level is Level.UNVERIFIED
    saved = json.loads(record.read_text(encoding="utf-8"))
    assert "--nets" in saved["argv"] and "B" in saved["argv"]
    assert "--track-width" in saved["argv"] and "--clearance" in saved["argv"]
    assert "--via-size" in saved["argv"] and "--via-drill" in saved["argv"]
    project = Path(__file__).resolve().parents[3]
    assert "fenolite-route-" in saved["cwd"]
    assert not Path(saved["cwd"]).is_relative_to(project)


def test_failure_is_returned_as_an_issue(tmp_path, monkeypatch) -> None:
    checkout = create_fake_router(tmp_path)
    monkeypatch.setenv("FAKE_ROUTER_MODE", "fail")
    result = KicadRoutingToolsRouter(checkout, sys.executable).route(_job())
    assert result.tracks == () and result.unrouted == ("B",)
    assert result.issues[0].code == "route.tool-failed"
    assert "boom from fake router" in result.issues[0].message


def test_missing_router_is_available_as_a_readiness_result(monkeypatch) -> None:
    monkeypatch.delenv("FENOLITE_KRT", raising=False)
    status = KicadRoutingToolsRouter(path=None, python=sys.executable).available()
    assert not status.available and "FENOLITE_KRT" in status.reason


def test_timeout_and_unpinned_checkout_are_reported(tmp_path, monkeypatch) -> None:
    checkout = create_fake_router(tmp_path, version="0.23.0")
    monkeypatch.setenv("FAKE_ROUTER_MODE", "sleep")
    result = KicadRoutingToolsRouter(checkout, sys.executable, timeout=0.05).route(_job())
    assert {issue.code for issue in result.issues} == {"route.tool-failed", "route.tool-unpinned"}
    assert result.unrouted == ("B",)


def test_router_removal_is_reported_but_not_lifted(tmp_path, monkeypatch) -> None:
    checkout = create_fake_router(tmp_path)
    monkeypatch.setenv("FAKE_ROUTER_MODE", "drop")
    result = KicadRoutingToolsRouter(checkout, sys.executable).route(_job())
    assert any(issue.code == "route.copper-removed" for issue in result.issues)
    assert result.tracks == ()
    assert apply(_job().design, result).board == _job().design.board
