# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Custom rules files (``.kicad_dru``) in the full dialect: the front end, the reader and the writer.

Facts and Fenolite choices: ``docs/formats/kicad/rules.md``. Comment lines stay in place as opaque
slots, rules outside the closed grammar of ``rulemap`` stay verbatim, and every written text is checked
before it is returned. ``versions.wrap_rules`` and ``versions.rules_text`` keep their common-subset
contract; this module blanks comment lines before calling ``wrap_rules``.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from fenolite.backends.kicad import resolver, rulemap
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.sexpr import Atom, Node, dumps
from fenolite.backends.kicad.versions import (
    DEFAULT_TARGET,
    TARGET_MAJORS,
    FileKind,
    FormatInfo,
    LossyWriteError,
    VersionStatus,
    check_emittable,
    classify,
    inspect,
    major_for,
    require_editable,
    require_readable,
    version_issues,
    wrap_rules,
)
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.provenance import Provenance
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.rules import Rule, RuleSet

EVIDENCE = Evidence(
    Level.KICAD_VERIFIED, hypotheses=("H-K-DRU-DIALECT", "H-K-DRU-ORDER", "H-K-DRU-COND", "H-K-DRU-KIND")
)
"""Settled on ``kicad-cli`` 9.0.9 and 10.0.6 by the rules oracle (``tests/kicad/rules/``)."""
RULES_VERSION = 1
KEPT_CODE = "rules.kept-opaque"
DROPPED_CODE = "rules.dropped-for-target"
REFUSED_FOR_9 = frozenset({"kicad.token.too-new", "kicad.token.uninventoried"})
"""``check_emittable`` codes that refuse a preserved rule for target 9 (9.0.9 drops the whole file)."""
REWRITE_HINT = "rewrite the rule with the selectors, kinds and layers of docs/formats/kicad/rules.md"


class RulesLossError(LossyWriteError):
    """A rules write would lose content or cannot represent a rule (FEN-7001)."""

    def __init__(self, issues: Sequence[Issue], *, droppable: bool) -> None:
        super().__init__(issues, droppable=droppable)
        if not droppable:
            self.hint = REWRITE_HINT


class RulesSelfCheckError(FenoliteError):
    """The written rules text failed its self-check; no text is returned. This is a bug (FEN-1001)."""

    cli_code = "FEN-1001"

    def __init__(self, step: str, message: str, issues: Sequence[Issue] = ()) -> None:
        self.step = step
        self.issues = tuple(issues)
        self.hint = "this is a bug; report it with the rules that were written"
        super().__init__(f"rules self-check failed at step '{step}': {message}")


@dataclass(frozen=True, slots=True)
class VersionItem:
    version: int
    text: str
    line: int


@dataclass(frozen=True, slots=True)
class RuleItem:
    """A top-level list other than ``version``, with its exact source text."""

    node: Node
    text: str
    line: int
    has_comment: bool = False


@dataclass(frozen=True, slots=True)
class CommentItem:
    text: str
    line: int


RulesItem = VersionItem | RuleItem | CommentItem


@dataclass(frozen=True, slots=True)
class RulesDocument:
    items: tuple[RulesItem, ...]
    file: str = ""

    @property
    def node(self) -> Node:
        """The synthetic ``kicad_dru`` node of the version and rule lists, without comments."""
        children: list[Node] = []
        for item in self.items:
            if isinstance(item, VersionItem):
                children.append(Node(Atom.symbol("version"), (Atom.integer(item.version),)))
            elif isinstance(item, RuleItem):
                children.append(item.node)
        return Node(Atom.symbol("kicad_dru"), tuple(children))

    @property
    def version(self) -> int:
        return next(i.version for i in self.items if isinstance(i, VersionItem))


# --- the dialect front end ------------------------------------------------------------------------


def _is_comment(line: str) -> bool:
    return line.lstrip(" \t").startswith("#")


