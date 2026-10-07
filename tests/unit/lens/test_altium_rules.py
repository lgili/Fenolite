# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rules of a script in an Altium build (capability altium-build, "Rules in an Altium build"; capability
altium-pcb-writer, "Scoped rule records"; change c0084; hypothesis ``H-A-RULE-READBACK``).

Each build's PCB document is read back with Fenolite's own reader and its rule records are mapped onto the
neutral rules: own readback, which proves that the writer and the reader agree, not what Altium reads.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest
from _altium import blink, blink_resolver, blink_tree, example, example_resolver, hier_board
from _altium_board6 import board6_build, board6_model
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from fenolite.backends.altium import pcbdoc, rulemap
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.rules import map_rules
from fenolite.dsl import USB2, Design, Net, mm, placements, to_model
from fenolite.dsl.select import net, netclass
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput
from fenolite.model.rules import Rule, RuleSet, Selector

DOCUMENT = "blink.PcbDoc"
C0038 = ["Clearance_PWR", "Clearance", "Width_PWR", "Width", "RoutingVias"]
"""The rules the build wrote before change c0084 for the blink (class ``PWR``, Fenolite's defaults)."""


def built(design: Design, *, document: bool = True) -> BuildOutput:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        if document:
            output = build_altium(
                to_model(design),
                name=design.name,
                placed=tuple(placements(design)),
                placements=placements(design),
                resolver=blink_resolver(root, blink_tree(root)),
            )
        else:
            output = build_altium(to_model(design), name=design.name, resolver=example_resolver(root))
    assert output.files, [i.message for i in output.issues]
    return output


def read_back(
    output: BuildOutput, name: str = DOCUMENT
) -> tuple[list[tuple[str, str, int, str, str]], list[Rule]]:
    """The rule records of the built document as (kind, name, priority, scope1, scope2), and the neutral
    rules they map to; every record must map."""
    document = read_pcbdoc(output.files[name], file=name)
    mapping = map_rules([r.fields for r in document.rules], origin=name)
    assert mapping.unmapped == (), mapping.unmapped
    header = [
        (r.rule_kind or "", r.name or "", r.priority or 0, r.scope1 or "", r.scope2 or "")
        for r in document.rules
    ]
    assert [r.kind_number for r in document.rules] == [
        rulemap.row_of(next(rule.kind for rule in mapping.ruleset.rules if rule.name == r.name)).number
        for r in document.rules
    ]
    return header, list(mapping.ruleset.rules)


def fields_of(record: bytes) -> list[tuple[str, str | None]]:
    """The pairs of one ``Rules6`` record as ``rule_records`` returns it: a 16-bit kind number, a 32-bit
    length and the property text, ended by a NUL."""
    text = record[6:].rstrip(b"\x00").decode("ascii")
    return [(key, value) for key, _sep, value in (part.partition("=") for part in text.split("|") if part)]


def not_lowered(output: BuildOutput) -> list[tuple[str, str, str]]:
    found = [
        i for i in output.issues if i.code == "altium.not-lowered" and i.where.startswith("design-rules")
    ]
    assert all(i.where.startswith("design-rules/") for i in found)
    return [(i.where, i.severity, i.message) for i in found]


def summary(output: BuildOutput) -> dict[str, list[dict[str, str]]]:
    return output.summary["rules"]  # type: ignore[return-value]


def lowered_of(design: Design) -> list[Rule]:
    return list(rulemap.lower(to_model(design).rules.rules).written)  # type: ignore[union-attr]


def test_a_design_without_rules_gets_the_rules_of_c0038() -> None:
    """ "A design without rules MUST get the rules the build wrote before this change"."""
    output = built(blink())
    header, _rules = read_back(output)
    assert [name for _kind, name, _priority, _first, _second in header] == C0038
    assert summary(output) == {"written": [], "not_lowered": []}
    assert not_lowered(output) == []


