# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Short-Circuit and Net Antennae records (change c0465, design D5; capability altium-project-reader,
"Short-Circuit and Net Antennae records map"): read onto ``short`` and ``antenna`` rules where a record of
the document relaxes the check, and written back with the keys of the public records (S-2243). Every record
here is authored for Fenolite."""

from __future__ import annotations

from collections.abc import Sequence

from fenolite.backends.altium import rulemap
from fenolite.backends.altium.read.rules import (
    CHECKED_KINDS,
    HEADER_KEYS,
    RULE_KIND_MAP,
    Field,
    RuleMapping,
    map_rules,
)
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, Selector

MIL = 25_400


def record(kind: str, *keys: tuple[str, str], **header: str) -> list[Field]:
    """A field list with every header key (defaults below, ``header`` overrides) and ``keys``."""
    values = {
        "RULEKIND": kind,
        "NETSCOPE": "AnyNet",
        "LAYERKIND": "SameLayer",
        "SCOPE1EXPRESSION": "All",
        "SCOPE2EXPRESSION": "All",
        "NAME": kind,
        "ENABLED": "TRUE",
        "PRIORITY": "1",
        "COMMENT": "",
        "UNIQUEID": "ABCDEFGH",
        "DEFINEDBYLOGICALDOCUMENT": "FALSE",
    } | header
    return [*((key, values[key]) for key in HEADER_KEYS), *keys]


def mapped(*records: Sequence[Field]) -> RuleMapping:
    return map_rules(records, origin="allow")


def short(allowed: str, first: str = "All", second: str = "All", **header: str) -> list[Field]:
    return record(
        "ShortCircuit", ("ALLOWED", allowed), SCOPE1EXPRESSION=first, SCOPE2EXPRESSION=second, **header
    )


def antenna(tolerance: str, **header: str) -> list[Field]:
    return record("NetAntennae", ("NETANTENNAETOLERANCE", tolerance), **header)


def test_an_allowed_short_and_a_default_rule() -> None:
    """Scenario "An allowed short and a default rule"."""
    mapping = mapped(
        short("TRUE", "InNet('AGND')", "InNet('DGND')", NAME="Allowed"),
        short("FALSE", NAME="ShortCircuit", PRIORITY="2"),
        antenna("50mil"),
    )
    assert mapping.unmapped == ()
    assert not [issue for issue in mapping.issues if issue.code == "altium.rules.check-relaxed"]
    allowed, default, stub = mapping.ruleset.rules
    assert (allowed.kind, allowed.severity, allowed.priority) == ("short", "ignore", 1)
    assert (allowed.selector_a, allowed.selector_b) == (Selector("net", "AGND"), Selector("net", "DGND"))
    assert (default.kind, default.severity, default.priority) == ("short", "error", 2)
    assert (default.selector_a, default.selector_b) == (Selector("all"), Selector("all"))
    assert (stub.kind, stub.max, stub.min, stub.selector_a, stub.selector_b) == (
        "antenna",
        50 * MIL,
        None,
        Selector("all"),
        None,
    )
    assert mapping.rule_records == (0, 1, 2)


def test_nothing_relaxed_nothing_mapped() -> None:
    """Scenario "Nothing relaxed, nothing mapped": a rule that forbids a short is Fenolite's own check."""
    mapping = mapped(short("FALSE"), antenna("0mil"))
    assert mapping.ruleset.rules == ()
    assert [(u.kind, u.reason) for u in mapping.unmapped] == [
        ("ShortCircuit", "checked"),
        ("NetAntennae", "checked"),
    ]


def test_each_kind_maps_on_its_own() -> None:
    """A tolerance maps the Net Antennae records and leaves the Short-Circuit records checked; a disabled
    record that relaxes makes nothing map."""
    mapping = mapped(short("FALSE"), antenna("1mil"), antenna("0mil", NAME="Zero", PRIORITY="2"))
    assert [(u.kind, u.reason) for u in mapping.unmapped] == [("ShortCircuit", "checked")]
    assert [(rule.kind, rule.max) for rule in mapping.ruleset.rules] == [("antenna", MIL), ("antenna", 0)]
    off = mapped(short("TRUE", ENABLED="FALSE"), short("FALSE", NAME="On", PRIORITY="2"))
    assert [(u.kind, u.reason) for u in off.unmapped] == [("ShortCircuit", "checked")] * 2