def _quoted_symbols(data: bytes, file: str) -> None:
    """Refuse a symbol atom holding ``'`` outside double-quoted strings, naming its line."""
    in_string = escaped = False
    start: int | None = None
    for pos in range(len(data) + 1):
        byte = data[pos : pos + 1]
        if in_string:
            if escaped:
                escaped = False
            elif byte == b"\\":
                escaped = True
            elif byte == b'"':
                in_string = False
            continue
        if byte in (b"", b" ", b"\t", b"\r", b"\n", b"(", b")", b'"'):
            if start is not None:
                token = data[start:pos]
                if b"'" in token:
                    line = data.count(b"\n", 0, start) + 1
                    shown = token.decode("utf-8", "replace")
                    raise FormatError(
                        f"line {line}: the single-quoted name {shown} makes KiCad drop the whole rules file; "
                        "use a double-quoted name",
                        file=file,
                        locator=f"line {line}",
                        offset=start,
                    )
                start = None
            in_string = byte == b'"'
        elif start is None:
            start = pos


def _span(data: bytes, start: int) -> int:
    """The offset just after the list that opens at ``start``."""
    depth = 0
    in_string = escaped = False
    for pos in range(start, len(data)):
        byte = data[pos]
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:
                escaped = True
            elif byte == 0x22:
                in_string = False
        elif byte == 0x22:
            in_string = True
        elif byte == 0x28:
            depth += 1
        elif byte == 0x29:
            depth -= 1
            if depth == 0:
                return pos + 1
    return len(data)


def parse_rules(text: str, *, file: str = "") -> RulesDocument:
    """The items of a rules file in order: the version list, rule lists and comment lines."""
    lines = text.split("\n")
    comments = {n: line for n, line in enumerate(lines, start=1) if _is_comment(line)}
    blanked = "\n".join(
        " " * len(line.encode("utf-8")) if n in comments else line for n, line in enumerate(lines, start=1)
    )
    data = blanked.encode("utf-8")
    original = text.encode("utf-8")
    _quoted_symbols(data, file)
    root = wrap_rules(blanked, file=file)
    found: list[tuple[int, RulesItem]] = []
    inside: set[int] = set()
    seen_version = False
    for child in root.children:
        if not isinstance(child, Node):
            raise FormatError(f"an atom {child.text!r} at top level", file=file, locator="/kicad_dru")
        start = child.offset or 0
        end = _span(data, start)
        line = data.count(b"\n", 0, start) + 1
        last = data.count(b"\n", 0, end) + 1
        source = original[start:end].decode("utf-8")
        if child.name == "version":
            if seen_version:
                raise FormatError(f"line {line}: a second version list", file=file, locator=f"line {line}")
            seen_version = True
            atoms = child.atoms()
            if len(atoms) != 1 or not atoms[0].text.isdigit():
                raise FormatError(
                    f"line {line}: the version is not an integer", file=file, locator=f"line {line}"
                )
            found.append((line, VersionItem(int(atoms[0].text), source, line)))
        else:
            held = {n for n in comments if line < n <= last}
            inside |= held
            found.append((line, RuleItem(child, source, line, bool(held))))
    found += [(n, CommentItem(text, n)) for n, text in comments.items() if n not in inside]
    if not seen_version:
        raise FormatError("the rules file has no (version N) list", file=file, locator="/kicad_dru")
    items = tuple(item for _, item in sorted(found, key=lambda pair: pair[0]))
    document = RulesDocument(items, file)
    require_readable(inspect(document.node, file=file), file=file)
    return document


def print_rules(items: Iterable[RulesItem]) -> str:
    """Each item's text followed by a newline (blank lines between items are not kept)."""
    return "".join(item.text + "\n" for item in items)


# --- reading --------------------------------------------------------------------------------------


def _clause_slots(node: Node) -> tuple[Slot, ...]:
    return slotlib.split(node, rulemap.CLAUSE_FIELDS, positional=("name",))


