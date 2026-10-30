# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The contract half of the stage ``circuit.rules`` and its requirement table (change c0253; capability
electrical-contracts, "Contract judge on the model", "Device records of the judgement", "Contract
severities", "Strictness of unknown rows" and "Contract evidence"; ``docs/contracts.md``).

``judge_circuit`` runs c0252's rail rules and this change's contracts on one model with the device records
(``devices``, by device id) and part classes (``classes``, by component id) that the command resolved, and
returns the findings, the requirement rows, the evidence and the summary. The judge runs no tool, reads no
board and gives the same result for the same inputs.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction

from fenolite.checks.circuit import corners as rig_corners
from fenolite.checks.circuit.expect import Evaluator, judge_expectation
from fenolite.checks.circuit.propagate import as_value, links, propagate
from fenolite.checks.circuit.rails import EVIDENCE, View, circuit_evidence, level_of, rule_issues
from fenolite.checks.circuit.ratings import DEVICE_PROPERTY, Judged, judge_parts
from fenolite.checks.circuit.values import Values, ground_nets, part_classes, resolve
from fenolite.checks.codes import issue
from fenolite.checks.waivers import EXPIRED, CircuitWaived, Keyed, apply_circuit_waivers
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level, min_level
from fenolite.core.requirement_table import Corner, RequirementRow, row_digest, table_json
from fenolite.model import canonical
from fenolite.model.design import Design
from fenolite.model.findings import Waiver
from fenolite.model.library import DeviceDef
from fenolite.model.rules import ContractSet

DEVICE_SHA256_PROPERTY = "fenolite.device.sha256"
HYPOTHESIS = "H-G-CIRCUIT-EXAMPLE"
"""The hypothesis of the contract judgement (``docs/hypotheses.md``)."""
LISTED = 8
"""The most rows or parts a count finding names before it says how many more."""
ERRORS: frozenset[str] = frozenset(
    {
        "circuit.rating-voltage",
        "circuit.rating-current",
        "circuit.rating-power",
        "circuit.rating-temperature",
        "circuit.operating-range",
        "circuit.expect-failed",
    }
)


def device_digest(device: DeviceDef) -> str:
    """The SHA-256 a build records in ``fenolite.device.sha256``: of the canonical record without its
    provenance (``fenolite.catalog.devices.device_digest``; ``checks`` does not import the catalog, and a test
    keeps the two equal)."""
    return hashlib.sha256(canonical.dumps(replace(device, provenance=None)).encode("utf-8")).hexdigest()


def has_contracts(design: Design) -> bool:
    """Whether the model holds anything for the contract half: a component with a ``fenolite.device``
    property, an expectation or a rig element."""
    contracts = design.rules.contracts if design.rules is not None else None
    if contracts is not None and (contracts.expects or contracts.rig):
        return True
    return any(DEVICE_PROPERTY in component.properties for component in design.circuit.components)


@dataclass(frozen=True, slots=True)
class CircuitResult:
    """One judgement of the stage ``circuit.rules``: the findings (sorted), the requirement rows, the
    evidence and the summary entries of the contract half."""

    issues: tuple[Issue, ...]
    rows: tuple[RequirementRow, ...]
    evidence: Evidence
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    waived: CircuitWaived | None = None
    """What the circuit waivers did (change c0274): their outcome and their ``check.waiver-*`` warnings,
    which the stage reports and the build does not."""


@dataclass(slots=True)
class _Pass:
    """The rows and findings of one evaluation (the full ranges, or one corner)."""

    rails: list[Issue]
    view: View
    values: Values
    rows: list[Judged]
    missing_parts: list[str]
    changed: list[Issue]


def _ground(design: Design) -> str | None:
    grounds = ground_nets(design)
    return next(iter(grounds)) if len(grounds) == 1 else None


