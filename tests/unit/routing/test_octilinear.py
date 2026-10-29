# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The octilinear router (change c0228; capability routing, "Octilinear router plugin" and the requirements
after it), on the authored benches of ``tests/_octibench.py``."""

from __future__ import annotations

import dataclasses
import io
import json
from pathlib import Path
from typing import Any

import pytest
from _octibench import CLEARANCE, WIDTH, dots, gate_loop, sense
from _reusebench import project_files

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.cli import cmd_route
from fenolite.cli import main as cli_main
from fenolite.core.coords import Point
from fenolite.model.board import Track
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject
from fenolite.routing.codes import ISSUE_CODES
from fenolite.routing.octilinear import (
    MAX_LENGTH,
    OctilinearRouter,
    bends_ok,
    fresh,
    offset,
    shapes,
    simplify,
)
from fenolite.routing.protocol import (
    JobNet,
    JobPad,
    JobPair,
    RouterStatus,
    RoutingJob,
    RoutingResult,
    router_features,
)
from fenolite.routing.registry import routers

MM = 1_000_000


def _p(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def job(design: Design, names: tuple[str, ...], **options: object) -> RoutingJob:
    """A job of ``names`` as ``fenolite route`` builds it, without the command's checks."""
    pads = board_pads(design)
    ids = {net.name: net.id for net in design.circuit.nets}
    nets = tuple(
        JobNet(
            name,
            ids[name],
            tuple(
                JobPad(pad.ref, pad.number, name, pad.position, pad.layers) for pad in pads if pad.net == name
            ),
            WIDTH,
            CLEARANCE,
            600_000,
            300_000,
        )
        for name in sorted(names)
    )
    return RoutingJob(
        design,
        nets,
        ("F.Cu", "B.Cu"),
        {key: str(value) for key, value in options.items()},
        {"board_pads": pads, "outline": board_outline(design).rings},
    )


def route_cli(
    monkeypatch: pytest.MonkeyPatch, folder: Path, design: Design, *args: str
) -> tuple[int, dict[str, Any], Path]:
    """``design`` written with its project into ``folder`` and routed by ``fenolite route``."""
    for file, text in project_files(design, name="bench", major=10).items():
        path = folder / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    monkeypatch.chdir(folder)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main(["route", "bench.kicad_pcb", "--router", "octilinear", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), folder / "bench.kicad_pcb"


def _segments(tracks: tuple[Track, ...] | list[Track]) -> list[tuple[Point, Point]]:
    return [(track.start, track.end) for track in tracks]


def _octilinear(track: Track) -> bool:
    dx, dy = abs(track.end.x - track.start.x), abs(track.end.y - track.start.y)
    return dx == 0 or dy == 0 or dx == dy


def _no_acute(tracks: list[Track]) -> bool:
    """No two tracks of one net and layer that share an end meet at an acute angle."""
    ends: dict[tuple[str | None, str, Point], list[tuple[int, int]]] = {}
    for track in tracks:
        ends.setdefault((track.net_id, track.layer, track.start), []).append(
            (track.end.x - track.start.x, track.end.y - track.start.y)
        )
        ends.setdefault((track.net_id, track.layer, track.end), []).append(
            (track.start.x - track.end.x, track.start.y - track.end.y)
        )
    for found in ends.values():
        for i, a in enumerate(found):
            for b in found[i + 1 :]:
                if a[0] * b[0] + a[1] * b[1] > 0:
                    return False
    return True


def _checks(path: Path) -> tuple[Design, Any]:
    """The board at ``path`` and the copper check of ``fenolite route`` with its project's rules."""
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    rules = cmd_route._project_rules(design, path, [])  # pyright: ignore[reportPrivateUsage]
    checks = cmd_route._job_checks(rules.design, rules)  # pyright: ignore[reportPrivateUsage]
    return rules.design, checks["copper_check"]


def test_registry_lists_the_router_with_its_features() -> None:
    """Scenario "Listed with its features"."""
    router = routers()["octilinear"]
    assert isinstance(router, OctilinearRouter) and router.available().available
    assert router_features(router) == frozenset({"pairs", "short", "roles"})
    assert router.sends_data_offsite is False


def test_shapes_in_their_order() -> None:
    a, b = _p(0, 0), _p(4, 2)
    assert shapes(a, b) == (
        (a, _p(2, 2), b),
        (a, _p(2, 0), b),
        (a, _p(4, 0), b),
        (a, _p(0, 2), b),
    )
    assert shapes(a, _p(3, 3)) == ((a, _p(3, 3)), (a, _p(3, 0), _p(3, 3)), (a, _p(0, 3), _p(3, 3)))
    assert shapes(a, _p(5, 0)) == ((a, _p(5, 0)),)
    assert all(bends_ok(shape) for shape in shapes(a, b))
    assert not bends_ok((a, _p(4, 0), _p(1, 1)))  # an acute joint
    assert simplify((a, a, _p(1, 0), _p(2, 0), _p(2, 1))) == (a, _p(2, 0), _p(2, 1))
    assert offset((a, _p(4, 0)), 1, 100) == (Point(0, 100), Point(4 * MM, 100))


def test_gate_loop_routed_octilinear(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A gate loop routed octilinear"."""
    code, env, board = route_cli(
        monkeypatch, tmp_path, gate_loop(), "--nets", "GATE", "--nets", "KSRC", "--confirm"
    )
    assert code == 0, env
    assert env["result"]["routed"] == ["GATE", "KSRC"] and env["result"]["unrouted"] == []
    design, check = _checks(board)
    assert design.board is not None
    tracks = list(design.board.tracks)
    assert len(tracks) == 4 and all(_octilinear(track) for track in tracks) and _no_acute(tracks)
    assert any(not (t.start.x == t.end.x or t.start.y == t.end.y) for t in tracks), "no 45 degree segment"
    assert fresh(check(gate_loop()), check(design)) == []


def test_three_pads_two_groups() -> None:
    """Scenario "Three pads, two connections"."""
    design = dots({"A": ((10, 10), (14, 10), (18, 10))})
    assert design.board is not None
    net = design.circuit.nets[0].id
    joined = Track(id="trk_00000000-0000-4000-8000-000000000901", start=_p(10, 10), end=_p(14, 10),
                   width=WIDTH, layer="F.Cu", net_id=net)  # fmt: skip
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=(joined,)))
    result = OctilinearRouter().route(job(design, ("A",)))
    assert _segments(result.tracks) == [(_p(14, 10), _p(18, 10))] and result.routed == ("A",)