def read_rules(text: str, *, file: str = "", issues: list[Issue] | None = None) -> RuleSet:
    """A ``RuleSet`` from a rules file: rules in the closed grammar are lifted, the rest stays opaque."""
    found = issues if issues is not None else []
    document = parse_rules(text, file=file)
    info = inspect(document.node, file=file)
    found.extend(version_issues(info))
    future = info.status == VersionStatus.FUTURE
    version = str(info.version)
    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    total = sum(1 for item in document.items if isinstance(item, RuleItem))
    slots: list[Slot] = []
    rules: list[Rule] = []
    names: dict[str, int] = {}
    heads: dict[str, int] = {}
    index = 0
    for item in document.items:
        if isinstance(item, VersionItem):
            slots.append(Modeled("version"))
            continue
        if isinstance(item, CommentItem):
            slots.append(Opaque(item.text, version))
            continue
        head = item.node.name
        locator = f"/kicad_dru/{head}[{heads.get(head, 0)}]"
        heads[head] = heads.get(head, 0) + 1
        index += 1
        if future:
            slots.append(Opaque(item.text, version))
            continue
        lifted = "a comment line inside the rule" if item.has_comment else rulemap.lift_rule(item.node)
        if isinstance(lifted, str):
            slots.append(Opaque(item.text, version))
            found.append(
                Issue(KEPT_CODE, "info", f"line {item.line}: {lifted}; kept as written", where=locator)
            )
            continue
        repeat = names.get(lifted.name, 0)
        names[lifted.name] = repeat + 1
        native = f"rule:{lifted.name}" + (f":{repeat}" if repeat else "")
        rules.append(
            dataclasses.replace(
                lifted,
                id=derived_id("rul", "kicad", native),
                native_ids={"kicad": native},
                provenance=Provenance("kicad", file, sha256, locator, EVIDENCE),
                ext={"kicad": slotlib.to_ext(_clause_slots(item.node))},
                priority=total - index + 1,
            )
        )
        slots.append(Modeled("rules"))
    return RuleSet(
        id=derived_id("rst", "kicad", "rules"),
        provenance=Provenance("kicad", file, sha256, "/kicad_dru", EVIDENCE),
        ext={"kicad": slotlib.to_ext(slots)},
        rules=tuple(rules),
    )


# --- writing --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Written:
    """One item of the output: its text, and the slot it must read back as."""

    text: str
    slot: Slot
    rule: Rule | None = None


def _file_slots(ruleset: RuleSet) -> list[Slot]:
    bag = ruleset.ext.get("kicad")
    return list(slotlib.from_ext(bag)) if bag is not None else []


def _check_editable(slots: Sequence[Slot]) -> None:
    versions = [int(s.min_version) for s in slots if isinstance(s, Opaque) and s.min_version is not None]
    if versions:
        newest = max(versions)
        kind = FileKind.RULES
        require_editable(FormatInfo(kind, newest, major_for(kind, newest), classify(kind, newest)))


def _gate(text: str, target: int) -> tuple[list[Issue], list[Issue], list[Issue]]:
    """``(droppable errors, other errors, warnings)`` of one preserved rule for ``target``."""
    try:
        document = parse_rules(f"(version {RULES_VERSION})\n{text}")
    except FormatError as error:
        raise RulesSelfCheckError("parse", f"a preserved rule does not parse: {error.message}") from error
    droppable: list[Issue] = []
    errors: list[Issue] = []
    warnings: list[Issue] = []
    for issue in check_emittable(document.node, FileKind.RULES, target):
        if target < 10 and issue.code in REFUSED_FOR_9:
            droppable.append(dataclasses.replace(issue, severity="error"))
        elif issue.severity == "error":
            errors.append(issue)
        else:
            warnings.append(issue)
    return droppable, errors, warnings


def _rule_name(text: str) -> str:
    try:
        document = parse_rules(f"(version {RULES_VERSION})\n{text}")
    except FormatError:
        return "?"
    nodes = [i.node for i in document.items if isinstance(i, RuleItem)]
    atoms = nodes[0].atoms() if nodes else ()
    return atoms[0].value if atoms else (nodes[0].name if nodes else "?")