def test_edge_clearance_reaches_the_board() -> None:
    """Scenario "Edge clearance reaches the board"."""
    design = blink()
    design.rules.minimum(edge_clearance=mm(0.5))
    output = built(design)
    header, rules = read_back(output)
    assert [name for _kind, name, _priority, _first, _second in header] == [*C0038, "BoardOutlineClearance"]
    (edge,) = [rule for rule in rules if rule.kind == "edge_clearance"]
    assert abs((edge.min or 0) - 500_000) <= 2 and edge.selector_a == Selector("all") and edge.priority == 1
    assert summary(output) == {
        "written": [{"kind": "edge_clearance", "selector": "all", "rule": "BoardOutlineClearance"}],
        "not_lowered": [],
    }
    assert not_lowered(output) == []
    assert not [i for i in output.issues if i.where == "design-rules"]


def test_a_kind_without_a_counterpart() -> None:
    """Scenario "A kind without a counterpart": one warning per rule, with the selector and the reason."""
    design = blink()
    design.rules.minimum(edge_clearance=mm(0.5))
    design.rules.rule("silk", "silk_clearance", min=mm(0.15))
    design.rules.rule("hv", "creepage", where=netclass("PWR"), min=mm(4))
    design.rules.minimum(track_width=mm(0.2))
    output = built(design)
    found = not_lowered(output)
    assert [(where, severity) for where, severity, _message in found] == [
        ("design-rules/track_width", "warning"),
        ("design-rules/silk_clearance", "warning"),
        ("design-rules/creepage", "warning"),
    ]
    assert "'min_track_width' (all)" in found[0][2] and "value-unsupported" in found[0][2]
    assert "'hv' (netclass PWR)" in found[2][2] and "no-counterpart" in found[2][2]
    assert summary(output)["not_lowered"] == [
        {"kind": "track_width", "selector": "all", "reason": "value-unsupported"},
        {"kind": "silk_clearance", "selector": "all", "reason": "no-counterpart"},
        {"kind": "creepage", "selector": "netclass PWR", "reason": "no-counterpart"},
    ]
    assert [item["kind"] for item in summary(output)["written"]] == ["edge_clearance"]
    header, _rules = read_back(output)
    assert [name for _kind, name, _priority, _first, _second in header] == [*C0038, "BoardOutlineClearance"]


def test_class_rule_above_the_general_rule() -> None:
    """Scenario "Class rule above the general rule": the rules of the design replace the class rule and
    the default of the same scope, and the class rule has the higher priority."""
    design = blink()
    design.rules.rule("w", "track_width", min=mm(0.15), opt=mm(0.25), max=mm(2))
    design.rules.rule(
        "w_pwr", "track_width", where=netclass("PWR"), min=mm(0.4), opt=mm(0.5), max=mm(2), priority=1
    )
    output = built(design)
    header, rules = read_back(output)
    assert [entry for entry in header if entry[0] == "Width"] == [
        ("Width", "Width_PWR", 1, "InNetClass('PWR')", "All"),
        ("Width", "Width", 2, "All", "All"),
    ]
    widths = [rule for rule in rules if rule.kind == "track_width"]
    assert [(rule.selector_a, rule.priority) for rule in widths] == [
        (Selector("netclass", "PWR"), 1),
        (Selector("all"), 2),
    ]
    assert rulemap.same_rules(widths, lowered_of(design))
    assert [name for kind, name, *_rest in header if kind != "Width"] == [
        "Clearance_PWR",
        "Clearance",
        "RoutingVias",
    ]


def test_design_rules_come_before_the_class_rules_of_other_scopes() -> None:
    design = blink()
    design.rules.minimum(clearance=mm(0.15))
    design.rules.rule(
        "gap_led", "clearance", where=net("LED"), between=netclass("PWR"), min=mm(0.3), priority=1
    )
    output = built(design)
    header, rules = read_back(output)
    assert [entry for entry in header if entry[0] == "Clearance"] == [
        ("Clearance", "Clearance_net_LED_to_PWR", 1, "InNet('LED')", "InNetClass('PWR')"),
        ("Clearance", "Clearance", 2, "All", "All"),
        ("Clearance", "Clearance_PWR", 3, "InNetClass('PWR')", "All"),
    ]
    assert rulemap.same_rules([r for r in rules if r.kind == "clearance"][:2], lowered_of(design))
    assert [(r.min, r.selector_b) for r in rules if r.name == "Clearance_net_LED_to_PWR"] == [
        (299_999, Selector("netclass", "PWR"))
    ]