def test_a_pad_in_the_way() -> None:
    """Scenario "A pad in the way": the 45-then-straight shape runs through ``B`` and is refused."""
    design = dots({"A": ((5, 5), (15, 7)), "B": ((10, 7),)})
    result = OctilinearRouter().route(job(design, ("A",)))
    assert _segments(result.tracks) == [(_p(5, 5), _p(13, 5)), (_p(13, 5), _p(15, 7))]
    clear = OctilinearRouter().route(job(dots({"A": ((5, 5), (15, 7))}), ("A",)))
    assert _segments(clear.tracks) == [(_p(5, 5), _p(7, 7)), (_p(7, 7), _p(15, 7))]


def test_too_long_stays_open() -> None:
    """Scenario "Too long stays open"."""
    design = dots({"L": ((5, 10), (65, 10))}, width=80)
    result = OctilinearRouter().route(job(design, ("L",)))
    assert result.tracks == () and result.unrouted == ("L",)
    (issue,) = [found for found in result.issues if found.code == "route.unrouted"]
    assert "max-length" in issue.message and "D1-1 to D2-1" in issue.message and issue.where == "L"
    longer = OctilinearRouter().route(job(design, ("L",), **{"max-length": "70mm"}))
    assert longer.routed == ("L",) and MAX_LENGTH == 20 * MM


def test_bad_options_are_reported() -> None:
    design = dots({"A": ((5, 5), (15, 5))})
    result = OctilinearRouter().route(job(design, ("A",), rounds="0", speed="9", **{"max-length": "x"}))
    assert sorted(found.where for found in result.issues if found.code == "route.option-ignored") == [
        "max-length",
        "rounds",
        "speed",
    ]
    assert result.routed == ("A",)


BLOCKED = {"X": ((14.5, 5.0), (11.0, 13.0)), "Y": ((7.0, 13.0), (13.5, 8.0)), "O": ((5.5, 12.5),)}
"""``X`` is routed first (shorter) and its first fitting shape blocks every shape of ``Y``; ``Y`` routed
first leaves ``X`` another shape. ``O`` closes the other ways of ``Y``. Found by a search over dots."""


