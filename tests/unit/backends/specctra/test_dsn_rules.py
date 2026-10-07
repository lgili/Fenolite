# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rules of a design in a Specctra design file (capability specctra-dsn, "Routing rules in design
files" and "Specctra issue codes and facts"; change c0107). Hermetic: the bench is built in process from the
built-in catalog."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import _planebench as pb
import pytest
from _specctra import DEFAULTS

from fenolite.backends.specctra import dsn
from fenolite.backends.specctra.dsn import DsnResult, write_dsn
from fenolite.backends.specctra.lexer import SNode, dumps, parse
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, Selector

ROUTED = (*pb.SIGNALS, *pb.HIGH)
ALL = Selector("all")
SRC = Path(dsn.__file__).resolve().parent
PRODUCED: set[str] = set()


def cls(name: str) -> Selector:
    return Selector("netclass", name)


def rule(name: str, kind: str, a: Selector = ALL, b: Selector | None = None, **more: object) -> Rule:
    return Rule(
        id=derived_id("rul", "test", f"dsn:{name}"),
        name=name,
        kind=kind,
        selector_a=a,
        selector_b=b,
        **more,  # type: ignore[arg-type]
    )


@pytest.fixture(scope="module")
def found(tmp_path_factory: pytest.TempPathFactory) -> Iterator[pb.Loaded]:
    folder = tmp_path_factory.mktemp("planebench")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("KICAD_CONFIG_HOME", str(folder / "kicad-config"))
        yield pb.load(pb.build_project(folder))


def write(found: pb.Loaded, *rules: Rule, keep: bool = False, **more: object) -> DsnResult:
    """The bench written with ``rules`` in place of its own (or added to them with ``keep``)."""
    used = pb.with_rules(found, *rules, replace=not keep)
    result = write_dsn(
        used.design,
        pads=used.pads,
        outline=used.outline,
        selected=ROUTED,
        defaults=DEFAULTS,
        **more,  # type: ignore[arg-type]
    )
    PRODUCED.update(issue.code for issue in result.issues)
    return result


def flat(node: SNode) -> str:
    return " ".join(dumps(node).split()).replace("( ", "(").replace(" )", ")")


def lists(result: DsnResult, section: str, head: str) -> list[str]:
    node = parse(result.text).first(section)
    assert node is not None
    return [flat(child) for child in node.lists if child.head == head]


def classes(result: DsnResult) -> dict[str, str]:
    return {text.split()[1]: text for text in lists(result, "network", "class")}


def default_rule(result: DsnResult) -> str:
    (found,) = lists(result, "structure", "rule")
    return found


def infos(result: DsnResult, code: str) -> list[str]:
    assert all(i.severity == "info" for i in result.issues if i.code == code)
    return [i.message for i in result.issues if i.code == code]


# -- clearances


def test_class_class_clearance(found: pb.Loaded) -> None:
    """Scenario "Class to class clearance": the bench's own rule ``hv-sig``."""
    result = write(found, keep=True)
    assert lists(result, "network", "class_class") == [
        "(class_class (classes HV SIG) (rule (clearance 1000)))"
    ]
    made = classes(result)
    assert made["HV"].endswith("(rule (width 500) (clearance 300)))")
    assert made["SIG"].endswith("(rule (width 200) (clearance 200)))")
    network = [node.head for node in parse(result.text).first("network").lists]  # type: ignore[union-attr]
    assert network.index("class_class") > max(i for i, head in enumerate(network) if head == "class")
    (edge,) = infos(result, "specctra.rule-not-sent")
    assert "edge_clearance" in edge and "hv_sig" not in edge


def test_board_wide_clearance_above_a_class_value(found: pb.Loaded) -> None:
    """Scenario "Board-wide clearance above a class value"."""
    result = write(found, rule("wide", "clearance", min=250_000))
    assert default_rule(result) == "(rule (width 250) (clearance 250))"
    made = classes(result)
    assert (
        "(clearance 250)" in made["SIG"]
        and "(clearance 250)" in made["PWR"]
        and "(clearance 300)" in made["HV"]
    )
    both = write(found, rule("wide", "clearance", ALL, ALL, min=250_000))
    assert both.text == result.text


