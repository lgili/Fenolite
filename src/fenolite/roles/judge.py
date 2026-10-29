# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The roles of a board and their judgement (change c0222; capability net-roles, "Role sources", and
verification-loop, "Roles judge injected into the stage"; ``docs/roles.md``).

``resolve`` gives every net its one role: the script's declaration (``declared``), else the role the user
confirmed (``confirmed``), else the inferred one, with ``roles.declared-differs`` when a declaration differs
from what it overrides and one ``roles.unconfirmed`` with the count of the inferred roles and groups. The
stated groups come first; an inferred group is kept unless the user rejected its name or a stated group of
its kind has its name or its pads.

``run`` resolves, measures (``roles.measure``) and checks (``roles.checks``) a board. ``judge`` is the
``RolesJudge`` that ``fenolite check`` passes to the stage ``roles.rules`` (``checks.roles``), as it passes
the plotter: ``checks`` imports neither ``roles`` nor ``analysis``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.analysis.shapes import LOOP_EVIDENCE
from fenolite.backends.base import BoardPad, ProjectSet
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Circuit
from fenolite.model.design import Design
from fenolite.model.rules import NetRole, PartClass, RoleSet
from fenolite.roles import checks, profile
from fenolite.roles.classify import Classified, classify
from fenolite.roles.codes import issue
from fenolite.roles.infer import Inferred, infer, with_currents
from fenolite.roles.measure import Inputs, Measured, RoleBoard, measure
from fenolite.roles.store import document_path, read_document

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-ROLE-INFER",))
NETWORK_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-AN-NETWORK",))


@dataclass(frozen=True, slots=True)
class Resolved:
    """The roles in force (with their currents), the inference they came from, the classes, the pads each
    inferred role read, and the issues of the resolution."""

    roles: RoleSet
    inferred: Inferred
    classes: Mapping[str, Classified]
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True, slots=True)
class Judged:
    """A judged board: the resolution, the measures, the findings, their summary and evidence."""

    resolved: Resolved
    measured: Measured
    issues: tuple[Issue, ...]
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    evidence: Evidence = EVIDENCE


def _same_pads(a: Sequence[str], b: Sequence[str]) -> bool:
    return set(a) == set(b)


def resolve(
    circuit: Circuit,
    *,
    pads: Sequence[BoardPad] | None,
    stored: RoleSet | None = None,
    declared: RoleSet | None = None,
    classes: Sequence[PartClass] = (),
    net_ties: Sequence[str] = (),
    requirements_current: Mapping[str, int] | None = None,
    currents: Mapping[str, int] | None = None,
) -> Resolved:
    """The roles of ``circuit``: ``declared`` (the script's), ``stored`` (confirmed by the user) and the
    inferred ones; ``classes`` are classes the user states besides the stored ones."""
    stated = [found for found in (declared, stored) if found is not None]
    limits = tuple({(f.key, f.net, f.kind): f for found in reversed(stated) for f in found.limits}.values())
    user_classes = {
        found.ref: found for found in (*(c for s in reversed(stated) for c in s.classes), *classes)
    }
    shunt = profile.resolve("shunt_max_mohm", limits).value or 0
    counts: dict[str, int] = {}
    for record in pads or ():
        counts[record.ref] = counts.get(record.ref, 0) + 1
    found_classes = classify(
        circuit, user=tuple(user_classes.values()), pad_counts=counts, net_ties=net_ties, shunt_max_mohm=shunt
    )
    positions = {f"{record.ref}-{record.number}": record.position for record in pads or ()}
    inferred = infer(circuit, found_classes, positions=positions)
    issues: list[Issue] = []
    declared_nets = {role.net: role for role in (declared.nets if declared is not None else ())}
    stored_nets = {role.net: role for role in (stored.nets if stored is not None else ())}
    inferred_nets = {role.net: role for role in inferred.roles.nets}
    nets: list[NetRole] = []
    taken_inferred = 0
    for name in sorted({net.name for net in circuit.nets} | set(declared_nets) | set(stored_nets)):
        mine = declared_nets.get(name)
        before = stored_nets.get(name) or inferred_nets.get(name)
        if mine is not None:
            nets.append(mine)
            if before is not None and before.kind != mine.kind:
                issues.append(
                    issue(
                        "roles.declared-differs",
                        f"the script declares {name} as {mine.kind}; it was {before.kind} ({before.source}"
                        + (f" by {before.rule}" if before.rule else "")
                        + "); the declaration wins",
                        where=name,
                    )
                )
            continue
        if name in stored_nets:
            nets.append(stored_nets[name])
            continue
        if name in inferred_nets:
            nets.append(inferred_nets[name])
            taken_inferred += 1
    rejected: set[str] = {name for found in stated for name in found.rejected}
    groups: dict[str, list[object]] = {"loops": [], "kelvins": [], "gates": []}
    for attr in groups:
        chosen: dict[str, object] = {}
        for found in stated:
            for group in getattr(found, attr):
                chosen.setdefault(group.name, group)
        for group in getattr(inferred.roles, attr):
            if group.name in rejected or group.name in chosen:
                continue
            if any(_same_pads(group.pads, other.pads) for other in chosen.values()):  # type: ignore[attr-defined]
                continue
            chosen[group.name] = group
            taken_inferred += 1
        groups[attr] = list(chosen.values())
    roles = RoleSet(
        nets=tuple(nets),
        loops=tuple(groups["loops"]),  # type: ignore[arg-type]
        kelvins=tuple(groups["kelvins"]),  # type: ignore[arg-type]
        gates=tuple(groups["gates"]),  # type: ignore[arg-type]
        limits=limits,
        classes=tuple(user_classes.values()),
        rejected=tuple(sorted(rejected)),
    )
    roles = with_currents(roles, requirements_current=requirements_current, given=currents)
    final = {role.net: role for role in roles.nets}
    for found in inferred.issues:
        role = final.get(found.where)
        if role is not None and role.source == "inferred":
            issues.append(found)
    if taken_inferred:
        issues.append(
            issue(
                "roles.unconfirmed",
                f"{taken_inferred} inferred role(s) and group(s) are not confirmed; their findings are at "
                "most "
                "warnings",
                where="roles",
                hint="review them with fenolite roles PATH, then --accept, --set or --reject",
            )
        )
    return Resolved(roles, inferred, found_classes, tuple(issues))


