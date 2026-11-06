# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule records the Altium writer cannot rebuild are kept and written back (capability altium-import, "Rule
records the writer cannot rebuild are kept"; capability altium-pcb-writer, "Kept rule records written back";
change c0424). The records are authored in Fenolite's own sample (``_altium_rules_doc``)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from _altium_rules_doc import KIND_NUMBERS, ONE_OF_EACH, rule
from _altium_rules_doc import project as rules_project

from fenolite.backends.altium.adapter.layers import copper_layers_of
from fenolite.backends.altium.adapter.rules import KEPT_RECORD, KEPT_RULE, kept_fields
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.lower import write_design
from fenolite.backends.altium.read.pcb import RuleRecord, read_pcbdoc
from fenolite.backends.altium.read.rules import map_rules
from fenolite.model.canonical import dumps
from fenolite.model.design import Design

RECORDS = (
    rule("Clearance", ("GAP", "8mil"), ("GENERICCLEARANCE", "8mil"), net_scope="DifferentNets"),
    rule("Width", ("MINLIMIT", "6mil"), ("PREFEREDWIDTH", "8mil"), ("MAXLIMIT", "20mil"), enabled=False),
    rule("RoutingTopology", ("TOPOLOGY", "Starburst")),
    rule("HoleToHoleClearance", ("GAP", "10mil"), ("ALLOWSTACKEDMICROVIAS", "TRUE")),
)


def _design(tmp_path: Path) -> Design:
    return AltiumBackend().read(rules_project(tmp_path / "src", RECORDS)).design


def _kept(design: Design) -> list[tuple[int, dict[str, str]]]:
    assert design.board is not None
    payload = design.board.ext["altium"].payload
    return [
        (number, dict(fields))
        for number, fields in (kept_fields(text) for key, text in payload if key == KEPT_RULE)
    ]


def test_a_disabled_rule_and_a_routing_topology_are_kept(tmp_path: Path) -> None:
    design = _design(tmp_path)
    assert design.rules is not None
    kinds = sorted(str(rule.kind) for rule in design.rules.rules)
    assert kinds == ["clearance", "hole_to_hole"]
    kept = _kept(design)
    assert [(number, fields["RULEKIND"]) for number, fields in kept] == [
        (2, "Width"), (7, "RoutingTopology"), (52, "HoleToHoleClearance"),
    ]  # fmt: skip
    assert kept[0][1]["ENABLED"] == "FALSE" and kept[1][1]["TOPOLOGY"] == "Starburst"
    (stacked,) = [rule for rule in design.rules.rules if rule.kind == "hole_to_hole"]
    assert ("kept_record", "1") in stacked.ext["altium"].payload


def test_kept_records_are_written_back(tmp_path: Path) -> None:
    written = write_design(_design(tmp_path))
    document = next(data for name, data in written.files.items() if name.endswith(".PcbDoc"))
    rules = read_pcbdoc(document, file="board6.PcbDoc").rules
    by_kind = {r.rule_kind: dict(r.record.fields) for r in rules}
    assert by_kind["RoutingTopology"]["TOPOLOGY"] == "Starburst"
    assert by_kind["HoleToHoleClearance"]["ALLOWSTACKEDMICROVIAS"] == "TRUE"
    widths = [dict(r.record.fields) for r in rules if r.rule_kind == "Width"]
    disabled = [fields for fields in widths if fields["ENABLED"] == "FALSE"]
    assert len(disabled) == 1 and disabled[0]["MINLIMIT"] == "6mil"
    # the disabled width follows the width rules the writer makes, with the next priority
    assert int(disabled[0]["PRIORITY"]) == len(widths)
    assert sum(1 for r in rules if r.rule_kind == "HoleToHoleClearance") == 1
    assert not any(i.code == "altium.not-lowered" and "hole" in i.message.lower() for i in written.issues)


def _tail(record: RuleRecord) -> tuple[tuple[str, str | None], ...]:
    fields = list(record.record.fields)
    start = [key for key, _ in fields].index("RULEKIND")
    return tuple(fields[start:])


def _named(records: Sequence[RuleRecord]) -> dict[tuple[str, str], RuleRecord]:
    return {(r.rule_kind, str(r.record.get("NAME"))): r for r in records}


def test_round_trip_gives_an_equal_rule_record_set(tmp_path: Path) -> None:
    """Altium → model → Altium on one record of each kind: every record the import keeps comes back as Altium
    wrote it, from ``RULEKIND`` on, with its kind number; every record that maps comes back with the same
    neutral rules (the writer names them by its own scheme, ``<Kind>``)."""
    source = rules_project(tmp_path / "src", ONE_OF_EACH)
    before = read_pcbdoc((source.parent / "board6.PcbDoc").read_bytes(), file="board6.PcbDoc").rules
    design = AltiumBackend().read(source).design
    written = write_design(design)
    document = next(data for name, data in written.files.items() if name.endswith(".PcbDoc"))
    after = read_pcbdoc(document, file="board6.PcbDoc").rules
    old, new = _named(before), _named(after)
    kept = {(int(number), fields["RULEKIND"], fields["NAME"]) for number, fields in _kept(design)}
    kept |= {(KIND_NUMBERS["PolygonConnect"], "PolygonConnect", "PolygonConnect_1")}
    assert len(kept) > 25
    for number, kind, name in kept:
        assert _tail(new[kind, name]) == _tail(old[kind, name]), (kind, name)
        assert new[kind, name].kind_number == old[kind, name].kind_number == number
    assert set(new) - set(old) == {(kind, kind) for kind, name in set(old) - set(new)}
    assert design.board is not None
    layers = copper_layers_of(design.board.layers)

    def neutral(records: Sequence[RuleRecord]) -> list[tuple[object, ...]]:
        mapping = map_rules([r.record.fields for r in records], origin="board6.PcbDoc", layers=layers)
        return sorted(
            (str(r.kind), repr(r.selector_a), repr(r.selector_b), r.min, r.opt, r.max, r.layers, r.priority)
            for r in mapping.ruleset.rules
        )

    assert neutral(after) == neutral(before)


def test_a_board_without_kept_records_holds_neither_key(tmp_path: Path) -> None:
    """The two keys are additive: a board whose records all map serialises without them."""
    design = AltiumBackend().read(rules_project(tmp_path / "src", RECORDS[:1])).design
    text = dumps(design)
    assert KEPT_RULE not in text and KEPT_RECORD not in text


def test_the_import_knows_the_kinds_the_writer_rebuilds() -> None:
    """The import may not import the writer: ``read.rules.WRITTEN_KINDS`` names its kinds."""
    from fenolite.backends.altium.read.rules import WRITTEN_KINDS
    from fenolite.backends.altium.rulemap import KIND_ORDER

    assert set(KIND_ORDER) == WRITTEN_KINDS