def rule_text(node: Node) -> str:
    """A rule list as Fenolite writes it: the name on the first line, one clause per line."""
    head = " ".join(a.text for a in node.atoms())
    clauses = "".join(f"\n\t{dumps(child, style='compact')}" for child in node.nodes())
    return f"({node.name} {head}{clauses}\n)"


def write_rules(
    ruleset: RuleSet,
    *,
    target: int = DEFAULT_TARGET,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
    downgrade: bool = False,
    edits: list[resolver.Edit] | None = None,
) -> str:
    """The text of a rules file for KiCad ``target``.0 (rules.md, "Writing and target gating").

    Warnings and infos are appended to ``issues``; errors raise ``RulesLossError``,
    ``FutureFormatError`` or ``RulesSelfCheckError``. Every rules file is version 1, so a rules file of
    KiCad 10 is written for 9 without ``downgrade`` too: a preserved rule that 9.0 cannot read is a loss
    that needs ``allow_lossy``. With ``downgrade`` (change c0162) the resolver's row of each such token
    decides (every rules row is ``design``) and the edits are appended to ``edits``, the rule's name as
    their locator.
    """
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    slots = _file_slots(ruleset)
    _check_editable(slots)
    written: list[_Written] = []
    errors: list[Issue] = []
    droppable: list[Issue] = []
    notes: list[Issue] = []

    def model(rule: Rule) -> None:
        if target not in rulemap.KIND_SUPPORT[rule.kind]:
            unchecked = f"KiCad {target}.0 does not check {rule.kind} rules"
            if allow_lossy:
                notes.append(
                    Issue(DROPPED_CODE, "warning", f"rule {rule.name!r} dropped: {unchecked}", where=rule.id)
                )
            else:
                majors = ", ".join(f"{m}.0" for m in sorted(rulemap.KIND_SUPPORT[rule.kind])) or "none"
                droppable.append(
                    Issue(
                        rulemap.KIND_UNCHECKED_CODE,
                        "error",
                        f"rule {rule.name!r}: {unchecked}; the kind is written for KiCad {majors}",
                        where=rule.id,
                        hint="build for a KiCad major that checks this kind, or pass --allow-lossy to "
                        "leave the rule out",
                    )
                )
            return
        bag = rule.ext.get("kicad")
        clause = slotlib.from_ext(bag) if bag is not None else ()
        nodes, found = rulemap.rule_nodes(rule, target=target, slots=clause)
        errors.extend(found)
        for node in nodes:
            written.append(_Written(rule_text(node), Modeled("rules"), rule))

    found_edits: list[resolver.Edit] = []
    last = max((i for i, s in enumerate(slots) if isinstance(s, Modeled) and s.field == "rules"), default=-1)
    taken = 0
    for i, slot in enumerate(slots):
        if isinstance(slot, Modeled):
            if slot.field == "rules":
                if taken < len(ruleset.rules):
                    model(ruleset.rules[taken])
                taken += 1
                if i == last:
                    for rule in ruleset.rules[taken:]:
                        model(rule)
                    taken = len(ruleset.rules)
            continue
        if _is_comment(slot.fragment):
            written.append(_Written(slot.fragment, slot))
            continue
        refused, other, warnings = _gate(slot.fragment, target)
        errors.extend(other)
        notes.extend(warnings)
        if refused and downgrade:
            changed = _resolved(refused, _rule_name(slot.fragment), found_edits)
            if changed:
                continue
        if refused and allow_lossy:
            name = _rule_name(slot.fragment)
            tokens = "; ".join(i.message for i in refused)
            notes.append(
                Issue(
                    DROPPED_CODE,
                    "warning",
                    f"rule {name!r} dropped: KiCad {target}.0 would drop the whole file ({tokens})",
                    where=refused[0].where,
                    hint=refused[0].hint,
                )
            )
            continue
        droppable.extend(refused)
        written.append(_Written(slot.fragment, slot))
    for rule in ruleset.rules[taken:]:
        model(rule)
    if errors or droppable:
        raise RulesLossError([*errors, *droppable], droppable=not errors)
    text = print_rules([VersionItem(RULES_VERSION, f"(version {RULES_VERSION})", 1)]) + "".join(
        w.text + "\n" for w in written
    )
    _self_check(text, written, target)
    if issues is not None:
        issues.extend(notes)
    if edits is not None:
        edits.extend(found_edits)
    return text


