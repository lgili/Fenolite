# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small designs for the project-file unit tests (change c0010)."""

from __future__ import annotations

import dataclasses

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.pro import template
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Circuit, Net, NetClass
from fenolite.model.design import Design


def design(classes: dict[str, int | None], nets: dict[str, str | None]) -> Design:
    """``classes``: name → clearance (nm); ``nets``: name → class name or ``None``."""
    made = {
        name: NetClass(id=derived_id("cls", "test", name), name=name, clearance=c)
        for name, c in classes.items()
    }
    circuit = Circuit(
        nets=tuple(
            Net(id=derived_id("net", "test", n), name=n, netclass_id=made[c].id if c else None)
            for n, c in nets.items()
        ),
        netclasses=tuple(made.values()),
    )
    return dataclasses.replace(Design.new("t", seed=0), circuit=circuit)


def project(target: int = 10, **extra: object) -> JsonObject:
    """The template of ``target`` with HV (clearance 2) after Default, plus ``extra`` top-level keys."""
    data = template(target)
    classes = data["net_settings"]["classes"]
    hv = dict(classes[0])
    hv.update(name="HV", clearance=JsonNumber("2"))
    classes.append(hv)
    data.update(extra)
    return data


def text(data: JsonObject) -> str:
    return _json.dumps(data)