def every_kind(design: Design) -> Design:
    design.rules.minimum(clearance=mm(0.15), edge_clearance=mm(0.5))
    design.rules.rule(
        "w", "track_width", where=netclass("PWR"), min=mm(0.4), opt=mm(0.5), max=mm(2), priority=1
    )
    design.rules.rule("via_d", "via_diameter", min=mm(0.5), opt=mm(0.6), max=mm(0.8))
    design.rules.rule("via_h", "via_drill", min=mm(0.25), opt=mm(0.3), max=mm(0.4))
    design.rules.rule("holes", "hole_size", min=mm(0.3), max=mm(6))
    design.rules.rule("apart", "hole_to_hole", min=mm(0.25))
    design.rules.rule("ring", "annular_width", min=mm(0.125))
    return design


def test_readback() -> None:
    """``H-A-RULE-READBACK``: one rule of every ``exact`` kind reads back equal, within 2 nm."""
    design = every_kind(blink())
    output = built(design)
    header, rules = read_back(output)
    lowered = lowered_of(design)
    assert {rule.kind for rule in lowered} == {row.neutral for row in rulemap.TABLE if row.exact}
    names = {item["rule"] for item in summary(output)["written"]}
    read = [rule for rule in rules if rule.name in names]
    assert rulemap.same_rules(read, lowered)
    assert not_lowered(output) == [] and summary(output)["not_lowered"] == []
    assert [kind for kind, *_rest in header] == sorted(
        (kind for kind, *_rest in header), key=rulemap.KIND_ORDER.index
    )
    for kind in rulemap.KIND_ORDER:
        priorities = [priority for found, _name, priority, *_rest in header if found == kind]
        assert priorities == list(range(1, len(priorities) + 1))
    assert len({name for _kind, name, *_rest in header}) == len(header)
    again = built(every_kind(blink()))
    assert again.files[DOCUMENT] == output.files[DOCUMENT]  # equal names and unique ids in two builds


SCRIPTS: dict[str, Callable[[], Design]] = {"blink_2layer": blink, "altium_hier_board": hier_board}


@pytest.mark.parametrize("script", sorted(SCRIPTS))
def test_readback_of_examples(script: str) -> None:
    """The rules of each example that writes a PCB document from the script's own placements."""
    design = SCRIPTS[script]()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        output = build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            resolver=blink_resolver(root, blink_tree(root)),
        )
    (name,) = [file for file in output.files if file.endswith(".PcbDoc")]
    _header, rules = read_back(output, name)
    written = {item["rule"] for item in summary(output)["written"]}
    assert rulemap.same_rules([r for r in rules if r.name in written], lowered_of(design))


_VALUES = st.integers(min_value=50, max_value=4000).map(lambda value: value * 1000)
_WHERE = st.sampled_from([None, "PWR", "net:LED", "net:VCC"])


_KINDS = st.sampled_from(["clearance", "edge_clearance", "annular_width", "hole_to_hole"])


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.tuples(_KINDS, _WHERE, _VALUES, st.integers(0, 3)), max_size=6))
def test_readback_of_generated_rule_sets(found: list[tuple[str, str | None, int, int]]) -> None:
    """``H-A-RULE-READBACK`` on generated rule sets, through the records of ``rule_records``."""
    rules = [
        Rule(
            id=f"rul_{index}",
            name=f"r{index}",
            kind=kind,  # type: ignore[arg-type]
            selector_a=Selector("all")
            if where is None
            else Selector("net", where[4:])
            if where.startswith("net:")
            else Selector("netclass", where),
            min=value,
            priority=priority,
        )
        for index, (kind, where, value, priority) in enumerate(found)
    ]
    lowered = rulemap.lower(rules)
    classes = (pcbdoc.NetClassSpec("PWR", ("VCC",), clearance=200_000),)
    spec = pcbdoc.PcbDocSpec(outline=(), net_classes=classes, design_rules=lowered.records)
    records = [fields_of(record) for record in pcbdoc.rule_records(spec, "x.PcbDoc")]
    lifted, opaque = rulemap.lift(records)
    assert opaque == {}
    written = {record.name for record in lowered.records}
    assert rulemap.same_rules([rule for rule in lifted if rule.name in written], lowered.written)
    assert len({dict(r)["NAME"] for r in records}) == len(records)