def test_a_blocked_connection_goes_first() -> None:
    """Scenario "A blocked connection goes first"."""
    design = dots(BLOCKED)
    one = OctilinearRouter().route(job(design, ("X", "Y"), rounds=1))
    assert one.routed == ("X",) and one.unrouted == ("Y",)
    assert [found.where for found in one.issues if found.code == "route.unrouted"] == ["Y"]
    default = OctilinearRouter().route(job(design, ("X", "Y")))
    assert default.routed == ("X", "Y") and default.issues == ()
    again = OctilinearRouter().route(job(design, ("X", "Y")))
    assert again == default


def test_a_sense_pair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A sense pair"."""
    code, env, board = route_cli(monkeypatch, tmp_path, sense(), "--confirm")
    assert code == 0, env
    assert env["result"]["routed"] == ["SNS_N", "SNS_P"]
    (pair,) = env["result"]["pairs"]
    assert pair["routed"] is True and pair["gap"] == 200_000
    design, check = _checks(board)
    assert design.board is not None
    tracks = list(design.board.tracks)
    assert all(_octilinear(track) and track.width == 200_000 for track in tracks) and _no_acute(tracks)
    names = {net.id: net.name for net in design.circuit.nets}
    coupled = {
        names[t.net_id or ""]: t for t in tracks if t.start.y == t.end.y and abs(t.end.x - t.start.x) > MM
    }
    gap = abs(coupled["SNS_N"].start.y - coupled["SNS_P"].start.y) - 200_000
    assert 200_000 <= gap <= 200_002
    assert fresh(check(sense()), check(design)) == []


def test_a_pair_of_three_pads_is_not_routed() -> None:
    design = dots({"S_P": ((5, 5), (15, 5), (15, 9)), "S_N": ((5, 6), (15, 6))})
    base = job(design, ("S_N", "S_P"))
    paired = dataclasses.replace(base, pairs=(JobPair("S_P/S_N", "S_P", "S_N", 200_000, 200_000),))
    result = OctilinearRouter().route(paired)
    assert result.tracks == () and set(result.unrouted) == {"S_N", "S_P"}
    assert [found.code for found in result.issues] == ["route.pair-not-routed"]


def test_a_finding_refused() -> None:
    """Scenario "A finding refused": a copper check that names the job's track of ``GATE``."""
    design = dots({"GATE": ((5, 5), (10, 5)), "KSRC": ((5, 8), (10, 8))})
    gate_id = next(net.id for net in design.circuit.nets if net.name == "GATE")

    def check(checked: Design) -> list[tuple[str, str, tuple[str, ...], int]]:
        assert checked.board is not None
        return [
            ("copper.clearance", track.layer, (track.id,), 1000)
            for track in checked.board.tracks
            if track.net_id == gate_id
        ]

    base = job(design, ("GATE", "KSRC"))
    result = OctilinearRouter().route(dataclasses.replace(base, extra={**base.extra, "copper_check": check}))
    assert result.routed == ("KSRC",) and result.unrouted == ("GATE",)
    (refused,) = [found for found in result.issues if found.code == "route.check-refused"]
    assert refused.where == "GATE" and "copper.clearance" in refused.message


def test_without_board_pads_nothing_is_routed() -> None:
    design = dots({"A": ((5, 5), (15, 5))})
    base = job(design, ("A",))
    result = OctilinearRouter().route(dataclasses.replace(base, extra={}))
    assert result.tracks == () and [found.code for found in result.issues] == ["route.tool-failed"]


class _Recorder:
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


def test_extras_of_the_route_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Extras of the route command"."""
    router = _Recorder()
    monkeypatch.setattr(cmd_route, "_router", lambda _name, _args: router)
    code, env, _ = route_cli(monkeypatch, tmp_path, gate_loop(), "--dry-run")
    assert code == 0, env
    (recorded,) = router.jobs
    assert set(recorded.extra) == {"board_pads", "outline", "clearance", "copper_check"}
    check = recorded.extra["copper_check"]
    assert callable(check) and check(recorded.design) == []
    clearance = recorded.extra["clearance"]
    assert callable(clearance)
    assert (
        clearance(
            RuleSubject("track", "GATE", "Default", layer="F.Cu"),
            RuleSubject("pad", "KSRC", "Default", layer="F.Cu"),
        )
        == CLEARANCE
    )


def test_route_codes() -> None:
    """Scenario "Codes explained" (the codes' part; ``test_explain_cmd`` checks the entries)."""
    assert ISSUE_CODES["route.pair-not-routed"] == ISSUE_CODES["route.check-refused"] == "warning"
