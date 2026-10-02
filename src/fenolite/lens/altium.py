# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Building a model design into an experimental Altium project (capability altium-build, change c0032).

``build_altium`` runs the build checks of ``ALTIUM_ISSUE_CODES``, gives every component the generic pins
its nets name, validates, writes ``<name>.PrjPcb`` (only when the output folder has none) and the ASCII
``<name>.SchDoc`` through ``fenolite.backends.altium.project.write_project``, and adds the ``.fenolite/``
layer texts and build record of c0011 (``lens.build``). A design with an error gives no file. It reads no
library and no Altium or KiCad file: the board, placements, net classes and diff pairs stay in the model
and are reported as not lowered.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from fenolite.backends.altium import project
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.layout import SheetPlan
from fenolite.backends.altium.project import WRITE_KINDS, component_path, split_link, unique_id
from fenolite.backends.altium.symbols import natural_key
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.lens.build import CACHE_DIR, RECORD_FILE, RECORD_SCHEMA, BuildOutput
from fenolite.model import canonical
from fenolite.model.circuit import Component, Pin
from fenolite.model.design import Design

TARGET = "altium"
"""The value of ``build --target`` for this builder, and of ``target`` in its result and record."""
DSL_BACKEND = "dsl"
UPDATE_COMMAND = "Tools » Update From Libraries"
ALTIUM_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "altium.lib-id-form": "error",
        "altium.footprint-form": "error",
        "altium.text-unwritable": "error",
        "altium.name-case-collision": "error",
        "altium.unique-id-collision": "error",
        "altium.no-footprint": "warning",
        "altium.sheet-custom": "warning",
        "altium.generic-symbols": "info",
        "altium.not-lowered": "info",
        "altium.project-kept": "info",
    }
)
"""The closed table of the Altium build's own issue codes (``model.*`` and ``build.layout-exists`` pass
through)."""
ALTIUM_BUILD_EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-PRJ-KEEP",
        "H-A-PRJ-OPEN",
        "H-A-SCH-ECO",
        "H-A-SCH-LINEEND",
        "H-A-SCH-LINK",
        "H-A-SCH-NETS",
        "H-A-SCH-OPEN",
        "H-A-SCH-RELINK",
        "H-A-SCH-UID",
        "H-A-SCH-UPDATE",
    ),
)
"""``INFERRED`` for every build: author reports cover the files the maintainer opened, never a design."""
EXPERIMENTAL: Mapping[str, object] = MappingProxyType(
    {
        "name": "altium-schematic-writer",
        "command": "build",
        "option": f"--target {TARGET}",
        "write_kinds": list(WRITE_KINDS),
    }
)
"""The ``capabilities`` entry of this writer, without its evidence (``ALTIUM_BUILD_EVIDENCE``)."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, ALTIUM_ISSUE_CODES[code], message, where=where, hint=hint)


def generic_pins(design: Design) -> Design:
    """``design`` with one passive pin per designator its nets name, in natural order, for every component
    that holds no pin yet. A pin's name is its designator and its id is keyed ``pin:<path>:<designator>``."""
    used: dict[str, set[str]] = {c.id: set() for c in design.circuit.components}
    for net in design.circuit.nets:
        for member in net.members:
            if member.component_id in used:
                used[member.component_id].add(member.pin)
    components: list[Component] = []
    for component in design.circuit.components:
        if not component.pins:
            path = component_path(component)
            pins = tuple(
                Pin(id=derived_id("pin", DSL_BACKEND, f"pin:{path}:{d}"), number=d, name=d, etype="passive")
                for d in sorted(used[component.id], key=lambda d: (natural_key(d), d))
            )
            component = dataclasses.replace(component, pins=pins)
        components.append(component)
    circuit = dataclasses.replace(design.circuit, components=tuple(components))
    return dataclasses.replace(design, circuit=circuit)


def _unwritable(issues: list[Issue], text: str, what: str, where: str, *, parameter: bool = False) -> None:
    problem = text_problem(text, parameter=parameter)
    if problem is not None:
        issues.append(
            issue(
                "altium.text-unwritable",
                f"{what} {text!r} {problem}",
                where,
                "use printable 7-bit ASCII without '|', without surrounding spaces"
                + (" and not starting with '='" if parameter else ""),
            )
        )


def _case_collisions(issues: list[Issue], what: str, names: Sequence[str]) -> None:
    seen: dict[str, str] = {}
    for name in sorted(set(names)):
        other = seen.get(name.lower())
        if other is not None:
            issues.append(
                issue(
                    "altium.name-case-collision",
                    f"{what} names {other!r} and {name!r} differ only in letter case",
                    name,
                )
            )
        else:
            seen[name.lower()] = name


