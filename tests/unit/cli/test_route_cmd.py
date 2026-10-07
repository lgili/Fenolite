# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import dataclasses
import json
import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run
from _fakefreerouting import create_fake_jar, create_fake_java
from _fakerouter import create_fake_router
from _openconn import rb
from _resources import posix_tools
from _specctra import two_pads

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli import cmd_route
from fenolite.cli._examples import EXAMPLE_UNROUTED
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.board import Track, Zone
from fenolite.model.design import Design
from fenolite.routing import registry
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.plugins.specctra.freerouting import FreeroutingRouter
from fenolite.routing.protocol import RouterStatus, RoutingJob, RoutingResult

ROOT = Path(__file__).resolve().parents[3]


def test_example_route_dry_run(monkeypatch, tmp_path: Path) -> None:
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"),
        "--router",
        "direct",
        "--out",
        "routed.kicad_pcb",
        "--rip",
        "--dry-run",
    )
    assert code == 0, (env, error)
    assert env["result"]["routed"] == ["ROUTE_ME"]
    assert env["result"]["ripped"] == 0
    assert env["evidence"]["level"] == "UNVERIFIED"
    assert env["result"]["plan"][0]["path"] == "routed.kicad_pcb"


def test_unknown_router(monkeypatch, tmp_path: Path) -> None:
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, env, error, _ = run(monkeypatch, tmp_path, "route", str(board), "--router", "nope", "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001"


def test_fake_router_and_net_filter(monkeypatch, tmp_path: Path) -> None:
    checkout = create_fake_router(tmp_path)
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(ROOT / "src"))
    router = KicadRoutingToolsRouter(checkout, sys.executable)
    monkeypatch.setattr(cmd_route, "_router", lambda _name, _args: router)
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(board),
        "--router",
        "kicadroutingtools",
        "--nets",
        "ROUTE*",
        "--out",
        "routed.kicad_pcb",
        "--dry-run",
    )
    assert code == 0, (env, error)
    assert env["result"]["selected"] == ["ROUTE_ME"]
    # the fake tool appends a short track that joins nothing; the plugin lists the net as routed, and the
    # verdict comes from the board after the merge (change c0108)
    assert env["result"]["routed"] == [] and env["result"]["unrouted"] == ["ROUTE_ME"]
    assert env["result"]["connections"] == {"before": 1, "after": 1}
    messages = [issue["message"] for issue in env["issues"] if issue["code"] == "route.unrouted"]
    assert len(messages) == 1 and "listed the net as routed" in messages[0]
    assert env["result"]["plan"][0]["path"] == "routed.kicad_pcb"


def test_offsite_router_requires_explicit_flag(monkeypatch, tmp_path: Path) -> None:
    class Offsite:
        name = "offsite"
        description = "test"
        sends_data_offsite = True

        def available(self):
            from fenolite.routing.protocol import RouterStatus

            return RouterStatus(True)

    monkeypatch.setattr(cmd_route, "_router", lambda _name, _args: Offsite())
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, _, error, _ = run(monkeypatch, tmp_path, "route", str(board), "--router", "offsite", "--dry-run")
    assert code == 2 and "sends design data offsite" in error["message"]


def test_log_paths_are_redacted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    lines = cmd_route._safe_log((f"tool used {tmp_path}/router and {Path.home()}/board.kicad_pcb",), tmp_path)
    assert lines == ["tool used <tmp>/router and <home>/board.kicad_pcb"]


