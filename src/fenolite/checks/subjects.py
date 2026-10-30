# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Model identities attached to findings (c0256, verification-loop: Finding subjects)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.core.errors import Issue
from fenolite.model.design import Design

SUBJECT_KINDS: tuple[str, ...] = (
    "component",
    "pin",
    "pad",
    "net",
    "netclass",
    "interface",
    "track",
    "arc",
    "via",
    "zone",
    "rule_area",
    "rule",
)


@dataclass(frozen=True, slots=True)
class Subject:
    """A model entity and its human-readable name; never a generated replacement identity."""

    kind: str
    id: str
    name: str

    def __post_init__(self) -> None:
        if self.kind not in SUBJECT_KINDS:
            raise ValueError(f"unknown subject kind {self.kind!r}")
        if not self.id:
            raise ValueError("a subject needs a model id")

    def to_json(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id, "name": self.name}


__all__ = ["SUBJECT_KINDS", "Subject"]


def for_issues(design: Design, issues: Sequence[Issue]) -> tuple[tuple[Subject, ...], ...]:
    """Resolve stage-owned locations against the actual model, without inventing identities."""
    if not issues:
        return ()
    refs = {c.id: c.ref for c in design.circuit.components}
    names: dict[str, Subject] = {}
    for part in design.circuit.components:
        names[part.ref] = Subject("component", part.id, part.ref)
        if part.path:
            names[part.path] = names[part.ref]
        for pin in part.pins:
            name = f"{part.ref}-{pin.number}"
            names[name] = Subject("pin", pin.id, name)
    for net in design.circuit.nets:
        names[net.name] = Subject("net", net.id, net.name)
    if design.board is not None:
        for fp in design.board.footprints:
            for pad in fp.pads:
                ref = refs.get(fp.component_id, fp.id)
                name = f"{ref}-{pad.number}"
                names[name] = Subject("pad", pad.id, name)
        for attr, kind in (("tracks", "track"), ("arcs", "arc"), ("vias", "via"), ("zones", "zone")):
            for entity in getattr(design.board, attr):
                subject = Subject(
                    kind,
                    entity.id,
                    entity.provenance.locator
                    if entity.provenance and entity.provenance.locator
                    else entity.id,
                )
                names[entity.id] = subject
                if entity.provenance and entity.provenance.locator:
                    names[entity.provenance.locator] = subject
    found: list[tuple[Subject, ...]] = []
    for issue in issues:
        locations = [issue.where] if issue.where in names else re.split(r", |[@~:]", issue.where)
        subjects = {names[name] for name in locations if name in names}
        roles = design.rules.roles if design.rules else None
        if roles and issue.code.startswith("roles."):
            for group in (*roles.loops, *roles.kelvins, *roles.gates):
                if group.name in locations:
                    subjects.update(names[pad] for pad in group.pads if pad in names)
        if issue.code == "length.skew-out-of-range":
            subjects.update(
                subject
                for name, subject in names.items()
                if subject.kind == "net" and f" against {name} at " in issue.message
            )
        found.append(tuple(sorted(subjects, key=lambda s: (s.kind, s.name, s.id))))
    return tuple(found)
