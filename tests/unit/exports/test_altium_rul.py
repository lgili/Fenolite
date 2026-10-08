# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule file written from neutral rules and the export kind ``altium-rul`` (capability
altium-project-reader, "Rule file written"; manufacturing-exports, "Altium rule file export"; change c0084;
hypothesis ``H-A-RULE-FILE``). Hermetic: the rules are authored here or come from the example scripts."""

from __future__ import annotations

import runpy
import tempfile
from pathlib import Path

import pytest
from _altium import blink as altium_blink
from _altium import blink_resolver, blink_tree
from _buildhelp import blink, build

from fenolite.backends.altium import rulemap
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.rul import read_rule_file
from fenolite.backends.altium.read.rules import map_rules
from fenolite.backends.kicad.dru import read_rules
from fenolite.dsl import Design, mm, placements, to_model
from fenolite.dsl.select import netclass
from fenolite.exports import altium_rul
from fenolite.lens.altium import build_altium
from fenolite.model.rules import Rule, Selector

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
SCRIPTS = sorted(path.relative_to(EXAMPLES).as_posix() for path in EXAMPLES.glob("*/*.py"))
OFFICIAL = "blink_official/design.py"
"""The one example that resolves its parts from the official KiCad libraries when it is built; its rules
need no library, so it is read here like the others."""


def with_rules(design: Design, *, vias: bool = True) -> Design:
    """``vias`` off leaves out the via style: a KiCad build takes no preferred via drill."""
    design.rules.minimum(clearance=mm(0.15), edge_clearance=mm(0.5), track_width=mm(0.2))
    design.rules.minimum(clearance=mm(0.25), netclass="PWR")
    design.rules.rule(
        "w", "track_width", where=netclass("PWR"), min=mm(0.4), opt=mm(0.5), max=mm(2), priority=1
    )
    if vias:
        design.rules.rule("via_d", "via_diameter", min=mm(0.5), opt=mm(0.6), max=mm(0.8))
        design.rules.rule("via_h", "via_drill", min=mm(0.25), opt=mm(0.3), max=mm(0.4))
    design.rules.rule("holes", "hole_size", min=mm(0.3), max=mm(6))
    design.rules.rule("apart", "hole_to_hole", min=mm(0.25))
    design.rules.rule("ring", "annular_width", min=mm(0.125))
    design.rules.rule("silk", "silk_clearance", min=mm(0.15))
    return design


def rules_of(design: Design) -> tuple[Rule, ...]:
    found = to_model(design).rules
    return found.rules if found is not None else ()


def read_file(data: bytes) -> list[Rule]:
    """The neutral rules of a written rule file; every record must map."""
    file = read_rule_file(data, file="x.RUL")
    assert file.kind == "export" and file.to_bytes() == data
    # the end mark is the single byte B6, as in the public file that Altium saved: not UTF-8
    assert [issue.code for issue in file.issues] == ["altium.text.encoding-assumed"]
    mapping = map_rules([record.fields for record in file.records], origin="x.RUL")
    assert mapping.unmapped == ()
    return list(mapping.ruleset.rules)


def test_readback_of_a_rule_of_every_kind() -> None:
    """Scenario "Written file reads back", on one rule of every ``exact`` kind."""
    rules = rules_of(with_rules(altium_blink()))
    data = rulemap.write_rule_file(rules, name="blink")
    lowered = rulemap.lower(rules)
    assert {rule.kind for rule in lowered.written} == {row.neutral for row in rulemap.TABLE if row.exact}
    assert rulemap.same_rules(read_file(data), lowered.written)
    assert [(item.kind, item.reason) for item in lowered.not_lowered] == [
        ("track_width", "value-unsupported"),
        ("silk_clearance", "no-counterpart"),
    ]


@pytest.mark.parametrize("script", SCRIPTS)
def test_readback_of_every_example_script(script: str) -> None:
    """Scenario "Written file reads back": the rules of every example script. A script without a rule
    that lowers gives no bytes, which is no rule file."""
    design = next(v for v in runpy.run_path(str(EXAMPLES / script)).values() if isinstance(v, Design))
    rules = rules_of(design)
    lowered = rulemap.lower(rules)
    data = rulemap.write_rule_file(rules, name=design.name)
    if not lowered.records:
        assert data == b""
        return
    assert rulemap.same_rules(read_file(data), lowered.written)


def test_some_example_holds_rules() -> None:
    """The readback above is not empty: at least one example lowers a rule."""
    found = []
    for script in SCRIPTS:
        design = next(v for v in runpy.run_path(str(EXAMPLES / script)).values() if isinstance(v, Design))
        found += rulemap.lower(rules_of(design)).records
    assert found


def test_the_form_of_the_written_file() -> None:
    """The line ends and the encoding of ``rule-file.md``, "Writing a rule file"."""
    rules = [
        Rule(id="rul_a", name="a", kind="clearance", selector_a=Selector("all"), min=200_000),
        Rule(
            id="rul_b",
            name="b",
            kind="clearance",
            selector_a=Selector("netclass", "PWR"),
            min=300_000,
            priority=1,
        ),
    ]
    data = rulemap.write_rule_file(rules, name="board")
    assert data == rulemap.write_rule_file(list(reversed(rules)), name="board")
    assert data != rulemap.write_rule_file(rules, name="other")  # the name seeds the unique ids
    lines = data.split(b"\n")
    assert lines[-1] == b"" and len(lines) == 3 and b"\r" not in data
    assert all(line.endswith(b"\xb6") and line[:-1].isascii() for line in lines[:-1])
    first = lines[0][:-1].decode("ascii").split("|")
    assert first[:8] == [
        "SELECTION=FALSE",
        "LAYER=TOP",
        "LOCKED=FALSE",
        "POLYGONOUTLINE=FALSE",
        "USERROUTED=TRUE",
        "UNIONINDEX=0",
        "RULEKIND=Clearance",
        "NETSCOPE=DifferentNets",
    ]
    assert (
        "NAME=Clearance_PWR" in first
        and "PRIORITY=1" in first
        and "SCOPE1EXPRESSION=InNetClass('PWR')" in first
    )
    assert first[-4:] == [
        "GAP=11.811mil",
        "GENERICCLEARANCE=11.811mil",
        "IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE",
        "OBJECTCLEARANCES=",
    ]
    assert rulemap.write_rule_file([]) == b""


def test_rule_file_from_a_built_project() -> None:
    """Scenario "Rule file from a built project": the rule file of the rules file that the KiCad build of
    a script writes holds the rules that the Altium build of the same script writes into its PCB
    document."""
    kicad = build(with_rules(blink(), vias=False), 10)
    text = kicad.files["blink.kicad_dru"].decode("utf-8")
    exported = altium_rul.export_rules(read_rules(text).rules, stem="blink")
    assert exported.path == "blink.RUL" and exported.evidence == rulemap.EVIDENCE
    assert [(item["kind"], item["reason"]) for item in exported.not_lowered] == [
        ("track_width", "value-unsupported"),
        ("silk_clearance", "no-counterpart"),
    ]
    from_file = read_file(exported.data)
    design = with_rules(altium_blink(), vias=False)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        output = build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            resolver=blink_resolver(root, blink_tree(root)),
        )
    document = read_pcbdoc(output.files["blink.PcbDoc"], file="blink.PcbDoc")
    mapping = map_rules([r.fields for r in document.rules], origin="blink.PcbDoc")
    written = {item["rule"] for item in output.summary["rules"]["written"]}  # type: ignore[index]
    in_document = [rule for rule in mapping.ruleset.rules if rule.name in written]
    assert rulemap.same_rules(from_file, in_document)
    assert [rule.name for rule in from_file] == [rule.name for rule in in_document]
    assert [rule.priority for rule in from_file] == [rule.priority for rule in in_document]
    assert exported.written == tuple(output.summary["rules"]["written"])  # type: ignore[index]