def test_routing_marks_existing_fills_stale(monkeypatch, tmp_path: Path) -> None:
    source = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    design = read_board(source.read_text(encoding="utf-8"))
    assert design.board is not None
    net = next(item for item in design.circuit.nets if item.name == "ROUTE_ME")
    zone = Zone(
        id="zone_test",
        outline=(Point(0, 0), Point(1_000_000, 0), Point(1_000_000, 1_000_000), Point(0, 1_000_000)),
        name="filled zone",
        layers=("F.Cu",),
        net_id=net.id,
        filled=True,
    )
    board = replace(design.board, zones=(zone,))
    synthetic = replace(design, board=board)
    board_path = tmp_path / "filled.kicad_pcb"
    board_path.write_text(write_board(synthetic, target=10).text, encoding="utf-8")
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(board_path),
        "--router",
        "direct",
        "--include-zone-nets",
        "--dry-run",
    )
    assert code == 0, (env, error)
    assert env["result"]["fills_stale"] is True
    assert "route.fill-stale" in [issue["code"] for issue in env["issues"]]
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", str(board_path), "--router", "direct", "--dry-run"
    )
    assert code == 0, (env, error)
    assert env["result"]["fills_stale"] is False
    assert "route.zone-net-skipped" in [issue["code"] for issue in env["issues"]]


class _RecordingRouter:
    """A router that keeps the job it was given and routes nothing."""

    name = "recorder"
    description = "records its job"
    sends_data_offsite = False

    def __init__(self) -> None:
        self.jobs: list[RoutingJob] = []

    def available(self) -> RouterStatus:
        return RouterStatus(True)

    def route(self, job: RoutingJob) -> RoutingResult:
        self.jobs.append(job)
        return RoutingResult(unrouted=tuple(net.name for net in job.nets), tool=self.name)


def test_job_extra_holds_the_board_pads_and_the_outline(monkeypatch, tmp_path: Path) -> None:
    """Capability routing, "Job extras" (c0023): scenario "Extras passed by the command"."""
    router = _RecordingRouter()
    monkeypatch.setattr(cmd_route, "_router", lambda _name, _args: router)
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, env, error, _ = run(monkeypatch, tmp_path, "route", str(board), "--router", "recorder", "--dry-run")
    assert code == 0, (env, error)
    (job,) = router.jobs
    assert set(job.extra) == {"board_pads", "outline"}
    pads = job.extra["board_pads"]
    assert isinstance(pads, tuple) and pads and all(isinstance(pad, BoardPad) for pad in pads)
    assert {pad.net for pad in pads if pad.net} >= {net.name for net in job.nets}
    outline = job.extra["outline"]
    assert isinstance(outline, tuple) and all(isinstance(point, Point) for ring in outline for point in ring)


def test_freerouting_is_refused_without_allow_offsite(monkeypatch, tmp_path: Path) -> None:
    """Capability cli-contract, "Freerouting in doctor" (c0023): scenario "Refused without the flag". The
    scenario is about a plugin that sends data, which the shipped one no longer is, so the test sets it."""
    monkeypatch.setattr(FreeroutingRouter, "sends_data_offsite", True)
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(create_fake_jar(tmp_path)))
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path)))
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, _env, error, _ = run(
        monkeypatch, tmp_path, "route", str(board), "--router", "freerouting", "--dry-run"
    )
    assert code == 2 and error["code"] == "FEN-2001"
    assert "--allow-offsite" in error["hint"]


def test_missing_jar_names_the_fetch_command(monkeypatch, tmp_path: Path) -> None:
    """Capability routing, "Freerouting plugin" (c0078): scenario "Missing jar names the command"."""
    monkeypatch.delenv("FENOLITE_FREEROUTING_JAR", raising=False)
    monkeypatch.setenv("FENOLITE_TOOLS_DIR", str(tmp_path / "no-tools"))
    board = tmp_path / "two_pads.kicad_pcb"
    board.write_text(write_board(two_pads().design, target=10).text, encoding="utf-8")
    code, _env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "freerouting", "--dry-run"
    )
    assert code == 6 and error["code"] == "FEN-6001" and error["retryable"] is True
    assert error["hint"] == "run 'fenolite fetch freerouting --confirm'"
    assert "fenolite fetch freerouting --confirm" in error["message"]
    hide_kicad(monkeypatch, tmp_path)  # doctor then finds no tool of this machine to run
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor")
    entry = next(router for router in env["result"]["routers"] if router["name"] == "freerouting")
    assert code == 0 and entry["available"] is False and entry["source"] is None
    assert "fenolite fetch freerouting --confirm" in entry["reason"]
    # a jar that is named but absent is a missing jar too
    code, _env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "freerouting",
        "--router-path", str(tmp_path / "absent.jar"), "--dry-run",
    )  # fmt: skip
    assert code == 6 and error["hint"] == "run 'fenolite fetch freerouting --confirm'"