def test_no_document_no_rule_is_written() -> None:
    """Without a PCB document every rule is reported, with the reason ``no-document``."""
    design = example()
    design.rules.minimum(clearance=mm(0.15))
    output = built(design, document=False)
    assert not any(name.endswith(".PcbDoc") for name in output.files)
    assert summary(output) == {
        "written": [],
        "not_lowered": [{"kind": "clearance", "selector": "all", "reason": "no-document"}],
    }
    ((where, severity, message),) = not_lowered(output)
    assert (where, severity) == ("design-rules/clearance", "warning") and "no-document" in message


def test_class_rule_named_like_a_net_rule_keeps_both() -> None:
    lowered = rulemap.lower(
        [Rule(id="rul_a", name="a", kind="clearance", selector_a=Selector("net", "X"), min=300_000)]
    )
    spec = pcbdoc.PcbDocSpec(
        outline=(),
        net_classes=(pcbdoc.NetClassSpec("net_X", ("N",), clearance=200_000),),
        design_rules=lowered.records,
    )
    names = [dict(fields_of(record))["NAME"] for record in pcbdoc.rule_records(spec, "x.PcbDoc")]
    assert names[:3] == ["Clearance_net_X", "Clearance_net_X_class", "Clearance"]


def test_a_rule_of_the_design_replaces_the_default_of_its_scope() -> None:
    """Capability altium-pcb-writer, "Design rule records", scenario "A rule of the design replaces the
    default of its scope"."""
    design = blink()
    design.rules.minimum(clearance=mm(0.15), edge_clearance=mm(0.5))
    output = built(design)
    document = read_pcbdoc(output.files[DOCUMENT], file=DOCUMENT)
    found = [(r.name, r.kind_number, r.priority, dict(r.fields).get("GAP")) for r in document.rules]
    assert found == [
        ("Clearance", 0, 1, "5.9055mil"),
        ("Clearance_PWR", 0, 2, "7.874mil"),
        ("Width_PWR", 2, 1, None),
        ("Width", 2, 2, None),
        ("RoutingVias", 11, 1, None),
        ("BoardOutlineClearance", 63, 1, "19.685mil"),
    ]
    assert [r.scope1 for r in document.rules if r.rule_kind == "Clearance"] == ["All", "InNetClass('PWR')"]
    assert set(output.evidence.hypotheses) >= set(rulemap.EVIDENCE.hypotheses)


# --- the six-layer sample of change c0085: rule records do not depend on the stack ------------------


def model_rules() -> tuple[Rule, ...]:
    """One rule of every ``exact`` kind as model rules, with a net scope and a pair of nets."""
    everything, vin = Selector("all"), Selector("net", "VIN")
    return (
        Rule(id="rul_b6_gap", name="gap", kind="clearance", selector_a=everything, min=150_000),
        Rule(
            id="rul_b6_pair",
            name="pair",
            kind="clearance",
            selector_a=vin,
            selector_b=Selector("net", "GND"),
            min=300_000,
            priority=1,
        ),
        Rule(id="rul_b6_edge", name="edge", kind="edge_clearance", selector_a=everything, min=500_000),
        Rule(
            id="rul_b6_w",
            name="w",
            kind="track_width",
            selector_a=vin,
            min=400_000,
            opt=500_000,
            max=2_000_000,
        ),
        Rule(
            id="rul_b6_d",
            name="via_d",
            kind="via_diameter",
            selector_a=everything,
            min=500_000,
            opt=600_000,
            max=800_000,
        ),
        Rule(
            id="rul_b6_h",
            name="via_h",
            kind="via_drill",
            selector_a=everything,
            min=250_000,
            opt=300_000,
            max=400_000,
        ),
        Rule(
            id="rul_b6_holes",
            name="holes",
            kind="hole_size",
            selector_a=everything,
            min=300_000,
            max=6_000_000,
        ),
        Rule(id="rul_b6_apart", name="apart", kind="hole_to_hole", selector_a=everything, min=250_000),
        Rule(id="rul_b6_ring", name="ring", kind="annular_width", selector_a=everything, min=125_000),
    )