def test_records_that_do_not_read_stay_unmapped() -> None:
    """Another key, an ``ALLOWED`` other than ``TRUE`` and ``FALSE``, a second scope on Net Antennae, a
    disabled record among mapped ones."""
    mapping = mapped(
        short("TRUE"),
        short("MAYBE", NAME="Odd", PRIORITY="2"),
        [*short("FALSE", NAME="Extra", PRIORITY="3"), ("FUTUREKEY", "1")],
        short("TRUE", NAME="Off", PRIORITY="4", ENABLED="FALSE"),
        antenna("1mil"),
        antenna("2mil", NAME="Pair", PRIORITY="2", SCOPE2EXPRESSION="InNet('A')"),
        antenna("wide", NAME="Bad", PRIORITY="3"),
    )
    assert [(u.name, u.reason) for u in mapping.unmapped] == [
        ("Odd", "keys"),
        ("Extra", "keys"),
        ("Off", "disabled"),
        ("Pair", "scope"),
        ("Bad", "value"),
    ]
    assert [rule.kind for rule in mapping.ruleset.rules] == ["short", "antenna"]


def test_the_kinds_are_neutral() -> None:
    assert {"ShortCircuit", "NetAntennae"} <= set(RULE_KIND_MAP)
    assert not {"ShortCircuit", "NetAntennae"} & set(CHECKED_KINDS)


def _rule(kind: str, severity: str = "error", *, first: Selector, second: Selector | None = None,
          **limits: int) -> Rule:  # fmt: skip
    return Rule(
        id=derived_id("rul", "allow", f"{kind}:{severity}:{first}:{second}"),
        name=kind,
        kind=kind,  # type: ignore[arg-type]
        selector_a=first,
        selector_b=second,
        severity=severity,  # type: ignore[arg-type]
        **limits,  # type: ignore[arg-type]
    )


def test_write_both_kinds_with_the_public_keys() -> None:
    """The Altium writer lowers both kinds to their records, with the one key each public record holds
    (S-2243), and the reader maps the records back to the same rules."""
    rules = (
        _rule("short", "ignore", first=Selector("net", "AGND"), second=Selector("net", "DGND")),
        _rule("short", first=Selector("all"), second=Selector("all")),
        _rule("antenna", first=Selector("all"), max=50 * MIL),
    )
    lowered = rulemap.lower(rules)
    assert lowered.not_lowered == ()
    found = [(r.number, r.kind, r.scope1, r.scope2, r.net_scope, r.priority, r.keys) for r in lowered.records]
    assert found == [
        (15, "ShortCircuit", "InNet('AGND')", "InNet('DGND')", "AnyNet", 1, (("ALLOWED", "TRUE"),)),
        (15, "ShortCircuit", "All", "All", "AnyNet", 2, (("ALLOWED", "FALSE"),)),
        (56, "NetAntennae", "All", "All", "AnyNet", 1, (("NETANTENNAETOLERANCE", "50mil"),)),
    ]
    back, opaque = rulemap.lift(lowered.records)
    assert opaque == {}
    assert all(rulemap.same_rule(one, other) for one, other in zip(rules, back, strict=True))
    assert [rule.severity for rule in back] == ["ignore", "error", "error"]


def test_write_refuses_what_no_record_holds() -> None:
    """A ``short`` of severity ``warning``: a Short-Circuit record allows the short or not."""
    warned = _rule("short", "warning", first=Selector("all"), second=Selector("all"))
    lowered = rulemap.lower((warned,))
    assert lowered.records == ()
    assert [(n.reason, "warning" in n.detail) for n in lowered.not_lowered] == [("value-unsupported", True)]
