# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``analysis.connectivity`` (change c0108; capability board-analyses, "Open connections of a net").

The cases are those of the bench that the KiCad oracle judges (``tests/kicad/copper/_openbench.py``), read
here without a tool, plus a comparison with a union over every pair of shapes on generated boards."""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path

import pytest
from _openconn import ob, rb

from fenolite.analysis import connectivity as conn
from fenolite.analysis.connectivity import NetConnectivity, connectivity
from fenolite.analysis.copper import net_copper
from fenolite.backends.kicad.frame import board_pads
from fenolite.checks.equivalence.routing import pieces
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.geometry import thick_touch
from fenolite.model.design import Design

MM = 1_000_000
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def nets() -> dict[str, NetConnectivity]:
    report = ob.query(ob.open_bench(10).design)
    assert report.issues == () and report.evidence == conn.EVIDENCE
    return {net.name: net for net in report.nets}


def case(nets: dict[str, NetConnectivity], name: str) -> NetConnectivity:
    return nets[ob.net_name(name)]


def test_stub_and_the_far_pad(nets: dict[str, NetConnectivity]) -> None:
    """Scenario "A stub and the far pad": the pads are 8.4 mm apart and the stub is 3 mm long."""
    net = case(nets, "stub")
    assert net.islands == 2 and len(net.open) == 1
    (found,) = net.open
    ends = {found.a.kind: found.a, found.b.kind: found.b}
    assert set(ends) == {"pad", "track"} and found.length == 5_400_000
    assert ends["pad"].where == "RB2-1" and ends["pad"].layers == ("F.Cu",)
    assert ends["track"].layers == ("F.Cu",)
    assert ends["pad"].position.x - ends["track"].position.x == 5_400_000
    assert net.pads == (("RA2-1",), ("RB2-1",))


@pytest.mark.parametrize("name", ["joined", "crossing", "across", "beside", "tee-0", "tee-100", "tee-200"])
def test_copper_that_touches_joins(nets: dict[str, NetConnectivity], name: str) -> None:
    """Scenario "Copper that touches joins"."""
    net = case(nets, name)
    assert (net.islands, net.fill_islands, net.open) == (1, 0, ())


def test_islands_without_a_pad(nets: dict[str, NetConnectivity]) -> None:
    """Scenario "Islands without a pad": a floating track counts, a fill that touches nothing does not."""
    floating = case(nets, "floating")
    assert floating.islands == 2 and floating.pads[0] == ()
    (found,) = floating.open
    assert {found.a.kind, found.b.kind} == {"pad", "track"}
    between = case(nets, "fill-between")
    assert (between.islands, between.fill_islands) == (2, 1)
    (found,) = between.open
    assert (found.a.kind, found.b.kind, found.length) == ("pad", "pad", 8_400_000)
    lone = case(nets, "lone-via")
    assert lone.islands == 2 and {lone.open[0].a.kind, lone.open[0].b.kind} == {"pad", "via"}
    assert lone.open[0].b.layers == ("F.Cu", "B.Cu")


def test_fills_join_what_they_touch(nets: dict[str, NetConnectivity]) -> None:
    assert (case(nets, "fill-over").islands, case(nets, "fill-over").fill_islands) == (1, 0)
    one = case(nets, "fill-one-pad")
    assert (one.islands, one.fill_islands, len(one.open)) == (2, 0, 1)
    held = case(nets, "fill-track")  # a fill island that holds a track counts
    assert (held.islands, held.fill_islands, len(held.open)) == (2, 0, 1)


def test_a_missing_via(nets: dict[str, NetConnectivity]) -> None:
    """Scenario "A missing via": the two tracks meet at one point on two layers."""
    assert case(nets, "two-vias").open == ()
    (found,) = case(nets, "one-via").open
    assert (found.a.kind, found.b.kind, found.length) == ("track", "track", 0)
    assert found.a.position == found.b.position
    assert {found.a.layers, found.b.layers} == {("F.Cu",), ("B.Cu",)}


def test_three_pads_and_an_arc(nets: dict[str, NetConnectivity]) -> None:
    three = case(nets, "three-pads")
    assert three.islands == 2 and len(three.open) == 1 and len(three.pads[0]) + len(three.pads[1]) == 3
    assert case(nets, "arc").open == ()
    assert len(case(nets, "none").open) == 1


def test_order_does_not_matter() -> None:
    """Scenario "Order does not matter"."""
    design = ob.open_bench(10).design
    assert ob.query(ob.reversed_design(design)) == ob.query(design)


def test_only_the_named_nets() -> None:
    design = ob.open_bench(10).design
    pads = board_pads(design)
    wanted = (ob.net_name("stub"), ob.net_name("joined"), "no such net")
    report = connectivity(design, pads=pads, nets=wanted)
    assert [net.name for net in report.nets] == sorted(wanted[:2])
    assert report.open_nets() == (ob.net_name("stub"),) and report.total == 1
    assert report.net(ob.net_name("stub")) == ob.query(design).net(ob.net_name("stub"))
    assert report.net("no such net") is None


def test_a_pin_on_no_net() -> None:
    """Scenario "A pin on no net": the net KiCad gives a pin on no net has one pad and nothing open."""
    builder = rb.Builder()
    name = "unconnected-(R1-Pad1)"
    builder.part("r1", "R1", Point(10 * MM, 10 * MM), target=10, nets={"1": name})
    design = builder.build().design
    report = connectivity(design, pads=board_pads(design))
    (net,) = report.nets
    assert (net.name, net.islands, net.open, net.pads) == (name, 1, (), (("R1-1",),))
    assert report.open_nets() == ()


def test_unsupported_pads_lower_the_level() -> None:
    """Scenario "Unsupported pads lower the level"."""
    design = ob.open_bench(10).design
    report = connectivity(design, pads=None)
    (issue,) = report.issues
    assert issue.code == "analysis.item-unsupported" and issue.where == "pad" and issue.severity == "warning"
    assert report.evidence.level is Level.UNVERIFIED
    assert report.evidence.hypotheses == ("H-K-CONN-PARITY",)
    stub = report.net(ob.net_name("stub"))
    assert stub is not None and stub.unsupported == 2 and stub.islands == 1  # the track alone


def test_evidence_names_the_parity_row() -> None:
    assert conn.EVIDENCE.hypotheses == ("H-K-CONN-PARITY",)
    row = next(
        line
        for line in (ROOT / "docs" / "hypotheses.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| H-K-CONN-PARITY |")
    )
    assert row.split("|")[4].strip().startswith(conn.EVIDENCE.level.value)


# --- against a union over every pair ----------------------------------------------------------------


def brute_islands(design: Design) -> dict[str, int]:
    """Net → counted islands, by a union over every pair of shapes of the net (a test-only reference)."""
    copper = net_copper(design, pads=board_pads(design))
    found: dict[str, int] = {}
    for name, shapes in copper.by_net.items():
        items: dict[object, list[tuple[str, object, str]]] = {}
        for index, shape in enumerate(shapes):
            key = ("fill", index) if shape.kind == "fill" else (shape.kind, shape.entity_id, shape.where)
            items.setdefault(key, []).append((shape.layer, shape.shape, shape.kind))
        keys = list(items)
        parent = list(range(len(keys)))

        def find(index: int, parent: list[int] = parent) -> int:
            while parent[index] != index:
                index = parent[index]
            return index

        for i, one in enumerate(keys):
            for j in range(i + 1, len(keys)):
                touching = any(
                    la == lb and thick_touch(a, b)  # type: ignore[arg-type]
                    for la, a, _ in items[one]
                    for lb, b, _ in items[keys[j]]
                )
                if touching:
                    parent[find(i)] = find(j)
        groups: dict[int, set[str]] = {}
        for index, key in enumerate(keys):
            groups.setdefault(find(index), set()).update(kind for _, _, kind in items[key])
        found[name] = sum(1 for kinds in groups.values() if kinds - {"fill"})
    return found


def generated(seed: int) -> Design:
    """A board of four nets, each with two pads and random tracks, vias and fills on a 1 mm grid."""
    rng = random.Random(seed)
    builder = rb.Builder()
    for index in range(4):
        net = f"G{index}"
        y = builder.row()
        builder.part(f"a{index}", f"RA{index}", Point(rb.LEFT, y), target=10, nets={"1": net})
        builder.part(f"b{index}", f"RB{index}", Point(rb.RIGHT, y), target=10, nets={"1": net})
        for n in range(rng.randrange(0, 7)):
            x0 = rb.LEFT - MM + rng.randrange(0, 12) * MM - 800_000 * rng.randrange(0, 2)
            dy = rng.randrange(-2, 3) * MM
            layer = rng.choice(("F.Cu", "B.Cu"))
            builder.track(f"t{index}-{n}", net, y + dy, layer=layer, x0=x0, x1=x0 + rng.randrange(1, 6) * MM)
            if rng.random() < 0.4:
                turned = builder.tracks[-1]
                end = Point(turned.start.x, turned.start.y + rng.randrange(1, 4) * MM)
                builder.tracks[-1] = dataclasses.replace(turned, end=end)
        for n in range(rng.randrange(0, 3)):
            at = Point(rb.LEFT + rng.randrange(0, 11) * MM, y + rng.randrange(-2, 3) * MM)
            builder.via(f"v{index}-{n}", net, at)
        if rng.random() < 0.5:
            x0 = rb.LEFT + rng.randrange(0, 6) * MM
            builder.filled_zone(f"z{index}", net, y + rng.randrange(-3, 1) * MM, x0=x0, x1=x0 + 4 * MM)
    return builder.build().design


@pytest.mark.parametrize("seed", range(108, 132))
def test_brute_force_on_generated_boards(seed: int) -> None:
    """Scenario "Matches brute force"."""
    design = generated(seed)
    report = ob.query(design)
    expected = brute_islands(design)
    assert {net.name: net.islands for net in report.nets} == {n: c for n, c in expected.items() if c}
    for net in report.nets:
        assert len(net.open) == net.islands - 1
        assert len(net.pads) == net.islands
    assert ob.query(ob.reversed_design(design)) == report


def test_the_bench_matches_brute_force() -> None:
    design = ob.open_bench(10).design
    assert {net.name: net.islands for net in ob.query(design).nets} == brute_islands(design)


# --- against the equivalence check ------------------------------------------------------------------


def test_islands_agree_with_the_equivalence_check() -> None:
    """Scenario "Islands agree with the equivalence check": on the bench without fills, with square and
    round pads (the pad copper of the frame is the shape of the model), the islands hold the pads of the
    pieces of ``checks.equivalence.routing.pieces``."""
    design = ob.open_bench(10, fills=False, footprint=ob.DISC_FOOTPRINT).design
    report = ob.query(design)
    assert report.issues == ()
    found = pieces(design)
    assert found.unshaped == 0
    ids = {net.name: net.id for net in design.circuit.nets}
    assert len(report.nets) == len(ob.EXPECTED)
    for net in report.nets:
        held = found[ids[net.name]]
        assert len(held) == net.islands, net.name
        assert sorted(piece.pads for piece in held) == sorted(net.pads), net.name