def test_board6_rules_are_written_and_read_back() -> None:
    """The six-layer sample with a plane, a blind and a buried via (``tests/_altium_board6.py``) takes the
    same rule records as a two-layer board: a record holds no layer and no layer count. Its rules read back
    equal, the account of ``result.pcb`` counts them, and without rules the sample's files are unchanged."""
    rules = model_rules()
    lowered = rulemap.lower(rules)
    assert lowered.not_lowered == () and len(lowered.written) == len(rules)
    model = dataclasses.replace(board6_model(), rules=RuleSet(id="rst_board6_rules", rules=rules))
    with tempfile.TemporaryDirectory() as folder:
        output = board6_build(Path(folder), model)
        plain = board6_build(Path(folder))
    assert not [found for found in output.issues if found.severity == "error"]
    assert output.summary["copper"]["layers"] == 6  # type: ignore[index]
    assert output.summary["pcb"]["written"]["rule"] == len(rules)  # type: ignore[index]
    assert "rule" not in output.summary["pcb"]["not_lowered"]  # type: ignore[index]
    assert not_lowered(output) == [] and summary(output)["not_lowered"] == []
    name = "board6.PcbDoc"
    _header, read = read_back(output, name)
    written = {item["rule"] for item in summary(output)["written"]}
    assert rulemap.same_rules([rule for rule in read if rule.name in written], lowered.written)
    # the records are those of the lowering, whatever the stack: only the unique id is the document's
    document = read_pcbdoc(output.files[name], file=name)
    by_name = {record.name: record for record in lowered.records}
    seen = 0
    for record in document.rules:
        if record.name not in by_name:
            continue
        seen += 1
        mine = [(key, value) for key, value in by_name[record.name].fields() if key != "UNIQUEID"]
        keys = [key for key, _value in record.fields]
        theirs = [(k, v) for k, v in record.fields[keys.index("RULEKIND") :] if k != "UNIQUEID"]
        assert theirs == mine, record.name
    assert seen == len(lowered.records)
    # without rules the sample is the committed one, and with them only the document and the model differ
    assert summary(plain) == {"written": [], "not_lowered": []}
    data = Path(__file__).resolve().parents[2] / "data" / "altium" / "board6"
    for file in ("board6.PcbDoc", "board6.PcbLib", "board6.PrjPcb", "board6.SchDoc", "board6.SchLib"):
        assert plain.files[file] == (data / file).read_bytes(), file
        assert (output.files[file] == plain.files[file]) is (file != name), file


def test_no_tracks_rule_is_reported_and_not_written() -> None:
    """Scenario "A track layer rule in an Altium build" (capability altium-pcb-writer, "Track layer rules in
    the Altium rule table"; change c0107): one ``altium.not-lowered`` warning naming the rule, the reason
    ``no-counterpart`` in the result, and the rule records of the same script without the rule."""
    plain = built(blink())
    design = blink()
    design.rules.rule("sig-outer", "no_tracks", where=netclass("PWR"), layers=("F.Cu",))
    output = built(design)
    ((where, severity, message),) = not_lowered(output)
    assert (where, severity) == ("design-rules/no_tracks", "warning")
    assert "'sig-outer' (netclass PWR on F.Cu)" in message and "no-counterpart" in message
    assert summary(output) == {
        "written": [],
        "not_lowered": [
            {"kind": "no_tracks", "selector": "netclass PWR on F.Cu", "reason": "no-counterpart"}
        ],
    }
    assert read_back(output)[0] == read_back(plain)[0]
    document = read_pcbdoc(output.files[DOCUMENT], file=DOCUMENT)
    before = read_pcbdoc(plain.files[DOCUMENT], file=DOCUMENT)
    assert [r.fields for r in document.rules] == [r.fields for r in before.rules]
    # the thirteenth row: the five pair and length kinds of change c0104 follow it
    row = rulemap.TABLE[12]
    assert (row.neutral, row.status, row.exact) == ("no_tracks", "no-counterpart", False)
    assert "Routing Layers" in row.note and "no public file" in row.note
    lowered = rulemap.lower(to_model(design).rules.rules)  # type: ignore[union-attr]
    assert lowered.written == () and len(lowered.not_lowered) == 1


