# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Meanders from intents (capability manual-copper, "Meanders from intents"; hypothesis
H-K-NETLEN-MEANDER; change c0106). Hermetic: authored tracks of round lengths on a created board."""

from __future__ import annotations

import ast
import dataclasses
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

from _placed import design_of

from fenolite.backends.kicad import lengths, meander
from fenolite.backends.kicad.copper import copper_uuid, resolve_copper
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.meander import LENGTH_TOLERANCE_NM, MEANDER_ISSUE_CODES, resolve_meanders
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level
from fenolite.dsl import ArcStep, MeanderIntent, TrackIntent, ViaStep
from fenolite.geometry import orient2d, segment_length
from fenolite.model.board import Track
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
MM = 1_000_000
WIDTH = 200_000


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def tracked(*intents: TrackIntent, copper: int = 2) -> Design:
    """A created board with the net ``N`` and the copper of ``intents``."""
    base = design_of(copper=copper, extra_nets=("N", "P"))
    issues: list[Issue] = []
    design = resolve_copper(base, intents, issues=issues)
    assert not issues, issues
    return design


def run(key: str, *points: Any, net: str = "N", layer: str = "F.Cu") -> TrackIntent:
    return TrackIntent(key, tuple(points), layer, WIDTH, net)


def wave(key: str = "m", track: str = "t", **more: Any) -> MeanderIntent:
    values: dict[str, Any] = {"segment": 0, "amplitude": MM, "pitch": MM, "target": 23 * MM, **more}
    if "match" in more:
        values["target"] = more.get("target")
    return MeanderIntent(key, track, **values)


def resolve(design: Design, *meanders: Any, major: int = 10) -> tuple[Design, list[Issue]]:
    issues: list[Issue] = []
    return resolve_meanders(design, meanders, major=major, issues=issues), issues


def tracks(design: Design) -> list[Track]:
    assert design.board is not None
    return list(design.board.tracks)


def net_total(design: Design, net: str = "N", major: int = 10) -> int:
    assert design.board is not None
    depths, _ = lengths.layer_depths(design.board, major=major)
    return lengths.net_lengths(design, pads=board_pads(design), depths=depths, major=major)[net].total


AXIS = run("t", mm(0, 0), mm(20, 0))


def test_axis_run() -> None:
    design = tracked(AXIS)
    result, issues = resolve(design, wave())
    assert not issues
    found = tracks(result)
    points = [found[0].start, *(t.end for t in found)]
    assert points == [
        mm(0, 0), mm(1, 0), mm(1, -0.75), mm(2, -0.75), mm(2, 0), mm(3, 0), mm(3, -0.75), mm(4, -0.75),
        mm(4, 0), mm(20, 0),
    ]  # fmt: skip
    assert [t.native_ids["kicad"] for t in found] == [copper_uuid("m", f"m[{k}]") for k in range(9)]
    assert copper_uuid("t", "seg[0]") not in {t.native_ids["kicad"] for t in found}
    assert sum(segment_length(t.start, t.end) for t in found) == 23 * MM == net_total(result)
    old = tracks(design)[0]
    assert {(t.width, t.layer, t.net_id, t.locked) for t in found} == {
        (old.width, old.layer, old.net_id, old.locked)
    }
    assert all(a.end == b.start for a, b in zip(found, found[1:], strict=False))
    assert meander.changed(result, [wave()]) == 1 and meander.changed(design, [wave()]) == 0
    assert design == tracked(AXIS)  # the input is not changed


def test_axis_right_side_and_margin() -> None:
    result, issues = resolve(tracked(AXIS), wave(side="right", margin=5 * MM, target=22 * MM))
    assert not issues
    found = tracks(result)
    assert [found[0].start, *(t.end for t in found)] == [
        mm(0, 0), mm(5, 0), mm(5, 1), mm(6, 1), mm(6, 0), mm(20, 0),
    ]  # fmt: skip


def test_the_new_tracks_take_the_place_of_the_segment() -> None:
    design = tracked(
        run("t", mm(0, 0), mm(5, 0), mm(25, 0), mm(25, 9)), run("z", mm(0, 30), mm(9, 30), net="P")
    )
    result, issues = resolve(design, wave(segment=1, target=38 * MM))
    assert not issues
    natives = [t.native_ids["kicad"] for t in tracks(result)]
    assert natives[0] == copper_uuid("t", "seg[0]") and natives[-2] == copper_uuid("t", "seg[2]")
    assert natives[1:-2] == [copper_uuid("m", f"m[{k}]") for k in range(len(natives) - 3)]
    assert natives[-1] == copper_uuid("z", "seg[0]")
    assert net_total(result) == 38 * MM and net_total(result, "P") == 9 * MM


def test_run_at_30_degrees() -> None:
    design = tracked(run("t", mm(0, 0), Point(17_320_508, 10_000_000)))
    result, issues = resolve(design, wave())
    assert not issues
    found = tracks(result)
    assert abs(net_total(result) - 23 * MM) <= LENGTH_TOLERANCE_NM
    start, end = found[0].start, found[-1].end
    for t in found:
        for point in (t.start, t.end):
            off = segment_length(point, _foot(start, end, point))
            assert off <= MM + LENGTH_TOLERANCE_NM
            assert off <= 1 or orient2d(start, end, point) < 0  # on the left


def _foot(a: Point, b: Point, p: Point) -> Point:
    dx, dy = b.x - a.x, b.y - a.y
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy)
    return Point(round(a.x + t * dx), round(a.y + t * dy))


def test_matching_another_intent() -> None:
    design = tracked(run("p", mm(0, 0), mm(20, 0), net="P"), run("n", mm(0, 5), mm(18.8, 5)))
    result, issues = resolve(design, wave("n_tune", "n", match="p", amplitude=MM // 2, pitch=MM))
    assert not issues
    assert abs(net_total(result, "N") - net_total(result, "P")) <= LENGTH_TOLERANCE_NM
    assert net_total(result, "P") == 20 * MM
    assert [t for t in tracks(result) if t.native_ids["kicad"] == copper_uuid("p", "seg[0]")] == [
        t for t in tracks(design) if t.native_ids["kicad"] == copper_uuid("p", "seg[0]")
    ]


def test_match_follows_the_matched_meander_and_cycles_are_refused() -> None:
    design = tracked(run("p", mm(0, 0), mm(20, 0), net="P"), run("n", mm(0, 5), mm(20, 5)))
    # "a" sorts first but waits for the meander of the track it matches
    first = wave("a", "n", match="p")
    second = wave("b", "p", target=24 * MM)
    result, issues = resolve(design, first, second)
    assert not issues
    assert net_total(result, "P") == 24 * MM == net_total(result, "N")
    cyclic, issues = resolve(design, wave("a", "n", match="p"), wave("b", "p", match="n"))
    assert cyclic == design
    assert [(i.code, i.where) for i in issues] == [
        ("kicad.meander.bad-match", "a"),
        ("kicad.meander.bad-match", "b"),
    ]
    missing, issues = resolve(design, wave("a", "n", match="nope"))
    assert missing == design and [i.code for i in issues] == ["kicad.meander.bad-match"]


def test_refusals_change_nothing() -> None:
    design = tracked(AXIS)
    for intent, code, words in (
        (wave(target=60 * MM), "kicad.meander.no-room", ("40 mm needed", "at most 18 mm")),
        (wave(target=15 * MM), "kicad.meander.too-long", ("20 mm", "15 mm")),
        (wave(pitch=WIDTH), "kicad.meander.bad-shape", ("0.2 mm",)),
        (wave(target=20 * MM), "kicad.meander.not-needed", ("20 mm",)),
        (wave(segment=3), "kicad.meander.no-segment", ("segment 3",)),
        (wave(track="nope"), "kicad.meander.no-segment", ("nope",)),
        (wave(side="up"), "kicad.meander.bad-intent", ("side",)),
        (wave(amplitude=0), "kicad.meander.bad-intent", ("amplitude",)),
        (wave(margin=-1), "kicad.meander.bad-intent", ("margin",)),
        (wave(target=None), "kicad.meander.bad-intent", ("target",)),
    ):
        result, issues = resolve(design, intent)
        assert result == design, code
        (issue,) = issues
        assert issue.code == code and issue.severity == MEANDER_ISSUE_CODES[code], issue
        assert all(word in issue.message for word in words), issue.message
        assert issue.where == "m"


def test_an_arc_segment_is_a_bad_intent() -> None:
    design = tracked(run("t", mm(0, 0), ArcStep(mm(3, 3), mm(6, 0)), mm(30, 0)))
    result, issues = resolve(design, wave(segment=0))
    assert result == design and [i.code for i in issues] == ["kicad.meander.bad-intent"]
    assert "arc" in issues[0].message


def test_a_refused_meander_leaves_the_others() -> None:
    design = tracked(AXIS, run("u", mm(0, 9), mm(20, 9), net="P"))
    result, issues = resolve(design, wave("bad", "t", target=90 * MM), wave("good", "u", target=22 * MM))
    assert [i.code for i in issues] == ["kicad.meander.no-room"]
    assert net_total(result, "N") == 20 * MM and net_total(result, "P") == 22 * MM
    again, issues = resolve(design, wave("m"), wave("m", segment=0, target=25 * MM))
    assert [i.code for i in issues] == ["kicad.meander.bad-intent"] and net_total(again) == 23 * MM


def test_via_steps_count_as_the_major_counts_them() -> None:
    """A track that changes layer: its length holds the via height of the major, so a target is met as
    KiCad of that major counts the net."""
    step = ViaStep(mm(10, 0), "B.Cu", 600_000, 300_000)
    design = tracked(run("t", mm(0, 0), step, mm(30, 0)))
    for major, height in ((10, 1_580_000), (9, 1_545_000)):
        assert net_total(design, major=major) == 30 * MM + height
        result, issues = resolve(design, wave(segment=1, target=35 * MM), major=major)
        assert not issues
        assert net_total(result, major=major) == 35 * MM
        assert {t.layer for t in tracks(result) if "m[" not in t.id} >= {"B.Cu"}


def test_two_meanders_on_one_track() -> None:
    design = tracked(run("t", mm(0, 0), mm(20, 0), mm(20, 20)))
    result, issues = resolve(design, wave("a", target=43 * MM), wave("b", segment=1, target=46 * MM))
    assert not issues and net_total(result) == 46 * MM


def test_generated_runs() -> None:
    """The intent's length is within 10 nm of the target, or the meander is refused with a code of the
    table and the design is unchanged."""
    rng = random.Random(106)
    met = refused = 0
    for _ in range(300):
        start = Point(rng.randint(0, 50) * MM, rng.randint(0, 50) * MM)
        end = Point(
            start.x + rng.randint(-30_000_000, 30_000_000), start.y + rng.randint(-30_000_000, 30_000_000)
        )
        if start == end:
            continue
        design = tracked(run("t", start, end))
        length = segment_length(start, end)
        intent = wave(
            target=length + rng.randint(-2 * MM, 12 * MM),
            amplitude=rng.randint(300_000, 3 * MM),
            pitch=rng.randint(150_000, 2 * MM),
            side=rng.choice(("left", "right")),
            margin=rng.choice((None, 0, rng.randint(0, 2 * MM))),
        )
        result, issues = resolve(design, intent)
        if issues:
            assert result == design and issues[0].code in MEANDER_ISSUE_CODES
            refused += 1
            continue
        assert abs(net_total(result) - intent.target) <= LENGTH_TOLERANCE_NM  # type: ignore[operator]
        way = -1 if intent.side == "left" else 1
        for t in tracks(result):
            for point in (t.start, t.end):
                off = segment_length(point, _foot(start, end, point))
                assert off <= intent.amplitude + LENGTH_TOLERANCE_NM
                assert off <= 2 or orient2d(start, end, point) * way > 0
        met += 1
    assert met > 60 and refused > 60, (met, refused)


def test_same_result_in_every_process() -> None:
    folders = [str(ROOT / "tests"), str(Path(__file__).parent)]
    script = (
        f"import sys; sys.path[:0] = {folders!r}\n"
        "import test_meander as t\n"
        "d, i = t.resolve(t.tracked(t.run('t', t.mm(0, 0), t.Point(17_320_508, 10_000_000))), t.wave(),"
        " t.wave('bad', 'nope'))\n"
        "print([(x.native_ids['kicad'], x.start, x.end) for x in t.tracks(d)])\n"
        "print([(x.code, x.message) for x in i])\n"
    )
    outputs: set[str] = set()
    for seed in ("0", "1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env, check=True
        )
        outputs.add(done.stdout)
    assert len(outputs) == 1 and "kicad.meander.no-segment" in next(iter(outputs))


def test_codes_evidence_and_imports() -> None:
    assert dict(MEANDER_ISSUE_CODES) == {
        "kicad.meander.bad-intent": "error",
        "kicad.meander.bad-shape": "error",
        "kicad.meander.too-long": "error",
        "kicad.meander.no-room": "error",
        "kicad.meander.bad-match": "error",
        "kicad.meander.inexact": "error",
        "kicad.meander.no-segment": "warning",
        "kicad.meander.not-needed": "info",
    }
    assert meander.EVIDENCE.level is Level.INFERRED and meander.EVIDENCE.hypotheses == ("H-K-NETLEN-MEANDER",)
    assert LENGTH_TOLERANCE_NM == 10
    tree = ast.parse(Path(meander.__file__).read_text(encoding="utf-8"))
    allowed = (
        "fenolite.core",
        "fenolite.model",
        "fenolite.geometry",
        "fenolite.backends.base",
        "fenolite.backends.kicad",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("fenolite"):
            assert node.module.startswith(allowed), node.module
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree))
    assert dataclasses.is_dataclass(MeanderIntent)
