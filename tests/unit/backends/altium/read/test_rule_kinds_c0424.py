# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule kinds of change c0424 onto the neutral model (capability altium-project-reader, "Rule kinds of change
c0424 onto the neutral model"). Every record is authored here with the keys of the public rule file S-0297
and the public PCB documents (S-1838); the values are Fenolite's own."""

from __future__ import annotations

from fenolite.backends.altium.read.rules import (
    HEADER_KEYS,
    CopperLayer,
    CopperLayers,
    Field,
    map_rules,
)
from fenolite.model.rules import Selector

FOUR = CopperLayers(
    (
        CopperLayer("Top Layer", "F.Cu", False, 1),
        CopperLayer("Inner 1", "In1.Cu", True, 2),
        CopperLayer("Inner 2", "In2.Cu", True, 3),
        CopperLayer("Plane 1", "In3.Cu", False, 39),
        CopperLayer("Bottom Layer", "B.Cu", False, 32),
    )
)


def record(
    kind: str, *keys: Field, scope: str = "All", enabled: str = "TRUE", priority: int = 1
) -> list[Field]:
    """An authored rule record of ``kind`` with the header keys and ``keys``."""
    values = {
        "RULEKIND": kind, "NETSCOPE": "AnyNet", "LAYERKIND": "SameLayer", "SCOPE1EXPRESSION": scope,
        "SCOPE2EXPRESSION": "All", "NAME": f"{kind}_{priority}", "ENABLED": enabled,
        "PRIORITY": str(priority), "COMMENT": "", "UNIQUEID": f"C0424{priority:03d}",
        "DEFINEDBYLOGICALDOCUMENT": "FALSE",
    }  # fmt: skip
    return [*((key, values[key]) for key in HEADER_KEYS), *keys]


SILK = record("SilkToSilkClearance", ("SILKTOSILKCLEARANCE", "4mil"))
COMPONENT = record(
    "ComponentClearance",
    ("GAP", "8mil"), ("COLLISIONCHECKMODE", "3"), ("VERTICALGAP", "8mil"), ("SHOWDISTANCES", "FALSE"),
)  # fmt: skip
PAIRS = record(
    "DiffPairsRouting",
    ("MAXLIMIT", "9mil"), ("MINLIMIT", "5mil"), ("MOSTFREQGAP", "7mil"), ("MAXUNCOUPLEDLENGTH", "200mil"),
    ("TOPLAYER_MINWIDTH", "5mil"), ("TOPLAYER_MAXWIDTH", "9mil"), ("TOPLAYER_PREFWIDTH", "7mil"),
)  # fmt: skip
LAYERS = record(
    "RoutingLayers",
    ("TOP LAYER_V5", "TRUE"), ("MID LAYER 1_V5", "FALSE"), ("MID LAYER 2_V5", "TRUE"),
    ("MID LAYER 9_V5", "FALSE"), ("BOTTOM LAYER_V5", "TRUE"),
)  # fmt: skip
HOLES = record("HoleToHoleClearance", ("GAP", "10mil"), ("ALLOWSTACKEDMICROVIAS", "TRUE"))


def test_one_record_of_each_new_kind() -> None:
    mapping = map_rules([SILK, COMPONENT, PAIRS, LAYERS, HOLES], origin="board.PcbDoc", layers=FOUR)
    assert mapping.unmapped == ()
    by_kind = {rule.kind: rule for rule in mapping.ruleset.rules}
    assert sorted(by_kind) == [
        "courtyard_clearance", "diff_pair_gap", "diff_pair_uncoupled", "hole_to_hole", "no_tracks",
        "silk_clearance",
    ]  # fmt: skip
    assert by_kind["silk_clearance"].min == 101_600
    assert by_kind["courtyard_clearance"].min == 203_200
    gap = by_kind["diff_pair_gap"]
    assert (gap.min, gap.opt, gap.max) == (127_000, 177_800, 228_600)
    assert gap.selector_a == Selector("diff_pair", "*")
    assert by_kind["diff_pair_uncoupled"].max == 5_080_000
    # MID LAYER 9 is no layer of the board: it applies to no object; the plane has no key
    assert by_kind["no_tracks"].layers == ("In1.Cu",)
    assert by_kind["hole_to_hole"].min == 254_000


def test_pair_scope_joins_the_record_scope() -> None:
    scoped = record("DiffPairsRouting", ("MINLIMIT", "5mil"), scope="InNetClass('USB')")
    (rule,) = map_rules([scoped], origin="board.PcbDoc").ruleset.rules
    assert rule.selector_a == Selector("and", items=(Selector("diff_pair", "*"), Selector("netclass", "USB")))


def test_routing_layers_without_a_closed_layer_or_without_layers() -> None:
    open_all = record("RoutingLayers", ("TOP LAYER_V5", "TRUE"), ("BOTTOM LAYER_V5", "TRUE"))
    mapping = map_rules([open_all], origin="board.PcbDoc", layers=FOUR)
    assert mapping.unmapped == () and mapping.ruleset.rules == ()
    (refused,) = map_rules([LAYERS], origin="board.RUL").unmapped
    assert refused.reason == "no-layer"


def test_a_net_scope_of_either_value_and_an_unknown_key() -> None:
    different = [(key, "DifferentNets" if key == "NETSCOPE" else value) for key, value in SILK]
    assert map_rules([different], origin="board.PcbDoc").unmapped == ()
    (refused,) = map_rules([[*PAIRS, ("TOPLAYER_SKEW", "1mil")]], origin="board.PcbDoc").unmapped
    assert refused.reason == "keys"
