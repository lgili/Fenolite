# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Traced native project rule context, distinct from canonical Design fields (c0352)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import cast

from fenolite.api.sides import ReadSide
from fenolite.backends.kicad import _json, pro
from fenolite.backends.kicad.derived_teardrops import native_net
from fenolite.backends.kicad.lowering import MINIMUM_KEYS, NETCLASS_KEYS
from fenolite.backends.kicad.sexpr import AtomKind, Node, parse_bytes
from fenolite.checks.assignment_compare import board_netlist, net_names
from fenolite.checks.equivalence.exclusions import Rule, apply_rules
from fenolite.checks.equivalence.model import Difference, EquivalenceReport, LevelResult
from fenolite.core.errors import FormatError, Issue
from fenolite.model.design import Design


def bindings(design: Design) -> dict[str, tuple[str, ...]]:
    netlist, _ = board_netlist(design)
    members: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, str] = {}
    for assignment in netlist.assignments:
        if assignment.element in seen:
            if seen[assignment.element] != assignment.net:
                raise ValueError("ambiguous numbered-pad binding")
            continue
        seen[assignment.element] = assignment.net
        members[assignment.net].append(assignment.element)
    names = net_names(design)
    result: dict[str, tuple[str, ...]] = {}
    for net, elements in members.items():
        name = names.get(net)
        if name is None:
            continue
        if name in result:
            raise ValueError("ambiguous native net name")
        result[name] = tuple(sorted(elements))
    return result