def test_clearance_of_named_classes(found: pb.Loaded) -> None:
    either = Selector("or", items=(cls("SIG"), cls("PWR")))
    result = write(
        found,
        rule("some", "clearance", either, min=400_000),
        rule("low", "clearance", cls("HV"), min=100_000),
    )
    made = classes(result)
    assert (
        "(clearance 400)" in made["SIG"]
        and "(clearance 400)" in made["PWR"]
        and "(clearance 300)" in made["HV"]
    )
    assert default_rule(result) == "(rule (width 250) (clearance 200))"
    # the other side: 'all' against classes selects the same pairs
    mirrored = write(found, rule("some", "clearance", ALL, either, min=400_000))
    assert classes(mirrored)["SIG"] == made["SIG"]


def test_pairs_combine_by_maximum_and_a_class_with_itself(found: pb.Loaded) -> None:
    either = Selector("or", items=(cls("SIG"), cls("PWR")))
    result = write(
        found,
        rule("a", "clearance", cls("HV"), either, min=800_000),
        rule("b", "clearance", cls("SIG"), cls("HV"), min=1_200_000),
        rule("c", "clearance", cls("HV"), cls("HV"), min=600_000),
        rule("d", "clearance", cls("NOPE"), cls("HV"), min=5_000_000),
    )
    assert lists(result, "network", "class_class") == [
        "(class_class (classes HV PWR) (rule (clearance 800)))",
        "(class_class (classes HV SIG) (rule (clearance 1200)))",
    ]
    assert "(clearance 600)" in classes(result)["HV"]
    assert infos(result, "specctra.rule-not-sent") == []


def test_ignored_rule_is_skipped_without_an_issue(found: pb.Loaded) -> None:
    result = write(
        found,
        rule("off", "clearance", min=900_000, severity="ignore"),
        rule("off2", "hole_to_hole", min=900_000, severity="ignore"),
    )
    assert result.issues == write(found).issues and result.text == write(found).text


def test_layer_clause_is_widened(found: pb.Loaded) -> None:
    result = write(
        found,
        rule("top", "clearance", cls("HV"), cls("SIG"), min=700_000, layers=("F.Cu",)),
        rule("wide", "clearance", min=250_000, layers=("B.Cu",)),
    )
    assert lists(result, "network", "class_class") == [
        "(class_class (classes HV SIG) (rule (clearance 700)))"
    ]
    first, second = infos(result, "specctra.rule-widened")
    assert "top" in first and "F.Cu" in first and "wide" in second and "B.Cu" in second
    assert default_rule(result) == "(rule (width 250) (clearance 250))"


# -- widths


def test_per_layer_width(found: pb.Loaded) -> None:
    """Scenario "Per-layer width"."""
    width = rule("w", "track_width", cls("SIG"), layers=("F.Cu",), min=350_000, opt=350_000, max=350_000)
    made = classes(write(found, width))
    assert made["SIG"].endswith("(rule (width 200) (clearance 200)) (layer_rule F.Cu (rule (width 350))))")
    assert "layer_rule" not in made["HV"]
    every = classes(write(found, rule("w", "track_width", layers=("B.Cu", "F.Cu"), opt=300_000)))
    assert all(
        text.endswith("(layer_rule F.Cu (rule (width 300))) (layer_rule B.Cu (rule (width 300))))")
        for text in every.values()
    )


def test_width_with_and_without_opt(found: pb.Loaded) -> None:
    result = write(
        found,
        rule("pref", "track_width", cls("SIG"), min=100_000, opt=300_000),
        rule("clamp", "track_width", cls("HV"), max=450_000),
        rule("floor", "track_width", min=420_000),
    )
    made = classes(result)
    assert "(width 420)" in made["SIG"] and "(width 450)" in made["HV"] and "(width 420)" in made["PWR"]
    assert default_rule(result) == "(rule (width 420) (clearance 200))"
    assert "(width 300)" in classes(write(found, rule("pref", "track_width", cls("SIG"), opt=300_000)))["SIG"]


def test_width_rules_the_file_cannot_carry(found: pb.Loaded) -> None:
    result = write(
        found,
        rule("no-opt", "track_width", cls("SIG"), layers=("F.Cu",), min=300_000),
        rule("no-layer", "track_width", cls("SIG"), layers=("In9.Cu",), opt=300_000),
    )
    first, second = infos(result, "specctra.rule-not-sent")
    assert "no-opt" in first and "opt" in first and "no-layer" in second and "In9.Cu" in second
    assert "layer_rule" not in result.text


# -- what is not sent