def _resolved(refused: Sequence[Issue], name: str, edits: list[resolver.Edit]) -> bool:
    """Record the resolver's edit of each too-new token of a preserved rule (``downgrade``); ``True`` when
    every one is a change (the rule is then left out without consent), ``False`` when one is a loss or has
    no row, which ``allow_lossy`` decides as before."""
    table = resolver.load()
    found: list[resolver.Edit] = []
    for issue in refused:
        row = table.rows.get(resolver.row_id(issue))
        if row is None:
            return False
        found.append(resolver.Edit(row.id, row.decide(()), f"rule {name}"))
    edits.extend(found)
    return all(edit.action in resolver.CHANGED for edit in found)


def _self_check(text: str, written: Sequence[_Written], target: int) -> None:
    """The four steps of rules.md: parse, emit check, lift and opaque order."""
    try:
        document = parse_rules(text)
    except FormatError as error:
        raise RulesSelfCheckError("parse", error.message) from error
    failed = [i for i in check_emittable(document.node, FileKind.RULES, target) if i.severity == "error"]
    if failed:
        raise RulesSelfCheckError("emit", failed[0].message, failed)
    try:
        again = read_rules(text)
    except FormatError as error:  # pragma: no cover - parse_rules passed above
        raise RulesSelfCheckError("parse", error.message) from error
    slots = [s for s in _file_slots(again) if not (isinstance(s, Modeled) and s.field == "version")]
    expected = [w.slot for w in written]
    lifted = iter(again.rules)
    for found, wanted, item in zip(slots, expected, written, strict=False):
        if isinstance(wanted, Opaque):
            if not isinstance(found, Opaque) or found.fragment != wanted.fragment:
                raise RulesSelfCheckError(
                    "opaque", f"a preserved item did not come back in place: {wanted.fragment[:60]!r}"
                )
            continue
        if not isinstance(found, Modeled):
            raise RulesSelfCheckError("lift", f"a written rule did not lift back: {item.text[:80]!r}")
        assert item.rule is not None
        rule = next(lifted)
        if _comparable(rule) != _comparable(_expected(item)):
            raise RulesSelfCheckError("lift", f"rule {rule.name!r} lifts back differently")
    if len(slots) != len(expected):
        raise RulesSelfCheckError("opaque", f"{len(expected)} items written, {len(slots)} read back")


def _expected(item: _Written) -> Rule:
    """The normal form of the model rule a written node stands for (one layer per node)."""
    assert item.rule is not None
    node_layers = _layers_of(item.text)
    name = _rule_name(item.text)
    return rulemap.normal_form(dataclasses.replace(item.rule, name=name, layers=node_layers))


def _layers_of(text: str) -> tuple[str, ...]:
    document = parse_rules(f"(version {RULES_VERSION})\n{text}")
    node = next(i.node for i in document.items if isinstance(i, RuleItem))
    layer = node.find("layer")
    return (layer.atoms()[0].value,) if layer is not None and layer.atoms() else ()


def _comparable(rule: Rule) -> tuple[object, ...]:
    return (
        rule.name,
        rule.kind,
        rule.selector_a,
        rule.selector_b,
        rule.layers,
        rule.min,
        rule.opt,
        rule.max,
        rule.severity,
    )


__all__ = [
    "EVIDENCE",
    "RULES_VERSION",
    "CommentItem",
    "RuleItem",
    "RulesDocument",
    "RulesItem",
    "RulesLossError",
    "RulesSelfCheckError",
    "VersionItem",
    "parse_rules",
    "print_rules",
    "read_rules",
    "rule_text",
    "write_rules",
]