@posix_tools
def test_missing_jar_hint_is_not_given_for_a_missing_java(monkeypatch, tmp_path: Path) -> None:
    """With a jar and no suitable Java the registry's hint stays: ``fetch`` installs no Java."""
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path, version="17.0.2")))
    board = tmp_path / "two_pads.kicad_pcb"
    board.write_text(write_board(two_pads().design, target=10).text, encoding="utf-8")
    code, _env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "freerouting",
        "--router-path", str(create_fake_jar(tmp_path)), "--dry-run",
    )  # fmt: skip
    assert code == 6 and error["code"] == "FEN-6001" and "Java 25" in error["message"]
    assert "fetch" not in error["hint"] and "capabilities" in error["hint"]


@posix_tools
def test_freerouting_through_the_command(monkeypatch, tmp_path: Path) -> None:
    """The whole path with a fake java: ``--router-path`` names the jar, ``--router-option max-passes``
    reaches the command line, and the authored session's copper is planned into the board."""
    board = tmp_path / "two_pads.kicad_pcb"
    board.write_text(write_board(two_pads().design, target=10).text, encoding="utf-8")
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path)))
    monkeypatch.setenv("FAKE_JAVA_SESSION", str(ROOT / "tests/data/specctra/two_pads.ses"))
    monkeypatch.delenv("FAKE_JAVA_MODE", raising=False)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_JAVA_RECORD", str(record))
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        board.name,
        "--router",
        "freerouting",
        "--router-path",
        str(create_fake_jar(tmp_path)),
        "--router-option",
        "max-passes=3",
        "--allow-offsite",
        "--out",
        "routed.kicad_pcb",
        "--dry-run",
    )
    assert code == 0, (env, error)
    result = env["result"]
    assert result["router"] == "freerouting" and result["tool_version"] == "2.4.1"
    assert result["selected"] == ["A"] and result["routed"] == ["A"] and result["unrouted"] == []
    assert (result["tracks"], result["vias"]) == (2, 1)
    assert result["plan"][0]["path"] == "routed.kicad_pcb"
    assert env["evidence"]["level"] == "UNVERIFIED" and "2.4.1" in env["evidence"]["oracle"]
    argv = json.loads(record.read_text(encoding="utf-8"))["argv"]
    assert argv[argv.index("-mp") + 1] == "3" and "-da" in argv


@posix_tools
def test_freerouting_needs_a_board_outline(monkeypatch, tmp_path: Path) -> None:
    """A board without an outline cannot be written as a design file: ``route.tool-failed``, no run."""
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path)))
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_JAVA_RECORD", str(record))
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(board),
        "--router",
        "freerouting",
        "--router-path",
        str(create_fake_jar(tmp_path)),
        "--allow-offsite",
        "--dry-run",
    )
    assert code == 5, (env, error)
    failed = [issue for issue in env["issues"] if issue["code"] == "route.tool-failed"]
    assert failed and "outline" in failed[0]["message"]
    assert not record.exists()


