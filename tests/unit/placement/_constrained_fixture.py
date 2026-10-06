# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored geometry, deliberately tiny and not a fabrication requirement."""

from dataclasses import replace

from fenolite.core.coords import Point, Size
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import to_model
from fenolite.model.board import Board, ComponentBody, FootprintInstance, Layer, Outline, Pad
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.rules import Rule, RuleSet, Selector


def copper_checker(design, supplied_frame, constraints, *, rules=None):
    """Test-only adapter for the real copper checker; placement consumes only its neutral report."""
    from fenolite.checks.copper import check_copper
    from fenolite.placement.constrained_legality import (
        CopperInspection,
        PlacementCopperFinding,
        check_geometry,
    )

    basic = check_geometry(design, supplied_frame, constraints, rules=rules)
    pads = supplied_frame.board_pads(design)
    owned = {p.pad_id: p.footprint_id for p in pads}
    copper = check_copper(design, pads=pads)
    findings = []
    for finding in copper.findings:
        owners = [owned.get(item.entity_id, "") if item.kind == "pad" else "" for item in finding.items]
        relation = (
            ("intrinsic" if owners[0] == owners[1] else "inter_component")
            if all(owners)
            else "routed_or_free"
        )
        findings.append(
            PlacementCopperFinding(
                finding.code,
                finding.severity,
                finding.layer,
                finding.at,
                finding.items,
                finding.gap,
                finding.clearance,
                finding.source,
                finding.message,
                relation,
                finding.where,
            )
        )
    hard = (*basic.hard, *(f"copper:{f.code}:{f.where}" for f in findings if f.relation != "intrinsic"))
    return replace(
        basic,
        hard=tuple(sorted(set(hard))),
        missing_inputs=tuple(x for x in basic.missing_inputs if x != "copper:checker-unavailable"),
        copper=CopperInspection(tuple(findings), copper.issues, copper.summary, copper.evidence),
    )


def part(key: str, x: int, y: int, *, side="top", drill=None, locked=False, two_pads=False, body=False):
    pads = (
        Pad(
            id=f"p_{key}",
            number="1",
            shape="rect",
            size=Size(4, 4),
            position=Point(0, 0),
            layers=("F.Cu", "B.Cu") if drill else (("F.Cu",) if side == "top" else ("B.Cu",)),
            drill=drill,
            kind="thru_hole" if drill else "smd",
            net_id="a",
        ),
    )
    if two_pads:
        pads += (replace(pads[0], id=f"q_{key}", number="2", position=Point(5, 0), net_id="b"),)
    bodies = (
        (
            ComponentBody(
                id=f"body_{key}",
                kind="extruded",
                outline=(Point(-2, -2), Point(2, -2), Point(2, 2), Point(-2, 2)),
                height=5,
            ),
        )
        if body
        else ()
    )
    return FootprintInstance(
        id=key,
        component_id=f"c_{key}",
        lib_ref="authored",
        position=Point(x, y),
        side=side,
        pads=pads,
        bodies=bodies,
        locked=locked,
    )


def board(*parts):
    d = to_model(DslDesign("probe"))
    return replace(
        d,
        circuit=Circuit(
            components=tuple(Component(id=f"c_{fp.id}", ref=fp.id) for fp in parts),
            nets=(Net(id="a", name="A"), Net(id="b", name="B")),
        ),
        board=Board(
            id=d.board.id,
            outline=Outline(id="outline", points=(Point(0, 0), Point(40, 0), Point(40, 30), Point(0, 30))),
            layers=(
                Layer(id="front", name="F.Cu", kind="copper", ordinal=0),
                Layer(id="back", name="B.Cu", kind="copper", ordinal=1),
            ),
            footprints=parts,
        ),
        rules=RuleSet(
            id="rules",
            rules=(
                Rule(id="clearance", name="distance", kind="clearance", selector_a=Selector("all"), min=3),
            ),
        ),
    )