def requirement_currents(circuit: Circuit, requirements: object) -> dict[str, int]:
    """The current of each net that a ``[[current]]`` row of the requirements file gives."""
    from fenolite.analysis.requirements import Requirements

    if not isinstance(requirements, Requirements):
        return {}
    found: dict[str, int] = {}
    for net in circuit.nets:
        row = requirements.current_for(net, circuit)
        if row is not None:
            found[net.name] = row.milliamps
    return found


def net_tie_parts(design: Design) -> tuple[str, ...]:
    """The references of the parts whose footprint holds a net-tie group."""
    board = design.board
    if board is None:
        return ()
    refs = {component.id: component.ref for component in design.circuit.components}
    found = [refs.get(fp.component_id or "", "") for fp in board.footprints if fp.net_ties]
    return tuple(sorted(ref for ref in found if ref))


def run(
    design: Design,
    pads: Sequence[BoardPad],
    *,
    circuit: Circuit | None = None,
    stored: RoleSet | None = None,
    declared: RoleSet | None = None,
    classes: Sequence[PartClass] = (),
    currents: Mapping[str, int] | None = None,
    inputs: Inputs | None = None,
    check: bool = True,
) -> Judged:
    """Resolve, and with ``check`` measure and judge, the roles of the board ``design``. ``circuit`` is the
    circuit to infer from (the ``.fenolite/`` model's of a built project, which holds the pin names), else
    the board's."""
    inputs = inputs if inputs is not None else Inputs()
    source = circuit if circuit is not None else design.circuit
    resolved = resolve(
        source,
        pads=pads,
        stored=stored,
        declared=declared,
        classes=classes,
        net_ties=net_tie_parts(design),
        requirements_current=requirement_currents(source, inputs.requirements),
        currents=currents,
    )
    if not check:
        return Judged(resolved, Measured(), resolved.issues, {}, EVIDENCE)
    board = RoleBoard(design, tuple(pads), resolved.roles, resolved.classes)
    measured = measure(board, inputs)
    found = checks.judge(board, measured)
    issues = tuple(dict.fromkeys((*resolved.issues, *found, *measured.issues)))
    extra = [LOOP_EVIDENCE] if "loop_areas" in measured.analyses else []
    if "path_network" in measured.analyses:
        extra.append(NETWORK_EVIDENCE)
    evidence = Evidence.combine(
        Evidence(Level.INFERRED, hypotheses=checks.hypotheses(measured)), *measured.evidences, *extra
    )
    return Judged(resolved, measured, issues, checks.summary(issues, measured, resolved.roles), evidence)


def split_roles(roles: RoleSet | None) -> tuple[RoleSet | None, RoleSet | None]:
    """``(declared, confirmed)``: the roles of a ``RuleSet`` of a built project, by source."""
    if roles is None:
        return None, None
    declared = RoleSet(
        nets=tuple(role for role in roles.nets if role.source == "declared"),
        loops=tuple(g for g in roles.loops if g.origin == "declared"),
        kelvins=tuple(g for g in roles.kelvins if g.origin == "declared"),
        gates=tuple(g for g in roles.gates if g.origin == "declared"),
        limits=roles.limits,
        classes=roles.classes,
    )
    confirmed = RoleSet(
        nets=tuple(role for role in roles.nets if role.source == "confirmed"),
        loops=tuple(g for g in roles.loops if g.origin == "confirmed"),
        kelvins=tuple(g for g in roles.kelvins if g.origin == "confirmed"),
        gates=tuple(g for g in roles.gates if g.origin == "confirmed"),
        rejected=roles.rejected,
    )
    return declared or None, confirmed or None


def judge(
    design: Design, model: Design | None, project: ProjectSet, pads: Sequence[BoardPad] | None
) -> tuple[tuple[Issue, ...], Mapping[str, object], Evidence]:
    """The ``RolesJudge`` of the stage ``roles.rules``: the stored roles of the board (``rules.json`` of the
    ``.fenolite/`` model of a built project, else the role document beside the board), judged with no option
    given."""
    declared = confirmed = None
    if model is not None and model.rules is not None:
        declared, confirmed = split_roles(model.rules.roles)
    else:
        beside = document_path(project.root / project.board)
        if beside.is_file():
            confirmed = read_document(beside)  # a malformed document is FormatError, which the stage reports
    judged = run(
        design,
        pads or (),
        circuit=model.circuit if model is not None else None,
        stored=confirmed,
        declared=declared,
    )
    return judged.issues, judged.summary, judged.evidence


__all__ = [
    "EVIDENCE",
    "Judged",
    "Resolved",
    "judge",
    "net_tie_parts",
    "requirement_currents",
    "resolve",
    "run",
    "split_roles",
]