def test_net_classes_come_from_the_project(monkeypatch, tmp_path: Path) -> None:
    """A KiCad board holds no net class: ``route`` reads them from the project beside the board, so a
    router gets the track width of each net's own class and not the default (c0023; found by the
    acceptance loop of c0025, where the supply nets were routed at the default width)."""
    code, _env, error, _ = run(
        monkeypatch,
        tmp_path,
        "build",
        str(ROOT / "examples" / "blink_2layer" / "design.py"),
        "--out",
        str(tmp_path / "blink"),
        "--confirm",
    )
    assert code == 0, error
    board_path = tmp_path / "blink" / "blink.kicad_pcb"
    design = read_board(board_path.read_text(encoding="utf-8"), file=board_path.name)
    assert not [net for net in design.circuit.nets if net.netclass_id], "the board alone names no class"
    issues: list[Issue] = []
    classed = cmd_route._with_project_classes(design, board_path, issues)  # pyright: ignore[reportPrivateUsage]
    classes = {item.id: item for item in classed.circuit.netclasses}
    widths = {
        net.name: classes[net.netclass_id].track_width for net in classed.circuit.nets if net.netclass_id
    }
    assert widths["VIN"] == widths["GND"] == 500_000
    assert "LED_DRV" not in widths or widths["LED_DRV"] != 500_000

    board_path.with_suffix(".kicad_pro").write_text("{ not json", encoding="utf-8")
    issues = []
    assert cmd_route._with_project_classes(design, board_path, issues) is design  # pyright: ignore[reportPrivateUsage]
    assert [(issue.code, issue.severity) for issue in issues] == [("route.project-unread", "warning")]
    assert cmd_route._with_project_classes(design, tmp_path / "none.kicad_pcb", []) is design  # pyright: ignore[reportPrivateUsage]


# --- open nets (change c0108) ------------------------------------------------------------------------

MM = 1_000_000
NET = "ROUTE_ME"
PLAIN_UUID = "0a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d"
LOCKED_UUID = "1a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d"


def _track(design: Design, start: Point, end: Point, native: str, *, locked: bool = False) -> Track:
    net = next(item for item in design.circuit.nets if item.name == NET)
    return Track(
        id=derived_id("trk", "kicad", native),
        native_ids={"kicad": native},
        start=start,
        end=end,
        width=250_000,
        layer="F.Cu",
        net_id=net.id,
        locked=locked,
    )


def stub_board(folder: Path, *tracks: tuple[Point, Point, str, bool], name: str = "board.kicad_pcb") -> Path:
    """The authored two-pad board (``J1-1`` at the origin, ``J2-1`` 10 mm to its right) with ``tracks``
    (start, end, KiCad uuid, locked) on its net."""
    design = read_board(Path(EXAMPLE_UNROUTED).read_text(encoding="utf-8"))
    assert design.board is not None
    added = tuple(_track(design, a, b, native, locked=locked) for a, b, native, locked in tracks)
    design = dataclasses.replace(
        design, board=dataclasses.replace(design.board, tracks=(*design.board.tracks, *added))
    )
    path = folder / name
    path.write_text(write_board(design, target=10).text, encoding="utf-8")
    return path


def segments(path: Path) -> list[Track]:
    design = read_board(path.read_text(encoding="utf-8"))
    assert design.board is not None
    return list(design.board.tracks)


class _Router:
    name = "test"
    description = "a test router"
    sends_data_offsite = False

    def __init__(self) -> None:
        self.jobs: list[RoutingJob] = []

    def available(self) -> RouterStatus:
        return RouterStatus(True)


class StubRouter(_Router):
    """Returns one 2 mm track from the first pad of every net, and claims what ``claim`` says."""

    def __init__(self, name: str, claim: str) -> None:
        super().__init__()
        self.name, self.claim = name, claim

    def route(self, job: RoutingJob) -> RoutingResult:
        self.jobs.append(job)
        tracks = tuple(
            Track(
                id="",
                start=net.pads[0].position,
                end=Point(net.pads[0].position.x + 2 * MM, net.pads[0].position.y),
                width=net.width,
                layer="F.Cu",
                net_id=net.net_id,
            )  # fmt: skip
            for net in job.nets
        )
        names = tuple(net.name for net in job.nets)
        if self.claim == "routed":
            return RoutingResult(tracks=tracks, routed=names, tool=self.name, tool_version="1")
        return RoutingResult(tracks=tracks, unrouted=names, tool=self.name, tool_version="1")