# -- differential pairs in an Altium build (capability altium-build; change c0104)


def pair_design(*, pair_content: bool = True, document: bool = True) -> Design:
    """The blink (the example of the build without a PCB document when ``document`` is false) with a USB
    pair in the class ``USB``; with ``pair_content`` the class holds a pair gap and the pair has its
    rules."""
    design = blink() if document else example()
    usb_p, usb_n = Net("USB_P"), Net("USB_N")
    usb = USB2(usb_p, usb_n)
    design.add(usb)
    gap = mm(0.15) if pair_content else None
    design.rules.netclass("USB", clearance=mm(0.2), diff_pair_gap=gap, nets=(usb_p, usb_n))
    if pair_content:
        design.rules.pair(
            usb,
            gap_min=mm(0.13),
            clearance=mm(0.15),
            uncoupled_max=mm(5),
            skew_max=mm(0.5),
            length_max=mm(60),
        )
    return design


@pytest.mark.parametrize("document", [True, False])
def test_pair_rules_in_an_altium_build(document: bool) -> None:
    """Scenario "Pair rules in an Altium build": nothing raises, each pair or length rule is named with
    ``no-counterpart``, the pair clearance rule with ``scope-unsupported``, and the class pair values in
    one info, with and without a PCB document."""
    output = built(pair_design(document=document), document=document)
    values = [i for i in output.issues if i.code == "altium.not-lowered" and i.where == "pair-values"]
    assert [(i.severity, "USB" in i.message, "PWR" in i.message) for i in values] == [("info", True, False)]
    interfaces = [i for i in output.issues if i.code == "altium.not-lowered" and i.where == "interfaces"]
    assert len(interfaces) == 1 and "USB_P/USB_N" in interfaces[0].message
    if not document:  # no document: every rule is named with that reason, the pair rules included
        reasons = {entry["kind"]: entry["reason"] for entry in summary(output)["not_lowered"]}
        assert reasons.pop("clearance") in ("no-document", "scope-unsupported")
        assert reasons == dict.fromkeys(
            ("diff_pair_gap", "diff_pair_uncoupled", "diff_pair_skew", "length"), "no-counterpart"
        )
        return
    found = not_lowered(output)
    assert [(where, severity) for where, severity, _message in found] == [
        ("design-rules/diff_pair_gap", "warning"),
        ("design-rules/clearance", "warning"),
        ("design-rules/diff_pair_uncoupled", "warning"),
        ("design-rules/diff_pair_skew", "warning"),
        ("design-rules/length", "warning"),
    ]
    reasons = ["no-counterpart", "scope-unsupported", "no-counterpart", "no-counterpart", "no-counterpart"]
    for (_where, _severity, message), reason in zip(found, reasons, strict=True):
        assert reason in message and "diff_pair USB_" in message
    assert [(entry["kind"], entry["reason"]) for entry in summary(output)["not_lowered"]] == [
        ("diff_pair_gap", "no-counterpart"),
        ("clearance", "scope-unsupported"),
        ("diff_pair_uncoupled", "no-counterpart"),
        ("diff_pair_skew", "no-counterpart"),
        ("length", "no-counterpart"),
    ]


@pytest.mark.parametrize("document", [True, False])
def test_pair_files_equal_without_the_pair_content(document: bool) -> None:
    """Scenario "Files equal without the pair content": every planned file outside ``.fenolite/`` is
    byte-equal to the file of the design without the pair rules and the class pair gap."""
    with_pair = built(pair_design(document=document), document=document)
    without = built(pair_design(pair_content=False, document=document), document=document)
    outside = {name for name in without.files if not name.startswith(".fenolite/")}
    assert outside and outside == {name for name in with_pair.files if not name.startswith(".fenolite/")}
    assert all(with_pair.files[name] == without.files[name] for name in outside)
    assert b"diff_pair_gap" in with_pair.files[".fenolite/circuit.json"]
    assert b"diff_pair_skew" in with_pair.files[".fenolite/rules.json"]
    assert not [i for i in without.issues if i.where == "pair-values"]
