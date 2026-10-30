# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where the devices of a script come from, and checked pin names (change c0248, ``docs/devices.md``).

A device id resolves from, in this order: the records given to ``Design.devices(*records)``, the project
devices that the script runner installed for this run (``devices/*.toml`` beside the script, read by
``fenolite.cli._script``), and the shipped ``Fenolite:`` devices of ``fenolite.catalog.devices``. The first
source that holds the id wins. The DSL itself reads no file: the runner installs the project devices
through the context variable of this module.
"""

from __future__ import annotations

import contextlib
import difflib
import keyword
from collections.abc import Generator, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from fenolite.catalog.devices import shipped_devices
from fenolite.dsl.errors import DslError
from fenolite.model.library import DeviceDef

if TYPE_CHECKING:
    from fenolite.dsl.part import Part, PinHandle

Origin = Literal["builtin", "authored"]
PIN_LIST_LIMIT = 24
"""The most functions a ``PinNameError`` lists before it cuts the list with ``…``."""


@dataclass(frozen=True, slots=True)
class ProjectDevices:
    """The project devices of one run: the records in file-name order, and the file of each id."""

    devices: tuple[DeviceDef, ...] = ()
    files: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class Resolved:
    """A resolved device id: the record, its origin (``authored`` for a design or project record,
    ``builtin`` for a shipped one) and whether it overrides a shipped device of the same id."""

    device: DeviceDef
    origin: Origin
    overrides: bool = False


_PROJECT: ContextVar[ProjectDevices | None] = ContextVar("fenolite_project_devices", default=None)
_DESIGN: ContextVar[Mapping[str, DeviceDef] | None] = ContextVar("fenolite_design_devices", default=None)


@contextlib.contextmanager
def installed(project: ProjectDevices) -> Generator[None]:
    """Install the project devices of one script run (used by the script runner)."""
    token = _PROJECT.set(project)
    try:
        yield
    finally:
        _PROJECT.reset(token)


@contextlib.contextmanager
def design_records(records: Mapping[str, DeviceDef]) -> Generator[None]:
    """Resolve device ids against ``records`` first while the block runs (``Design.part``)."""
    token = _DESIGN.set(records)
    try:
        yield
    finally:
        _DESIGN.reset(token)


def project_devices() -> ProjectDevices:
    """The project devices installed for this run, or none."""
    return _PROJECT.get() or ProjectDevices()


def known_ids() -> tuple[str, ...]:
    """Every device id the current call can resolve, in code-point order."""
    project = project_devices()
    found = {device.id for device in shipped_devices()}
    found |= {device.id for device in project.devices}
    found |= set(_DESIGN.get() or {})
    return tuple(sorted(found))


def resolve(device_id: object) -> Resolved:
    """The device of ``device_id`` by the precedence of this module; ``DslError`` naming the closest known
    ids when no source holds it."""
    if not isinstance(device_id, str) or not device_id:
        raise DslError(f"a device is named by its id, such as 'Fenolite:R_0603', not {device_id!r}")
    shipped = {device.id for device in shipped_devices()}
    design = _DESIGN.get() or {}
    if device_id in design:
        return Resolved(design[device_id], "authored", device_id in shipped)
    for device in project_devices().devices:
        if device.id == device_id:
            return Resolved(device, "authored", device_id in shipped)
    for device in shipped_devices():
        if device.id == device_id:
            return Resolved(device, "builtin")
    closest = difflib.get_close_matches(device_id, known_ids(), n=3, cutoff=0.6)
    hint = f"; closest: {', '.join(closest)}" if closest else ""
    raise DslError(
        f"unknown device {device_id!r}{hint}; list the shipped devices with 'fenolite catalog list --kind "
        "device', or put the record in devices/ beside the script"
    )


def check_records(records: Sequence[object]) -> tuple[DeviceDef, ...]:
    """``records`` checked as ``DeviceDef`` values for ``Design.devices``."""
    found: list[DeviceDef] = []
    for record in records:
        if not isinstance(record, DeviceDef):
            raise DslError(
                f"devices() takes DeviceDef records (fenolite.catalog.devices.parse_device), not {record!r}"
            )
        found.append(record)
    return tuple(found)


# ------------------------------------------------------------------------------------------- pins


class PinNameError(DslError, AttributeError):
    """A designator that is neither a function nor a listed symbol pin of a device part. It is also an
    ``AttributeError``, so ``hasattr`` and ``copy`` keep working on device parts."""


def functions(device: DeviceDef) -> tuple[str, ...]:
    """The function names of ``device``, in code-point order."""
    return tuple(sorted(pin.function for pin in device.pins))


def closest(name: str, names: Sequence[str]) -> list[str]:
    """A case-insensitive exact match when there is one, else up to three close names (``difflib``)."""
    folded = [found for found in names if found.casefold() == name.casefold()]
    if folded:
        return folded[:1]
    return difflib.get_close_matches(name, list(names), n=3, cutoff=0.6)


def pin_name_error(part: Part, device: DeviceDef, name: str, what: str = "pin") -> PinNameError:
    """The error of a wrong designator ``name`` on ``part``: the closest functions, then every function."""
    names = functions(device)
    near = closest(name, names)
    listed = ", ".join(names[:PIN_LIST_LIMIT]) + (", …" if len(names) > PIN_LIST_LIMIT else "")
    near_text = f"; closest: {', '.join(near)}" if near else ""
    return PinNameError(
        f"part {part.label} (device {device.id}) has no {what} {name!r}{near_text}; pins: {listed}"
    )


def designator(part: Part, device: DeviceDef, text: str) -> str:
    """``text`` checked against ``device``: a function name, or a symbol pin number the device lists."""
    if any(pin.function == text for pin in device.pins):
        return text
    if any(text in pin.pins for pin in device.pins):
        return text
    raise pin_name_error(part, device, text)


def function_pad(part: Part, device: DeviceDef, name: str, index: int | None) -> str | None:
    """The pad that ``part.pad(name, index=…)`` names on a device part: ``None`` when ``name`` is a pad of
    the device (mapped or unused), else the ``index``-th pad (default the first) of function ``name``."""
    pads = {pad for pin in device.pins for pad in pin.pads} | set(device.unused_pads)
    if name in pads:
        return None
    for pin in device.pins:
        if pin.function == name:
            pick = 0 if index is None else index
            if isinstance(pick, bool) or not isinstance(pick, int) or not 0 <= pick < len(pin.pads):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(
                    f"part {part.label}: function {name} has {len(pin.pads)} pad(s); "
                    f"index {index!r} names none"
                )
            return pin.pads[pick]
    raise pin_name_error(part, device, name, "pad or pin")


def attribute_names(device: DeviceDef, taken: set[str]) -> tuple[str, ...]:
    """The functions of ``device`` that are Python identifiers, not keywords and not in ``taken``."""
    return tuple(
        name
        for name in functions(device)
        if name.isidentifier() and not keyword.iskeyword(name) and name not in taken
    )


def shadowed(device: DeviceDef) -> tuple[str, ...]:
    """The functions of ``device`` that an attribute of ``Part`` hides: reached only as ``part["name"]``."""
    from fenolite.dsl.part import Part

    return tuple(name for name in functions(device) if hasattr(Part, name))


def end_handle(part: Part, index: int) -> PinHandle | None:
    """The handle of the ``index``-th named end (0 or 1) of a device part with ``ends``, or ``None``: the
    hook that ``Part._end`` of change c0247 reads."""
    device = part.device
    if device is None or not device.ends:
        return None
    from fenolite.dsl.part import PinHandle

    return PinHandle(part, device.ends[index])


def must_connect_pins(device: DeviceDef | None) -> tuple[str, ...]:
    """The symbol pins of the functions of ``device`` marked ``must_connect``, in code-point order: what
    ``must_connect_pins(component, device)`` of change c0247 reads."""
    if device is None:
        return ()
    return tuple(sorted({number for pin in device.pins if pin.must_connect for number in pin.pins}))


__all__ = [
    "PIN_LIST_LIMIT",
    "Origin",
    "PinNameError",
    "ProjectDevices",
    "Resolved",
    "attribute_names",
    "check_records",
    "closest",
    "design_records",
    "designator",
    "end_handle",
    "function_pad",
    "functions",
    "installed",
    "known_ids",
    "must_connect_pins",
    "pin_name_error",
    "project_devices",
    "resolve",
    "shadowed",
]