def _evaluate(
    design: Design,
    contracts: ContractSet | None,
    devices: Mapping[str, DeviceDef] | None,
    classes: Mapping[str, str] | None,
    currents: Mapping[str, tuple[Fraction, str]] | None,
) -> _Pass:
    rig = contracts.rig if contracts is not None else ()
    view = View(design.circuit, rig)
    found_classes = part_classes(design, classes)
    spread = None
    if contracts is None or contracts.propagate:
        stated_view = View(design.circuit, rig)
        rule_issues(stated_view)  # sets the rails' own voltages: the stated ones
        stated = resolve(design, stated_view, contracts, currents=currents)
        spread = propagate(stated_view, stated.voltage, links(design, stated_view, found_classes))
        view.propagated = dict(spread.values)
    rails = rule_issues(view)
    values = resolve(design, view, contracts, currents=currents)
    if spread is not None:
        for net, found in spread.values.items():
            values.voltage.setdefault(net, as_value(found))
        values.issues += spread.issues
    parts: list[tuple[object, DeviceDef, str | None]] = []
    missing: list[str] = []
    changed: list[Issue] = []
    for component in sorted(design.circuit.components, key=lambda c: c.ref):
        device_id = component.properties.get(DEVICE_PROPERTY)
        if not device_id:
            continue
        record = None if devices is None else devices.get(device_id)
        if record is None:
            missing.append(component.ref)
            continue
        recorded = component.properties.get(DEVICE_SHA256_PROPERTY, "")
        current = device_digest(record)
        if recorded and recorded != current:
            changed.append(
                issue(
                    "circuit.device-changed",
                    f"{component.ref}: the device {device_id} is now {current[:12]}, not the {recorded[:12]} "
                    "the "
                    "build recorded; the current record is judged",
                    where=component.ref,
                    hint="rebuild the design so the model records the current device",
                )
            )
        parts.append((component, record, found_classes.get(component.id)))
    rows = judge_parts(view, values, contracts, parts, _ground(design))  # type: ignore[arg-type]
    evaluator = Evaluator(view, values, devices)
    for expectation in contracts.expects if contracts is not None else ():
        rows.append(judge_expectation(evaluator, expectation))
    return _Pass(rails, view, values, rows, missing, changed)


def _listed(items: Sequence[str]) -> str:
    shown = ", ".join(items[:LISTED])
    return shown + (f" and {len(items) - LISTED} more" if len(items) > LISTED else "")


def _severity(row: Judged, strict: bool) -> str | None:
    if row.status == "fail" and row.check in ERRORS:
        return "error"
    if row.status == "unsure" or (row.status == "unknown" and row.check == "circuit.expect-unknown"):
        return "warning"
    if row.status == "unknown" and strict:
        return "warning"
    return None


def finding_digest(found: Issue) -> str:
    """The digest of a circuit finding that no requirement row gives (change c0274): of its code, place and
    message, which name every number it judged."""
    return row_digest({"code": found.code, "where": found.where, "message": found.message})


def _keyed(found: Sequence[Issue], links: Mapping[int, tuple[Issue, RequirementRow]]) -> list[Keyed]:
    """Each finding with its item and digest (a row's, else its own), its hint ending ``digest <digest>``
    when it is an error or a warning: what a waiver copies (change c0274)."""
    keyed: list[Keyed] = []
    for item in found:
        link = links.get(id(item))
        row = link[1] if link is not None and link[0] is item else None
        name, digest = (row.item, row.digest) if row is not None else (item.where, finding_digest(item))
        if item.severity in ("error", "warning"):
            hint = f"{item.hint}; digest {digest}" if item.hint else f"digest {digest}"
            item = replace(item, hint=hint)
        keyed.append(Keyed(item, name, digest, row.id if row is not None else ""))
    return keyed


