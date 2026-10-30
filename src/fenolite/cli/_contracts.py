# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The device records and part classes that ``fenolite build``, ``fenolite check`` and ``fenolite roles``
inject into the stage ``circuit.rules`` (change c0253; capability verification-loop, "Device records injected
into the circuit stage"; ``docs/contracts.md``).

``checks`` imports neither ``catalog`` nor ``roles``, so the commands resolve each component's
``fenolite.device`` id here (the design's own records, then ``devices/*.toml`` of the project folder, then the
shipped ``Fenolite:`` devices: the order of ``fenolite.dsl.devices``) and classify the parts with the one
classifier, ``fenolite.roles.classify``, with the classes the user states.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fenolite.catalog.devices import load_devices, shipped_devices
from fenolite.core.errors import FormatError
from fenolite.model.design import Design
from fenolite.model.library import DeviceDef
from fenolite.roles.classify import classify

DEVICE_PROPERTY = "fenolite.device"
DEVICES_DIR = "devices"


def devices_of(
    model: Design, folder: Path | None = None, records: Mapping[str, DeviceDef] | None = None
) -> dict[str, DeviceDef]:
    """The record of each device id the model's components name: from ``records`` (the design's own and the
    build's), then the ``devices/`` folder of ``folder``, then that of its parent (a build folder beside the
    script, ``--out <script folder>/build``), then the shipped devices. An id no source holds is
    left out, and the stage counts its parts in ``circuit.rating-missing``; a malformed project file is left
    out the same way."""
    wanted = {
        c.properties[DEVICE_PROPERTY] for c in model.circuit.components if DEVICE_PROPERTY in c.properties
    }
    if not wanted:
        return {}
    found: dict[str, DeviceDef] = {key: value for key, value in (records or {}).items() if key in wanted}
    for place in () if folder is None else (folder, folder.parent):
        if not wanted - set(found):
            break
        try:
            project, _issues = load_devices(place / DEVICES_DIR)
        except FormatError:
            project = ()
        for device in project:
            if device.id in wanted:
                found.setdefault(device.id, device)
    for device in shipped_devices():
        if device.id in wanted:
            found.setdefault(device.id, device)
    return dict(sorted(found.items()))


def classes_of(model: Design) -> dict[str, str]:
    """The class of each component id by ``fenolite.roles.classify`` with the classes the user states in the
    model (``design.part_class``, confirmed classes)."""
    roles = model.rules.roles if model.rules is not None else None
    user = roles.classes if roles is not None else ()
    by_ref = classify(model.circuit, user=user)
    return {
        component.id: by_ref[component.ref].cls
        for component in model.circuit.components
        if component.ref in by_ref
    }


__all__ = ["classes_of", "devices_of"]
