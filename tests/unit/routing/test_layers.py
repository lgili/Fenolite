# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Routing layers and the layers a net may use (capability routing, "Plane and routing layers in a routing
job"; change c0107)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from fenolite.core.ids import derived_id
from fenolite.model.circuit import Circuit, Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector
from fenolite.routing import layers as routing_layers_module
from fenolite.routing.layers import allowed_layers, class_name, routing_layers
from fenolite.routing.protocol import JobNet, RoutingJob

SIX = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")
FOUR = ("F.Cu", "In2.Cu", "In3.Cu", "B.Cu")


def design(*rules: Rule) -> tuple[Design, Net, Net, Net]:
    hv = NetClass(id=derived_id("cls", "test", "HV"), name="HV")
    sig = NetClass(id=derived_id("cls", "test", "SIG"), name="SIG")
    a = Net(id=derived_id("net", "test", "HV1"), name="HV1", netclass_id=hv.id)
    b = Net(id=derived_id("net", "test", "SIG1"), name="SIG1", netclass_id=sig.id)
    c = Net(id=derived_id("net", "test", "FREE"), name="FREE")
    base = Design.new("layers", seed=0)
    made = dataclasses.replace(
        base,
        circuit=Circuit(nets=(a, b, c), netclasses=(hv, sig)),
        rules=RuleSet(id=derived_id("rst", "test", "layers"), rules=rules) if rules else None,
    )
    return made, a, b, c


def rule(selector: Selector, layers: tuple[str, ...], **more: object) -> Rule:
    return Rule(
        id=derived_id("rul", "test", f"{selector}{layers}"),
        name="hv-outer",
        kind="no_tracks",
        selector_a=selector,
        layers=layers,
        **more,  # type: ignore[arg-type]
    )


def test_allowed_layers_from_track_layer_rules() -> None:
    """Scenario "Allowed layers from track layer rules"."""
    made, hv, sig, free = design(rule(Selector("netclass", "HV"), ("In2.Cu", "In3.Cu")))
    routing = routing_layers(SIX, ("In1.Cu", "In4.Cu"))
    assert routing == FOUR
    assert allowed_layers(made, hv, routing) == ("F.Cu", "B.Cu")
    assert allowed_layers(made, sig, routing) == FOUR and allowed_layers(made, free, routing) == FOUR
    assert class_name(made, hv) == "HV" and class_name(made, free) == "Default"


def test_ignored_rule() -> None:
    """Scenario "Ignored rule"."""
    made, hv, _sig, _free = design(rule(Selector("netclass", "HV"), ("In2.Cu", "In3.Cu"), severity="ignore"))
    assert allowed_layers(made, hv, FOUR) == FOUR
    warned, hv, _sig, _free = design(rule(Selector("netclass", "HV"), ("In2.Cu",), severity="warning"))
    assert allowed_layers(warned, hv, FOUR) == ("F.Cu", "In3.Cu", "B.Cu")


def test_selectors_and_other_kinds() -> None:
    by_net = rule(Selector("net", "FREE"), ("F.Cu", "B.Cu"))
    default = dataclasses.replace(rule(Selector("netclass", "Default"), ("In2.Cu",)), name="default")
    everything = dataclasses.replace(rule(Selector("all"), ("In3.Cu",)), name="all")
    width = Rule(
        id=derived_id("rul", "test", "w"), name="w", kind="track_width", selector_a=Selector("all"),
        layers=("F.Cu",), min=100_000,
    )  # fmt: skip
    made, hv, _sig, free = design(by_net, default, everything, width)
    assert allowed_layers(made, free, FOUR) == ()
    assert allowed_layers(made, hv, FOUR) == ("F.Cu", "In2.Cu", "B.Cu")
    plain, hv, _sig, _free = design()
    assert plain.rules is None and allowed_layers(plain, hv, FOUR) == FOUR


def test_job_fields_default_to_the_old_meaning() -> None:
    net = JobNet("A", "net_a", (), 250_000, 200_000, 600_000, 300_000)
    job = RoutingJob(Design.new("job", seed=1), (net,), ("F.Cu", "B.Cu"))
    assert net.layers is None and job.plane_layers == ()
    # the fields of change c0109 (tier, budget) follow those of c0107, and those of c0120 come last
    assert [f.name for f in dataclasses.fields(JobNet)][-3:] == ["via_drill", "layers", "tier"]
    assert [f.name for f in dataclasses.fields(RoutingJob)][-5:] == [
        "extra",
        "plane_layers",
        "budget",
        "on_run",
        "progress",
    ]


def test_module_imports_only_core_and_model() -> None:
    tree = ast.parse(Path(routing_layers_module.__file__).read_text(encoding="utf-8"))
    names = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert all(
        name.startswith(("fenolite.core", "fenolite.model")) or not name.startswith("fenolite")
        for name in names
    ), names
