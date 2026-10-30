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
from fenolite.checks.circuit.rails import EVIDENCE, View, circuit_evidence, level_of, rule_issues
from fenolite.checks.circuit.ratings import DEVICE_PROPERTY, Judged, judge_parts
from fenolite.checks.circuit.values import Values, ground_nets, part_classes, resolve
from fenolite.checks.codes import issue
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level, min_level
from fenolite.core.requirement_table import Corner, RequirementRow, table_json
from fenolite.model import canonical
from fenolite.model.design import Design
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
    entities: tuple[tuple[str, ...], ...] = ()
    """Aligned with ``issues``: the model ids (components, nets) of the row each finding comes from, empty
    for a finding of no row (change c0256, finding subjects)."""


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
    view = View(design.circuit, contracts.rig if contracts is not None else ())
    rails = rule_issues(view)
    values = resolve(design, view, contracts, currents=currents)
    found_classes = part_classes(design, classes)
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


def judge_circuit(
    design: Design,
    *,
    devices: Mapping[str, DeviceDef] | None = None,
    classes: Mapping[str, str] | None = None,
    currents: Mapping[str, tuple[Fraction, str]] | None = None,
) -> CircuitResult:
    """The rail rules (c0252) and the contracts (c0253) of ``design``, with the device records and classes
    the command resolved and, for ``fenolite roles --check``, the currents of ``[[current]]`` and
    ``--current`` by net name."""
    contracts = design.rules.contracts if design.rules is not None else None
    main = _evaluate(design, contracts, devices, classes, currents)
    view = main.view
    found: list[Issue] = [*main.rails, *main.values.issues, *main.changed]
    corner_set = rig_corners.corners(contracts)
    by_corner: list[tuple[str, dict[str, Judged]]] = []
    if corner_set and contracts is not None and any(row.rigs for row in main.rows):
        for corner in corner_set:
            evaluated = _evaluate(design, rig_corners.pinned(contracts, corner), devices, classes, currents)
            by_corner.append((rig_corners.name(corner), {row.id: row for row in evaluated.rows}))
    strict = contracts is not None and contracts.unknown == "warning"
    rows: list[RequirementRow] = []
    unknown_rows: list[Judged] = []
    entities: dict[int, tuple[str, ...]] = {}
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
            found.append(issue(row.check, text, severity=severity, where=row.part or row.id))  # type: ignore[arg-type]
            entities[len(found) - 1] = row.entities
    if unknown_rows:
        if strict:
            for row in unknown_rows:
                entities[len(found)] = row.entities
                found.append(
                    issue(
                        "circuit.value-unknown",
                        f"{row.id} is not judged: {row.missing or 'an input is not stated'}",
                        severity="warning",
                        where=row.part or row.id,
                        hint="state the missing value: a rig supply, a rail voltage, a role current "
                        "or a class",
                    )
                )
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
    order = sorted(range(len(found)), key=lambda k: (found[k].code, found[k].where, found[k].message))
    return CircuitResult(
        tuple(found[k] for k in order),
        tuple(rows),
        evidence,
        summary,
        tuple(entities.get(k, ()) for k in order),
    )


def circuit_issues(
    design: Design,
    *,
    devices: Mapping[str, DeviceDef] | None = None,
    classes: Mapping[str, str] | None = None,
) -> tuple[Issue, ...]:
    """Every finding of the circuit rules on ``design`` (c0252's rails and c0253's contracts), sorted by code,
    place and message; ``devices`` and ``classes`` are what the command resolved (``fenolite build`` and
    ``fenolite check`` pass them, so both give the same ``circuit.*`` codes on one model)."""
    return judge_circuit(design, devices=devices, classes=classes).issues


__all__ = ["HYPOTHESIS", "CircuitResult", "circuit_issues", "device_digest", "has_contracts", "judge_circuit"]