def raw_bindings(root: Node, expected: frozenset[tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Bind complete electrical terminal signatures; retain all physical copies outside this set view."""
    members: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, str] = {}
    identities: dict[str, tuple[str, str]] = {}
    signatures: dict[str, tuple[tuple[str, str], ...]] = {}
    for footprint in root.nodes("footprint"):
        terminals: dict[str, str] = {}
        for pad in footprint.nodes("pad"):
            atoms = pad.atoms()
            if not atoms or atoms[0].kind != AtomKind.STRING:
                raise ValueError("native pad number malformed")
            if not atoms[0].value or not pad.nodes("net"):
                continue
            net = native_net(pad, root)
            if not net:
                continue
            number = atoms[0].value
            if number in terminals and terminals[number] != net:
                raise ValueError("native numbered-pad identity ambiguous")
            terminals[number] = net
        if not terminals:
            continue  # No numbered electrical terminal to bind; no physical object is removed.
        references = [
            p.atoms()[1].value
            for p in footprint.nodes("property")
            if len(p.atoms()) >= 2 and p.atoms()[0].value == "Reference"
        ]
        references += [
            p.atoms()[1].value
            for p in footprint.nodes("fp_text")
            if len(p.atoms()) >= 2 and p.atoms()[0].value == "reference"
        ]
        if len(references) != 1 or not references[0]:
            raise ValueError("native electrical footprint has no unique reference")
        reference = references[0]
        signature = tuple(sorted(terminals.items()))
        if reference in signatures and signatures[reference] != signature:
            raise ValueError("native repeated reference has ambiguous terminal decomposition")
        signatures[reference] = signature
        for number, net in signature:
            element = reference + "-" + number
            identity = (reference, number)
            if element in identities and identities[element] != identity:
                raise ValueError("native terminal spelling is ambiguous")
            identities[element] = identity
            if element in seen:
                if seen[element] != net:
                    raise ValueError("native numbered-pad identity ambiguous")
                continue
            seen[element] = net
            members[net].append(element)
    result = {name: tuple(sorted(elements)) for name, elements in members.items()}
    if frozenset(result.values()) != expected:
        raise ValueError("native named-pad partitions changed")
    return result


@dataclass(frozen=True)
class NativeContext:
    floors: Mapping[str, int]
    classes: Mapping[str, Mapping[str, int | None]]
    members: Mapping[str, tuple[tuple[str, ...], ...]]
    files: Mapping[str, str]
    major: int


def context(side: ReadSide) -> NativeContext | None:
    """Consume only previously declared/read exact input bytes; never discover another file."""
    projects = [(path, digest) for path, digest in side.source_files if path.suffix.lower() == ".kicad_pro"]
    boards = [(path, digest) for path, digest in side.source_files if path.suffix.lower() == ".kicad_pcb"]
    if not projects:
        return None
    if len(projects) != 1 or len(boards) != 1:
        raise FormatError("native rules require one traced project and board")
    held: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for path, digest in (*projects, *boards):
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise FormatError("native rules input changed or is unreadable", file=path.name) from error
        if hashlib.sha256(raw).hexdigest() != digest:
            raise FormatError("native rules input changed since it was read", file=path.name)
        if path.suffix.lower() in held:
            raise FormatError("ambiguous native rule input", file=path.name)
        held[path.suffix.lower()] = raw
        digests[path.name] = digest
    project_path = projects[0][0]
    issues: list[Issue] = []
    info = pro.read_project(held[".kicad_pro"].decode("utf-8"), file=project_path.name, issues=issues)
    if (
        info.major not in (9, 10)
        or (info.meta_version, info.net_settings_version) not in pro.PROJECT_VERSIONS.values()
    ):
        raise FormatError(
            "native rule comparison requires supported writable project versions", file=project_path.name
        )
    floors = pro.project_minimums(info.data, issues=issues)
    keys = tuple(MINIMUM_KEYS[info.major].values())
    if any(key not in floors or floors[key] < 0 for key in keys):
        raise FormatError("native rule floor is missing, malformed or inexact", file=project_path.name)
    names = [cls.name for cls in info.classes]
    if len(set(names)) != len(names) or names.count("Default") != 1:
        raise FormatError("native classes require unique names and one Default", file=project_path.name)
    raw_classes = cast(list[_json.JsonObject], info.data["net_settings"]["classes"])
    for index, entry in enumerate(raw_classes):
        for key in NETCLASS_KEYS.values():
            if (
                key in entry
                and entry[key] is not None
                and (
                    not isinstance(entry[key], _json.JsonNumber)
                    or cast(_json.JsonNumber, entry[key]).text.startswith("-")
                )
            ):
                raise FormatError(
                    "native class field is malformed or unsupported",
                    file=project_path.name,
                    locator=f"/net_settings/classes/{index}/{key}",
                )
    try:
        canonical = bindings(side.design)
    except ValueError as error:
        raise FormatError(
            f"native canonical binding is ambiguous: {error}", file=project_path.name
        ) from error
    by_partition = {partition: name for name, partition in canonical.items()}
    if len(by_partition) != len(canonical):
        raise FormatError("native canonical net partitions are ambiguous", file=project_path.name)
    try:
        raw_partitions = raw_bindings(parse_bytes(held[".kicad_pcb"]), frozenset(canonical.values()))
    except ValueError as error:
        raise FormatError(f"native rule binding is ambiguous: {error}", file=project_path.name) from error
    raw_names = {by_partition[partition]: name for name, partition in raw_partitions.items()}
    if any(net.name and net.name not in raw_names for net in side.design.circuit.nets):
        raise FormatError("native rule membership has an unbound net", file=project_path.name)
    clone = replace(
        side.design,
        circuit=replace(
            side.design.circuit,
            nets=tuple(
                replace(net, name=raw_names.get(net.name, net.name)) for net in side.design.circuit.nets
            ),
        ),
    )
    applied = pro.apply_project(clone, info, issues=issues)
    relevant = [issue for issue in issues if issue.where.startswith(("/net_settings/", "/net/"))]
    if relevant:
        raise FormatError(
            f"native class semantics are not fully represented: {relevant[0].message}",
            file=project_path.name,
            locator=relevant[0].where,
        )
    values: dict[str, dict[str, int | None]] = {}
    for cls in applied.circuit.netclasses:
        values[cls.name] = {field: cast(int | None, getattr(cls, field)) for field in NETCLASS_KEYS}
    by_id = {cls.id: cls.name for cls in applied.circuit.netclasses}
    members: dict[str, list[tuple[str, ...]]] = {name: [] for name in values}
    for net in applied.circuit.nets:
        if not net.name:
            continue
        name = by_id[net.netclass_id] if net.netclass_id is not None else "Default"
        members[name].append(raw_partitions[net.name])
    return NativeContext(
        {key: floors[key] for key in keys},
        values,
        {name: tuple(sorted(parts)) for name, parts in members.items()},
        digests,
        info.major,
    )


def compare(a: NativeContext, b: NativeContext) -> LevelResult:
    """Exact supported floor values, represented class fields and verified effective membership."""
    differences: list[Difference] = []
    judged: list[str] = []
    unjudged: list[str] = []
    for key in sorted(a.floors):
        judged.append(key)
        if a.floors[key] != b.floors[key]:
            differences.append(
                Difference(6, "rule-field", "native-project", key, str(a.floors[key]), str(b.floors[key]))
            )
    for name in sorted(set(a.classes) | set(b.classes)):
        where = "native-project:netclass:" + name
        if name not in a.classes or name not in b.classes:
            differences.append(
                Difference(
                    6,
                    "netclass-missing",
                    where,
                    "name",
                    name if name in a.classes else "",
                    name if name in b.classes else "",
                )
            )
            continue
        for key in NETCLASS_KEYS:
            av, bv = a.classes[name][key], b.classes[name][key]
            label = "netclass." + name + "." + key
            (unjudged if av is None and bv is None else judged).append(label)
            if av != bv:
                differences.append(
                    Difference(
                        6,
                        "netclass-field",
                        where,
                        key,
                        str(av) if av is not None else "",
                        str(bv) if bv is not None else "",
                    )
                )
        judged.append("netclass." + name + ".numbered-pad-partition-membership")
        if a.members[name] != b.members[name]:
            differences.append(
                Difference(6, "netclass-members", where, "nets", repr(a.members[name]), repr(b.members[name]))
            )
    summary = {
        "native_project_rules": {
            "scope": "five-supported-floors-and-represented-netclass-fields-and-verified-membership",
            "judged_keys": judged,
            "unjudged_absent_fields": unjudged,
            "judged_count": len(judged),
            "source_major": a.major,
            "generated_major": b.major,
            "a_read_files": dict(a.files),
            "b_read_files": dict(b.files),
            "unjudged": "custom DRU rules and unrelated native properties",
        }
    }
    return LevelResult(
        6, len(judged), tuple(sorted(differences, key=lambda d: (d.where, d.kind, d.field))), summary=summary
    )


def augment(
    report: EquivalenceReport, a: ReadSide, b: ReadSide, rules: tuple[Rule, ...] = ()
) -> EquivalenceReport:
    """Append scoped native evidence/differences without replacing canonical comparisons."""
    if not any(level.level == 6 for level in report.levels):
        return report
    ca, cb = context(a), context(b)
    if ca is None and cb is None:
        return report
    if ca is None or cb is None:
        # Canonical Design sides never acquire an undeclared native floor property.
        if a.backend != "kicad" or b.backend != "kicad":
            return report
        raise FormatError("native project context is missing on one side; complete native rules are unjudged")
    extra = apply_rules(compare(ca, cb), rules)
    return replace(
        report,
        levels=tuple(
            replace(
                level,
                compared=level.compared + extra.compared,
                differences=tuple(
                    sorted((*level.differences, *extra.differences), key=lambda d: (d.where, d.kind, d.field))
                ),
                excluded=(*level.excluded, *extra.excluded),
                summary={**level.summary, **extra.summary},
            )
            if level.level == 6
            else level
            for level in report.levels
        ),
    )