class OneStepRouter(_Router):
    """Joins the shortest open connection of each net, one per run."""

    name = "test-one-step"

    def route(self, job: RoutingJob) -> RoutingResult:
        self.jobs.append(job)
        pads = job.extra["board_pads"]
        assert isinstance(pads, tuple)
        typed = tuple(pad for pad in pads if isinstance(pad, BoardPad))
        report = connectivity(job.design, pads=typed, nets=[net.name for net in job.nets])
        tracks: list[Track] = []
        for net in job.nets:
            found = report.net(net.name)
            assert found is not None and found.open
            first = min(found.open, key=lambda link: link.length)
            tracks.append(Track(id="", start=first.a.position, end=first.b.position,
                                width=net.width, layer="F.Cu", net_id=net.net_id))  # fmt: skip
        names = tuple(net.name for net in job.nets)
        return RoutingResult(tracks=tuple(tracks), routed=names, tool=self.name, tool_version="1")


@pytest.fixture
def test_routers() -> Iterator[dict[str, _Router]]:
    """Test routers registered through ``routing.registry.register``, removed again after the test."""
    made: dict[str, _Router] = {
        "test-claims": StubRouter("test-claims", "routed"),
        "test-partial": StubRouter("test-partial", "unrouted"),
        "test-one-step": OneStepRouter(),
    }
    for router in made.values():
        registry.register(router)  # type: ignore[arg-type]
    try:
        yield made
    finally:
        for name in made:
            registry._BUILTINS.pop(name, None)  # pyright: ignore[reportPrivateUsage]


def codes(env: dict) -> list[str]:
    return [issue["code"] for issue in env["issues"]]


# --- the example and the selection ------------------------------------------------------------------


def test_example_confirm_routes_the_two_pads(monkeypatch, tmp_path: Path) -> None:
    """Scenario "Direct route of the example"."""
    args = cmd_route.COMMAND.mutation_example_args
    assert args is not None and cmd_route.COMMAND.paged == "open"
    code, env, error, _ = run(monkeypatch, tmp_path, "route", *args, "--confirm")
    assert code == 0, (env, error)
    result = env["result"]
    assert result["routed"] == [NET] and result["selected"] == [NET] and result["unrouted"] == []
    assert result["connections"] == {"before": 1, "after": 0} and result["open"] == []
    assert result["rip_kept"] == {"locked": 0, "script": 0}
    assert env["evidence"]["level"] == "UNVERIFIED"
    assert len(segments(tmp_path / "fenolite-routed.kicad_pcb")) == len(segments(Path(EXAMPLE_UNROUTED))) + 1