def test_rules_the_file_cannot_carry(found: pb.Loaded) -> None:
    """Scenario "Rules the file cannot carry"."""
    plain = write(found)
    result = write(
        found,
        rule("net-rule", "clearance", Selector("net", "HV1"), min=900_000),
        rule("holes", "hole_to_hole", min=900_000),
    )
    assert result.text == plain.text
    first, second = infos(result, "specctra.rule-not-sent")
    assert "net-rule" in first and "holes" in second and "hole_to_hole" in second


@pytest.mark.parametrize(
    "made",
    [
        rule("glob", "clearance", cls("S*"), min=900_000),
        rule("not", "clearance", Selector("not", items=(cls("SIG"),)), min=900_000),
        rule("ref", "clearance", Selector("ref", "U1"), min=900_000),
        rule("kind", "clearance", Selector("item_kind", "via"), min=900_000),
        rule("mixed", "clearance", Selector("or", items=(cls("SIG"), Selector("net", "HV1"))), min=900_000),
        rule("b-net", "clearance", cls("SIG"), Selector("net", "HV1"), min=900_000),
        rule("via", "via_diameter", min=900_000),
        rule("creep", "creepage", cls("HV"), cls("SIG"), min=900_000),
    ],
)
def test_other_selectors_and_kinds_are_not_sent(found: pb.Loaded, made: Rule) -> None:
    result = write(found, made)
    (message,) = infos(result, "specctra.rule-not-sent")
    assert repr(made.name) in message and result.text == write(found).text


def test_no_tracks_rule_is_carried_elsewhere(found: pb.Loaded) -> None:
    result = write(found, pb.no_tracks("sig-outer", cls("SIG"), "In1.Cu"))
    assert result.text == write(found).text and infos(result, "specctra.rule-not-sent") == []


def test_default_class_without_a_model_class(found: pb.Loaded) -> None:
    """``netclass Default`` selects the nets without a class: the default rule carries their value."""
    assert "Default" not in classes(write(found))
    result = write(found, rule("d", "clearance", cls("Default"), min=450_000))
    assert (
        default_rule(result) == "(rule (width 250) (clearance 450))"
        and "(clearance 200)" in classes(result)["SIG"]
    )
    paired = write(found, rule("d", "clearance", cls("Default"), cls("HV"), min=450_000))
    (message,) = infos(paired, "specctra.rule-not-sent")
    assert "without a class" in message


# -- the edge clearance (Decision 11's fallback)


def test_edge_clearance_is_reported_and_no_band_is_written(found: pb.Loaded) -> None:
    """Scenario "Edge clearance is not sent": no keep-out band along the edges, one info per rule."""
    plain = write(found)
    result = write(found, pb.edge_rule(500_000), rule("rim", "edge_clearance", cls("HV"), min=900_000))
    assert result.text == plain.text and result.text.count("(path signal") == 1
    first, second = infos(result, "specctra.rule-not-sent")
    assert "'edge'" in first and "board edge" in first and "'rim'" in second
    edge = pb.edge_bench(1_000_000).write()
    assert edge.text.count("(path signal") == 1, "the boundary path alone"
    assert [i.code for i in edge.issues if i.code.startswith("specctra.rule")] == ["specctra.rule-not-sent"]


# -- the table of codes


def test_codes_form_a_closed_table(found: pb.Loaded) -> None:
    """Scenario "Closed table of codes": every ``specctra.*`` literal of the package is a key of
    ``ISSUE_CODES`` with its severity, and the three codes of this change are produced by these tests."""
    assert dsn.ISSUE_CODES == {
        "specctra.unknown-padstack": "error",
        "specctra.session-moved": "error",
        "specctra.pad-approximated": "warning",
        "specctra.plane-skipped": "warning",
        "specctra.rounded": "info",
        "specctra.renamed": "info",
        "specctra.unknown-list": "info",
        "specctra.rule-not-sent": "info",
        "specctra.rule-widened": "info",
    }
    literals: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        literals |= set(re.findall(r'"(specctra\.[a-z-]+)"', path.read_text(encoding="utf-8")))
    assert literals == set(dsn.ISSUE_CODES)
    both = write(found, rule("w", "clearance", min=250_000, layers=("B.Cu",)), rule("h", "hole_size", min=1))
    assert {"specctra.rule-not-sent", "specctra.rule-widened"} <= {i.code for i in both.issues} <= PRODUCED