def judge_circuit(
    design: Design,
    *,
    devices: Mapping[str, DeviceDef] | None = None,
    classes: Mapping[str, str] | None = None,
    currents: Mapping[str, tuple[Fraction, str]] | None = None,
    waivers: Sequence[Waiver] = (),
) -> CircuitResult:
    """The rail rules (c0252) and the contracts (c0253) of ``design``, with the device records and classes
    the command resolved and, for ``fenolite roles --check``, the currents of ``[[current]]`` and
    ``--current`` by net name. The ``circuit.*`` waivers of ``waivers`` accept their findings (change
    c0274): a waived finding is ``info`` and its row names the waiver."""
    contracts = design.rules.contracts if design.rules is not None else None
    main = _evaluate(design, contracts, devices, classes, currents)
    view = main.view
    found: list[Issue] = [*main.rails, *main.values.issues, *main.changed]
    links: dict[int, tuple[Issue, RequirementRow]] = dict(view.links)
    corner_set = rig_corners.corners(contracts)
    by_corner: list[tuple[str, dict[str, Judged]]] = []
    if corner_set and contracts is not None and any(row.rigs for row in main.rows):
        for corner in corner_set:
            evaluated = _evaluate(design, rig_corners.pinned(contracts, corner), devices, classes, currents)
            by_corner.append((rig_corners.name(corner), {row.id: row for row in evaluated.rows}))
    strict = contracts is not None and contracts.unknown == "warning"
    rows: list[RequirementRow] = []
    unknown_rows: list[Judged] = []
    no_rating: dict[str, None] = dict.fromkeys(main.missing_parts)
    policy: list[str] = []
    levels: list[Level] = []
    for row in main.rows:
        entries: list[Corner] = []
        if row.rigs:
            for label, evaluated in by_corner:
                other = evaluated.get(row.id)
                status = other.status if other is not None else "unknown"
                text = other.value.text if other is not None and other.value is not None else ""
                entries.append(Corner(label, status, text))
        severity = _severity(row, strict)
        if row.no_rating:
            no_rating.setdefault(row.part)
        elif row.status == "unknown" and row.check != "circuit.expect-unknown":
            unknown_rows.append(row)
        if row.policy:
            policy.append(row.id)
        if row.device_evidence and not row.no_rating:
            levels.append(level_of(row.device_evidence))
        rows.append(
            RequirementRow(
                row.id,
                row.check,
                row.subject,
                row.quantity,
                row.unit,
                row.value,
                row.limit,
                row.status,
                severity if not row.no_rating else ("warning" if strict else None),
                row.entities,
                tuple(entries),
                row.missing,
            )  # fmt: skip
        )
        if severity is not None and (
            row.status in ("fail", "unsure") or row.check == "circuit.expect-unknown"
        ):
            failing = [c for c in entries if c.status == "fail"]
            text = row.text
            if failing:
                text += "; fails at " + "; ".join(
                    f"{c.corner}: {c.text} over {row.limit.text}" for c in failing
                )
            made = issue(row.check, text, severity=severity, where=row.part or row.id)  # type: ignore[arg-type]
            links[id(made)] = (made, rows[-1])
            found.append(made)
    if unknown_rows:
        if strict:
            found += [
                issue(
                    "circuit.value-unknown",
                    f"{row.id} is not judged: {row.missing or 'an input is not stated'}",
                    severity="warning",
                    where=row.part or row.id,
                    hint="state the missing value: a rig supply, a rail voltage, a role current or a class",
                )
                for row in unknown_rows
            ]
        else:
            found.append(
                issue(
                    "circuit.value-unknown",
                    f"{len(unknown_rows)} contract row(s) are not judged for a missing input: "
                    + _listed([f"{row.id} ({row.missing})" for row in unknown_rows]),
                    severity="info",
                    where="contracts",
                    hint="state the voltages and currents (design.rig, design.rail, design.net_role); "
                    "design.contracts(unknown='warning') makes each row a warning",
                )
            )
    if no_rating:
        names = list(no_rating)
        if strict:
            found += [
                issue(
                    "circuit.rating-missing",
                    f"{name}: no device record or no rating for a check that applies",
                    severity="warning",
                    where=name,
                    hint="add the rating to the device record (its datasheet value)",
                )
                for name in names
            ]
        else:
            found.append(
                issue(
                    "circuit.rating-missing",
                    f"{len(names)} part(s) lack a device record or a rating for a check that applies: "
                    + _listed(names),
                    severity="info",
                    where="contracts",
                    hint="add the ratings to the device records",
                )
            )
    if policy:
        found.append(
            issue(
                "circuit.policy-missing",
                f"{len(policy)} rating(s) judged at 100 % because no derating rule covers them: "
                + _listed(policy),
                where="contracts",
                hint="state your derating policy with design.derating(...) and ratio(); Fenolite ships none",
            )
        )
    rows += view.rows
    ran = has_contracts(design)
    hypotheses = (*EVIDENCE.hypotheses, HYPOTHESIS) if ran else EVIDENCE.hypotheses
    base = circuit_evidence(design)
    evidence = Evidence(min_level(base.level, *levels), hypotheses=hypotheses)
    summary: dict[str, object] = {
        "requirements": table_json(rows),
        "corners": rig_corners.TOO_MANY if corner_set is None else len(corner_set),
    }
    waived = apply_circuit_waivers(waivers, _keyed(found, links))
    if waived.rows:
        rows = [replace(r, waiver=waived.rows[r.id]) if r.id in waived.rows else r for r in rows]
        summary["requirements"] = table_json(rows)
    return CircuitResult(
        tuple(sorted(waived.issues, key=lambda i: (i.code, i.where, i.message))),
        tuple(rows),
        evidence,
        summary,
        waived,
    )


def circuit_issues(
    design: Design,
    *,
    devices: Mapping[str, DeviceDef] | None = None,
    classes: Mapping[str, str] | None = None,
    waivers: Sequence[Waiver] = (),
) -> tuple[Issue, ...]:
    """Every finding of the circuit rules on ``design`` (c0252's rails and c0253's contracts), sorted by code,
    place and message; ``devices`` and ``classes`` are what the command resolved (``fenolite build`` and
    ``fenolite check`` pass them, so both give the same ``circuit.*`` codes on one model). The ``circuit.*``
    waivers of ``waivers`` (the design's) accept their findings as the stage does, and a waiver whose digest
    changed adds its ``check.waiver-expired`` (change c0274)."""
    result = judge_circuit(design, devices=devices, classes=classes, waivers=waivers)
    expired = () if result.waived is None else tuple(i for i in result.waived.reports if i.code == EXPIRED)
    return (*result.issues, *expired)


__all__ = [
    "HYPOTHESIS",
    "CircuitResult",
    "circuit_issues",
    "device_digest",
    "finding_digest",
    "has_contracts",
    "judge_circuit",
]