def test_nothing_to_route_on_a_closed_board(monkeypatch, tmp_path: Path) -> None:
    """Scenario "Nothing to route"."""
    board = stub_board(tmp_path, (Point(0, 0), Point(10 * MM, 0), PLAIN_UUID, False))
    before = board.read_bytes()
    code, env, error, _ = run(monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--confirm")
    assert code == 0, (env, error)
    result = env["result"]
    assert result["selected"] == [] and result["open"] == []
    assert result["connections"] == {"before": 0, "after": 0}
    assert "receipt" not in env or not env["receipt"]
    assert board.read_bytes() == before


def test_stub_net_is_routed(monkeypatch, tmp_path: Path) -> None:
    """Scenario "A net with a stub is routed": copper of its own does not exclude a net."""
    board = stub_board(tmp_path, (Point(0, 0), Point(3 * MM, 0), PLAIN_UUID, False))
    code, env, error, _ = run(monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--confirm")
    assert code == 0, (env, error)
    result = env["result"]
    assert result["selected"] == [NET] and result["routed"] == [NET] and result["unrouted"] == []
    assert result["connections"] == {"before": 1, "after": 0}
    found = segments(board)
    assert len(found) == 2
    assert [t for t in found if t.native_ids.get("kicad") == PLAIN_UUID and t.end == Point(3 * MM, 0)]


def test_a_closed_net_is_not_given_to_the_router(monkeypatch, tmp_path: Path, test_routers) -> None:
    """Scenario "A closed net is not given to the router"."""
    builder = rb.Builder()
    for index, net in enumerate(("CLOSED", "OPEN")):
        y = builder.row()
        builder.part(f"a{index}", f"RA{index}", Point(rb.LEFT, y), target=10, nets={"1": net})
        builder.part(f"b{index}", f"RB{index}", Point(rb.RIGHT, y), target=10, nets={"1": net})
        if net == "CLOSED":
            builder.track("joined", net, y, x0=rb.LEFT - 800_000, x1=rb.RIGHT - 800_000)
    board = tmp_path / "two_nets.kicad_pcb"
    board.write_text(write_board(builder.build().design, target=10).text, encoding="utf-8")
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "test-partial", "--dry-run"
    )
    assert code == 0, (env, error)
    (job,) = test_routers["test-partial"].jobs
    assert [net.name for net in job.nets] == ["OPEN"]
    assert env["result"]["selected"] == ["OPEN"]


# --- the verdict after the merge --------------------------------------------------------------------


def test_claim_of_the_router_does_not_decide(monkeypatch, tmp_path: Path, test_routers) -> None:
    """Scenario "The router's claim does not decide"."""
    board = stub_board(tmp_path)
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "test-claims", "--confirm"
    )
    assert code == 0, (env, error)
    result = env["result"]
    assert result["routed"] == [] and result["unrouted"] == [NET]
    assert result["connections"] == {"before": 1, "after": 1}
    (entry,) = result["open"]
    assert entry["net"] == NET and entry["islands"] == 2
    (link,) = entry["connections"]
    assert link["length"] == 8 * MM
    ends = {link["a"]["kind"]: link["a"], link["b"]["kind"]: link["b"]}
    assert ends["track"]["position"] == {"x": 2 * MM, "y": 0} and ends["pad"]["where"] == "J2-1"
    assert ends["pad"]["layers"] == ["F.Cu", "B.Cu"] and ends["track"]["layers"] == ["F.Cu"]
    assert codes(env).count("route.partial") == 1 and codes(env).count("route.unrouted") == 1
    (warning,) = [issue for issue in env["issues"] if issue["code"] == "route.unrouted"]
    assert warning["severity"] == "warning" and "listed the net as routed" in warning["message"]
    assert "1 open connection" in warning["message"] and "8mm" in warning["message"].replace(" ", "")
    assert env["receipt"]["written"][0]["path"] == board.name
    (track,) = segments(board)
    assert (track.start, track.end) == (Point(0, 0), Point(2 * MM, 0))


def test_partial_copper_is_merged(monkeypatch, tmp_path: Path, test_routers) -> None:
    """Scenario "Partial copper is merged" (capability routing, "Router copper on open nets")."""
    board = stub_board(tmp_path)
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "test-partial", "--confirm"
    )
    assert code == 0, (env, error)
    assert env["result"]["unrouted"] == [NET] and env["result"]["tracks"] == 1
    (info,) = [issue for issue in env["issues"] if issue["code"] == "route.partial"]
    assert info["severity"] == "info" and NET in info["message"] and "1 item" in info["message"]
    (warning,) = [issue for issue in env["issues"] if issue["code"] == "route.unrouted"]
    assert "listed the net as routed" not in warning["message"]
    assert len(segments(board)) == 1
    assert env["result"]["fills_stale"] is False


def test_required_complete_writes_nothing(monkeypatch, tmp_path: Path, test_routers) -> None:
    """Scenario "Required complete"."""
    board = stub_board(tmp_path)
    before = board.read_bytes()
    code, env, _error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        board.name,
        "--router",
        "test-claims",
        "--require-complete",
        "--confirm",
    )
    assert code == 5
    (failed,) = [issue for issue in env["issues"] if issue["code"] == "route.incomplete"]
    assert (
        failed["severity"] == "error" and NET in failed["message"] and "1 selected net" in failed["message"]
    )
    assert not env.get("receipt") and "plan" not in env["result"]
    assert board.read_bytes() == before
    assert env["result"]["unrouted"] == [NET] and len(env["result"]["open"]) == 1
    # a run that closes every net is not stopped by the option
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--require-complete", "--confirm"
    )
    assert code == 0, (env, error)
    assert "route.incomplete" not in codes(env) and env["result"]["routed"] == [NET]