def _check(design: Design, name: str, placed: Sequence[str]) -> list[Issue]:
    """The build checks of the closed table, before any pin is set."""
    issues: list[Issue] = []
    _unwritable(issues, name, "design name", name)
    components = sorted(design.circuit.components, key=component_path)
    by_id = {c.id: c for c in components}
    for component in components:
        path, ref = component_path(component), component.ref
        _unwritable(issues, ref, "ref", path)
        link = split_link(component.lib_symbol_ref)
        if link is None:
            issues.append(
                issue(
                    "altium.lib-id-form",
                    f"{ref}: lib_id {component.lib_symbol_ref!r} is not <library>:<name>",
                    path,
                    "name the schematic library file and the symbol, e.g. 'MyParts.SchLib:RES'",
                )
            )
        else:
            _unwritable(issues, link[0], f"{ref} symbol library", path)
            _unwritable(issues, link[1], f"{ref} symbol name", path)
            _unwritable(issues, component.value or link[1], f"{ref} comment", path, parameter=True)
        footprint = component.lib_footprint_ref
        if not footprint:
            issues.append(
                issue(
                    "altium.no-footprint",
                    f"{ref} names no footprint; the engineering change order cannot place it",
                    path,
                    "give the part footprint='<library>.PcbLib:<name>'",
                )
            )
        elif (fp_link := split_link(footprint)) is None:
            issues.append(
                issue(
                    "altium.footprint-form",
                    f"{ref}: footprint {footprint!r} is not <library>:<name>",
                    path,
                    "name the PCB library file and the footprint, e.g. 'MyParts.PcbLib:R0603'",
                )
            )
        else:
            _unwritable(issues, fp_link[0], f"{ref} footprint library", path)
            _unwritable(issues, fp_link[1], f"{ref} footprint name", path)
    for net in sorted(design.circuit.nets, key=lambda n: n.name):
        _unwritable(issues, net.name, "net name", net.name)
        for member in net.members:
            component = by_id.get(member.component_id)
            ref = component.ref if component is not None else member.component_id
            _unwritable(issues, member.pin, f"{ref} pin designator", net.name)
    _case_collisions(issues, "net", [n.name for n in design.circuit.nets])
    _case_collisions(issues, "ref", [c.ref for c in components])
    ids: dict[str, str] = {}
    for component in components:
        uid = unique_id(component.id)
        other = ids.get(uid)
        if other is not None:
            issues.append(
                issue(
                    "altium.unique-id-collision",
                    f"{other} and {component.ref} get the same unique id {uid}",
                    component_path(component),
                )
            )
        ids.setdefault(uid, component.ref)
    issues += _not_lowered(design, placed)
    return issues


def _not_lowered(design: Design, placed: Sequence[str]) -> list[Issue]:
    """One info per kind of design item the Altium files have no place for."""
    found: list[Issue] = []
    if design.board is not None and design.board.outline is not None:
        found.append(issue("altium.not-lowered", "the board outline is kept in the model only", "board"))
    if placed:
        found.append(
            issue(
                "altium.not-lowered",
                f"placements of {', '.join(placed)} are kept in the model only; "
                "Altium's change order places the parts",
                "placements",
            )
        )
    classes = sorted(c.name for c in design.circuit.netclasses)
    if classes:
        message = f"net classes {', '.join(classes)} are kept in the model only"
        found.append(issue("altium.not-lowered", message, "rules"))
    pairs = sorted(i.name for i in design.circuit.interfaces if i.kind == "diff_pair")
    if pairs:
        message = f"diff pairs {', '.join(pairs)} are kept in the model only"
        found.append(issue("altium.not-lowered", message, "interfaces"))
    return found


def _summary(design: Design, kept: Sequence[str], plan: SheetPlan | None) -> dict[str, object]:
    labels = sum(1 for s in plan.stubs if s.net.kind == "label") if plan is not None else 0
    ports = sum(1 for s in plan.stubs if s.net.kind == "port") if plan is not None else 0
    return {
        "components": len(design.circuit.components),
        "nets": len(design.circuit.nets),
        "labels": labels,
        "power_ports": ports,
        "sheet": plan.size.name if plan is not None else None,
        "kept": list(kept),
        "experimental": True,
    }


def build_altium(
    design: Design,
    *,
    name: str,
    placed: Sequence[str] = (),
    project_exists: bool = False,
    form: project.SchematicForm = project.DEFAULT_FORM,
) -> BuildOutput:
    """Every file of the Altium project of ``design`` as bytes, or no file when an issue is an error.

    ``placed`` are the component paths the script placed; ``project_exists`` tells that
    ``<name>.PrjPcb`` already exists in the output folder, so it is kept and not planned; ``form`` is the
    form of ``<name>.SchDoc`` (``binary`` or ``ascii``).
    """
    evidence = Evidence.combine(ALTIUM_BUILD_EVIDENCE, project.EVIDENCE)
    kept = [f"{name}.PrjPcb"] if project_exists else []
    issues = _check(design, name, placed)
    if project_exists:
        issues.append(
            issue(
                "altium.project-kept",
                f"{name}.PrjPcb exists and is kept (Altium rewrites it when documents are added); "
                "delete it to write a new one",
                f"{name}.PrjPcb",
            )
        )
    model = generic_pins(design)
    issues += list(model.validate())
    if any(i.severity == "error" for i in issues):
        return BuildOutput(model, {}, tuple(issues), evidence, _summary(model, kept, None))
    count = len(model.circuit.components)
    issues.append(
        issue(
            "altium.generic-symbols",
            f"{count} component(s) got generic bodies with the pins the design uses; "
            f"'{UPDATE_COMMAND}' replaces them with the library symbols",
            f"{name}.SchDoc",
            "use 'Replace selected attributes' with graphical attributes off to keep every connection",
        )
    )
    files = project.write_project(model, name=name, project=not project_exists, issues=issues, form=form)
    record = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(files.items())}
    for file_name, text in canonical.dump_texts(model).items():
        files[f"{CACHE_DIR}/{file_name}"] = text.encode("utf-8")
    files[RECORD_FILE] = (
        json.dumps(
            {"design": name, "files": record, "schema": RECORD_SCHEMA, "target": TARGET},
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    summary = _summary(model, kept, project.plan_sheet(model))
    return BuildOutput(model, dict(sorted(files.items())), tuple(issues), evidence, summary)


__all__ = [
    "ALTIUM_BUILD_EVIDENCE",
    "ALTIUM_ISSUE_CODES",
    "EXPERIMENTAL",
    "TARGET",
    "build_altium",
    "generic_pins",
]
