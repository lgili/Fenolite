# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A model design as the files of an Altium project: ``<name>.PrjPcb`` and an ASCII ``<name>.SchDoc``
(capability altium-schematic-writer, "Altium writer package").

``write_project`` takes a design whose components hold their pins (``lens.altium.generic_pins`` gives
them), lays the sheet out and returns the file bytes. It writes no file, starts no process and reads no
environment. A design it cannot write raises ``ValueError``; ``lens.altium`` reports the same problems
as issues before it calls the writer.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.layout import PartSpec, PinNet, SheetPlan, layout_sheet
from fenolite.backends.altium.prjpcb import write_prjpcb
from fenolite.backends.altium.schdoc import write_schdoc
from fenolite.backends.altium.symbols import generic_symbol
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Component
from fenolite.model.design import Design

PATH_PROPERTY = "fenolite.path"
"""The component property that holds the component path (set by the DSL)."""
UNIQUE_ID_SALT = "fenolite.altium.uniqueid:"
UNIQUE_ID_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXY"
UNIQUE_ID_LENGTH = 8
WRITE_KINDS: tuple[str, str] = ("altium_prjpcb", "altium_schdoc_ascii")
"""The kinds of the planned writes of an Altium build."""
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-PRJ-OPEN",
        "H-A-SCH-LINEEND",
        "H-A-SCH-LINK",
        "H-A-SCH-NETS",
        "H-A-SCH-OPEN",
        "H-A-SCH-UID",
    ),
)
"""The writer's format facts are inferred from public sources until the maintainer's author reports."""

PowerStyle = Literal["ground", "bar"]


def split_link(text: str) -> tuple[str, str] | None:
    """``<library>:<name>`` split at the first ``:``, or ``None`` when a part is missing."""
    library, colon, name = text.partition(":")
    if not colon or not library or not name:
        return None
    return library, name


def unique_id(key: str) -> str:
    """Eight letters from ``A`` to ``Y``: the SHA-256 of ``fenolite.altium.uniqueid:<key>`` as a big-endian
    integer, written as its eight lowest base-25 digits, least significant first."""
    value = int.from_bytes(hashlib.sha256((UNIQUE_ID_SALT + key).encode("utf-8")).digest(), "big")
    letters: list[str] = []
    for _ in range(UNIQUE_ID_LENGTH):
        value, digit = divmod(value, len(UNIQUE_ID_LETTERS))
        letters.append(UNIQUE_ID_LETTERS[digit])
    return "".join(letters)


def power_styles(design: Design) -> dict[str, PowerStyle]:
    """Net id → port style of every net of a ``power`` interface: ``ground`` for a net that is only ever
    the ``lv`` member, ``bar`` otherwise."""
    roles: dict[str, set[str]] = {}
    for interface in design.circuit.interfaces:
        if interface.kind != "power":
            continue
        for role, net_id in interface.members.items():
            roles.setdefault(net_id, set()).add(role)
    return {net_id: "ground" if found == {"lv"} else "bar" for net_id, found in sorted(roles.items())}


def component_path(component: Component) -> str:
    """The component path: the ``fenolite.path`` property, else the model path, else the ref."""
    return component.properties.get(PATH_PROPERTY) or component.path or component.ref


def _text(text: str, what: str, *, parameter: bool = False) -> str:
    problem = text_problem(text, parameter=parameter)
    if problem is not None:
        raise ValueError(f"{what} {text!r} {problem}")
    return text


def _link(text: str, what: str) -> tuple[str, str]:
    link = split_link(text)
    if link is None:
        raise ValueError(f"{what} {text!r} is not <library>:<name>")
    return _text(link[0], f"{what} library"), _text(link[1], f"{what} name")


def part_specs(design: Design) -> list[PartSpec]:
    """One ``PartSpec`` per component, in component-path order."""
    styles = power_styles(design)
    components = {c.id: c for c in design.circuit.components}
    joins: dict[str, dict[str, PinNet]] = {cid: {} for cid in components}
    for net in sorted(design.circuit.nets, key=lambda n: n.name):
        _text(net.name, "net name")
        style = styles.get(net.id)
        how = PinNet(net.name, "label") if style is None else PinNet(net.name, "port", style)
        for member in net.members:
            component = components.get(member.component_id)
            if component is None:
                raise ValueError(f"net {net.name}: unknown component {member.component_id}")
            if member.pin not in {p.number for p in component.pins}:
                raise ValueError(f"net {net.name}: {component.ref} holds no pin {member.pin!r}")
            current = joins[component.id].get(member.pin)
            if current is not None and current.net != net.name:
                raise ValueError(
                    f"{component.ref} pin {member.pin} is on the nets {current.net} and {net.name}"
                )
            joins[component.id][member.pin] = how
    specs: list[PartSpec] = []
    for component in sorted(design.circuit.components, key=component_path):
        library, symbol = _link(component.lib_symbol_ref, f"{component.ref} lib_id")
        footprint = (
            _link(component.lib_footprint_ref, f"{component.ref} footprint")
            if component.lib_footprint_ref
            else None
        )
        pins = [
            (
                _text(p.number, f"{component.ref} pin designator"),
                _text(p.name or p.number, f"{component.ref} pin name"),
            )
            for p in component.pins
        ]
        specs.append(
            PartSpec(
                key=component_path(component),
                ref=_text(component.ref, "ref"),
                comment=_text(component.value or symbol, f"{component.ref} comment", parameter=True),
                library=library,
                symbol=symbol,
                footprint=footprint,
                unique_id=unique_id(component.id),
                body=generic_symbol(pins),
                nets=joins[component.id],
            )
        )
    ids = [s.unique_id for s in specs]
    if len(set(ids)) != len(ids):
        raise ValueError("two components share a unique id")
    return specs


def plan_sheet(design: Design) -> SheetPlan:
    """The sheet layout of ``design``: sheet size, placed components and stubs."""
    return layout_sheet(part_specs(design))


def write_project(
    design: Design, *, name: str, project: bool = True, issues: list[Issue] | None = None
) -> dict[str, bytes]:
    """``<name>.SchDoc`` and, when ``project`` is true, ``<name>.PrjPcb``, as bytes; no file is written."""
    _text(name, "design name")
    plan = plan_sheet(design)
    if plan.size.style is None and issues is not None:
        issues.append(
            Issue(
                "altium.sheet-custom",
                "warning",
                f"the layout does not fit an A0 sheet; a custom sheet of {plan.size.width} x "
                f"{plan.size.height} mil is written",
                where=f"{name}.SchDoc",
            )
        )
    files: dict[str, bytes] = {}
    if project:
        files[f"{name}.PrjPcb"] = write_prjpcb(schematic=f"{name}.SchDoc")
    files[f"{name}.SchDoc"] = write_schdoc(plan)
    return files


__all__ = [
    "EVIDENCE",
    "PATH_PROPERTY",
    "WRITE_KINDS",
    "component_path",
    "part_specs",
    "plan_sheet",
    "power_styles",
    "split_link",
    "unique_id",
    "write_project",
]