def test_second_pass_completes_a_net(monkeypatch, tmp_path: Path, test_routers) -> None:
    """Scenario "A second pass completes a net": three pads, one connection joined per run."""
    builder = rb.Builder()
    y = builder.row()
    builder.part("a", "RA", Point(rb.LEFT, y), target=10, nets={"1": "N3"})
    builder.part("b", "RB", Point(rb.RIGHT, y), target=10, nets={"1": "N3"})
    builder.part("c", "RC", Point(rb.LEFT + 5 * MM, y + 4 * MM), target=10, nets={"1": "N3"})
    board = tmp_path / "three.kicad_pcb"
    board.write_text(write_board(builder.build().design, target=10).text, encoding="utf-8")
    args = ("route", board.name, "--router", "test-one-step", "--confirm")
    code, env, error, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0, (env, error)
    assert env["result"]["unrouted"] == ["N3"] and env["result"]["connections"] == {"before": 2, "after": 1}
    assert codes(env).count("route.partial") == 1
    code, env, error, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0, (env, error)
    assert env["result"]["selected"] == ["N3"] and env["result"]["routed"] == ["N3"]
    assert env["result"]["connections"] == {"before": 1, "after": 0}
    assert len(segments(board)) == 2
    # a third run finds nothing to do and writes nothing
    before = board.read_bytes()
    code, env, error, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0 and env["result"]["selected"] == [] and board.read_bytes() == before


def test_open_list_is_paged(monkeypatch, tmp_path: Path, test_routers) -> None:
    board = stub_board(tmp_path)
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "test-claims", "--dry-run", "--limit", "1"
    )
    assert code == 0, (env, error)
    assert env["result"]["page"]["path"] == "open" and env["result"]["page"]["total"] == 1


# --- locks and the rip ------------------------------------------------------------------------------


def test_rip_keeps_locked_and_script_copper(monkeypatch, tmp_path: Path) -> None:
    """Scenario "Rip keeps locked and script copper"."""
    script = copper_uuid("stub", "seg[0]")
    board = stub_board(
        tmp_path,
        (Point(0, 2 * MM), Point(MM, 2 * MM), LOCKED_UUID, True),
        (Point(0, 3 * MM), Point(MM, 3 * MM), script, False),
        (Point(0, 4 * MM), Point(MM, 4 * MM), PLAIN_UUID, False),
    )
    assert board.read_text(encoding="utf-8").count("(locked yes)") == 1
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--rip", "--nets", NET,
        "--out", "routed.kicad_pcb", "--confirm",
    )  # fmt: skip
    assert code == 0, (env, error)
    result = env["result"]
    assert result["ripped"] == 1 and result["rip_kept"] == {"locked": 1, "script": 1}
    kept = {track.native_ids.get("kicad") for track in segments(tmp_path / "routed.kicad_pcb")}
    assert {LOCKED_UUID, script} <= kept and PLAIN_UUID not in kept and len(kept) == 3
    written = (tmp_path / "routed.kicad_pcb").read_text(encoding="utf-8")
    assert written.count("(locked yes)") == 1
    # without --rip nothing is ripped and nothing is counted as kept
    code, env, error, _ = run(monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--dry-run")
    assert code == 0 and env["result"]["ripped"] == 0
    assert env["result"]["rip_kept"] == {"locked": 0, "script": 0}


def test_rip_without_new_copper_is_not_written(monkeypatch, tmp_path: Path, test_routers) -> None:
    """A rip that is followed by no new copper plans no write (design, Decision 8)."""

    class Nothing(_Router):
        name = "test-nothing"

        def route(self, job: RoutingJob) -> RoutingResult:
            return RoutingResult(unrouted=tuple(net.name for net in job.nets), tool=self.name)

    monkeypatch.setattr(cmd_route, "_router", lambda _name, _args: Nothing())
    board = stub_board(tmp_path, (Point(0, 0), Point(10 * MM, 0), PLAIN_UUID, False))
    before = board.read_bytes()
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", board.name, "--router", "test-nothing", "--rip", "--confirm"
    )
    assert code == 0, (env, error)
    assert env["result"]["ripped"] == 1 and env["result"]["unrouted"] == [NET]
    assert "route.partial" not in codes(env) and not env.get("receipt")
    assert board.read_bytes() == before
