# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generator calls: small circuits whose values the build chooses, exactly (change c0254; ``docs/dsl.md``,
"Generators", and ``docs/picking.md``).

A generator checks its arguments at the call, creates its parts as query parts in the given block (or the
design) with a ``GeneratorRequest`` attached, connects them, and returns them. It reads no catalog and no
lock: the build solves the request (``fenolite.pick.generators``), records what it achieved
(``gen.achieved``) and writes the picks to the design lock. The parts' resistor or capacitor constraints are
the defaults of the enclosing levels merged with the call's (``series=``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from fenolite.core.partquery import KEYS, Bounds, Constraint, GeneratorRequest, PartQuery
from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import I2C
from fenolite.dsl.module import Container, Module
from fenolite.dsl.part import Net, Part, check_name, connect
from fenolite.dsl.quantity import Quantity, Range
from fenolite.dsl.query import Level, canonical, check_constraint, merged

MODES: tuple[str, ...] = ("standard", "fast", "fast-plus")
"""The I2C speed modes ``i2c_pull_ups`` knows (``fenolite.pick.generators.pullup.MODES``)."""


def _container(b: object, call: str) -> Container:
    if not isinstance(b, Container) or b.design is None:
        raise DslError(f"{call}: the first argument is the block builder b or the design, not {b!r}")
    return b


def _levels(container: Container, kind: str) -> list[Level]:
    chain: list[object] = []
    node: object | None = container
    while node is not None:
        chain.append(node)
        node = getattr(node, "parent", None)
    found: list[Level] = []
    for item in reversed(chain):
        store = cast("dict[str, Level] | None", getattr(item, "query_defaults", None))
        if store is not None and kind in store:
            found.append(store[kind])
    return found


def _range(value: object, unit: str, what: str, *, quantity: bool = True) -> Bounds:
    """``value`` as bounded bounds in ``unit``: a ``Range``, or a ``Quantity`` when ``quantity``."""
    if isinstance(value, Quantity) and quantity:
        value = value.as_range()
    if not isinstance(value, Range):
        need = (
            "a range, such as between(ua(40), ua(100))"
            if not quantity
            else f"a quantity or a range in {unit}"
        )
        raise DslError(f"{what} must be {need}, not {value!r}")
    if value.unit != unit:
        raise DslError(f"{what} is in {unit}, not in {value.unit}")
    if value.low is None or value.high is None:
        raise DslError(f"{what} must be bounded on both sides, not {value.text()}")
    if value.low <= 0:
        raise DslError(f"{what} must lie above zero, not {value.text()}")
    return Bounds(unit, value.low, value.high, value.nominal_value)


def _text(value: object) -> str:
    return value.text() if isinstance(value, (Range, Quantity)) else str(value)


def _net(value: object, what: str) -> Net:
    from fenolite.dsl.portnets import as_net

    found = as_net(value, what=what)
    if found is None:
        raise DslError(f"{what} must be a Net or a net-like port, not {value!r}")
    return found


def _free(container: Container, name: str, call: str) -> str:
    check_name(name, "part name")
    if any(isinstance(child, Part) and child.key == name for child in container.children):
        where = f"{container.path}/{name}" if isinstance(container, Module) else name
        raise DslError(f"{call}: the part name {where} is already used in {container.describe()}")
    return name


def _group(container: Container, name: str) -> str:
    return f"{container.path}/{name}" if isinstance(container, Module) else name


def _constraints(
    container: Container, kind: str, call: Mapping[str, object], what: str
) -> dict[str, Constraint]:
    given: dict[str, Constraint] = {}
    cleared: list[str] = []
    for key, value in call.items():
        checked = check_constraint(kind, key, value, what)
        if checked is None:
            cleared.append(key)
        else:
            given[key] = checked
    found = merged(kind, _levels(container, kind), None)
    for key in cleared:
        found.pop(key, None)
    found.update(given)
    return found


def _make(
    container: Container,
    name: str,
    kind: str,
    request: GeneratorRequest,
    constraints: Mapping[str, Constraint],
    fixed: PartQuery | None = None,
) -> Part:
    ordered = tuple((key.name, constraints[key.name]) for key in KEYS[kind] if key.name in constraints)
    query = PartQuery(
        kind,
        fixed.value if fixed is not None else None,
        fixed.exact if fixed is not None else False,
        ordered,
        canonical(kind, fixed.value_text if fixed is not None else "", dict(ordered)),
        generator=request,
        value_text=fixed.value_text if fixed is not None else "",
    )
    if isinstance(container, Module):
        from fenolite.dsl.block import Block

        if isinstance(container, Block):
            return container.part(name, device=query)
    return container.part(name=name, device=query)


def _request(
    name: str,
    group: str,
    inputs: list[tuple[str, object, str]],
    constraints: Mapping[str, Constraint],
    kind: str,
) -> tuple[tuple[tuple[str, object], ...], str]:
    """The request's inputs and canonical text: the inputs as written, then the part constraints."""
    shown = [f"{key}={text}" for key, _, text in inputs]
    body = canonical(kind, "", dict(constraints))
    inner = body[len(kind) + 1 : -1]
    if inner:
        shown.append(inner)
    return tuple((key, value) for key, value, _ in inputs), f"{name}({', '.join(shown)})"


def voltage_divider(
    b: object,
    hi: object,
    mid: object,
    lo: object,
    *,
    target: Range,
    ref: Range | Quantity | None = None,
    vin: Range | Quantity | None = None,
    current: Range,
    series: str | None = None,
    name: str | None = None,
) -> tuple[Part, Part]:
    """Two resistors from ``hi`` over ``mid`` to ``lo`` (``<name>_top``, ``<name>_bot``; ``name`` defaults to
    the leaf name of ``mid``). With ``ref``, ``target`` is the range of ``hi`` and ``VOUT = VREF · (1 + Rt /
    Rb)``; without, ``target`` is the range of ``mid`` and ``VMID = VIN · Rb / (Rt + Rb)`` with ``vin``.
    ``current`` is the window of the divider current (a range: the search window must be stated)."""
    call = "voltage_divider()"
    container = _container(b, call)
    nets = [_net(hi, f"{call}: hi"), _net(mid, f"{call}: mid"), _net(lo, f"{call}: lo")]
    if isinstance(current, Quantity):
        raise DslError(
            f"{call}: current must be a range of the divider current, such as between(ua(40), "
            f"ua(100)), not the quantity {current.text()}"
        )
    if ref is None and vin is None:
        raise DslError(f"{call}: give ref= (a feedback divider) or vin= (a plain divider); it has neither")
    if ref is not None and vin is not None:
        raise DslError(f"{call}: give ref= or vin=, not both")
    inputs: list[tuple[str, object, str]] = [
        ("target", _range(target, "volt", f"{call}: target"), _text(target))
    ]
    if ref is not None:
        inputs.append(("ref", _range(ref, "volt", f"{call}: ref"), _text(ref)))
    else:
        inputs.append(("vin", _range(vin, "volt", f"{call}: vin"), _text(vin)))
    inputs.append(("current", _range(current, "ampere", f"{call}: current", quantity=False), _text(current)))
    leaf = name if name is not None else nets[1].name.rpartition("/")[2]
    top_name = _free(container, f"{leaf}_top", call)
    bot_name = _free(container, f"{leaf}_bot", call)
    constraints = _constraints(container, "resistor", {} if series is None else {"series": series}, call)
    group = _group(container, leaf)
    values, text = _request("voltage_divider", group, inputs, constraints, "resistor")
    top = _make(
        container,
        top_name,
        "resistor",
        GeneratorRequest("voltage_divider", group, "top", values, text),
        constraints,
    )
    bot = _make(
        container,
        bot_name,
        "resistor",
        GeneratorRequest("voltage_divider", group, "bot", values, text),
        constraints,
    )
    connect(nets[0], top["1"])
    connect(nets[1], top["2"], bot["1"])
    connect(nets[2], bot["2"])
    return top, bot


def rc_lowpass(
    b: object,
    inp: object,
    out: object,
    gnd: object,
    *,
    corner: Range,
    r: PartQuery | None = None,
    c: PartQuery | None = None,
    name: str | None = None,
) -> tuple[Part, Part]:
    """A resistor from ``inp`` to ``out`` and a capacitor from ``out`` to ``gnd`` (``<name>_R``, ``<name>_C``)
    whose worst-case corner ``1 / (2πRC)`` lies within ``corner``; ``r=`` or ``c=`` fixes one part by a
    query of its kind."""
    call = "rc_lowpass()"
    container = _container(b, call)
    nets = [_net(inp, f"{call}: inp"), _net(out, f"{call}: out"), _net(gnd, f"{call}: gnd")]
    for given, kind in ((r, "resistor"), (c, "capacitor")):
        if given is not None and (
            not isinstance(given, PartQuery)  # pyright: ignore[reportUnnecessaryIsInstance]
            or given.kind != kind
            or given.generator is not None
        ):
            raise DslError(f"{call}: {kind[0]}= takes a {kind}(...) query, not {given!r}")
    inputs: list[tuple[str, object, str]] = [
        ("corner", _range(corner, "hertz", f"{call}: corner"), _text(corner))
    ]
    if r is not None:
        inputs.append(("r", r.value_text, r.text()))
    if c is not None:
        inputs.append(("c", c.value_text, c.text()))
    leaf = name if name is not None else nets[1].name.rpartition("/")[2]
    r_name, c_name = _free(container, f"{leaf}_R", call), _free(container, f"{leaf}_C", call)
    r_constraints = _constraints(container, "resistor", {}, call)
    c_constraints = _constraints(container, "capacitor", {}, call)
    if r is not None:
        r_constraints.update(dict(r.constraints))
    if c is not None:
        c_constraints.update(dict(c.constraints))
    group = _group(container, leaf)
    values, text = _request("rc_lowpass", group, inputs, {}, "resistor")
    rp = _make(
        container,
        r_name,
        "resistor",
        GeneratorRequest("rc_lowpass", group, "r", values, text),
        r_constraints,
        r,
    )
    cp = _make(
        container,
        c_name,
        "capacitor",
        GeneratorRequest("rc_lowpass", group, "c", values, text),
        c_constraints,
        c,
    )
    connect(nets[0], rp["1"])
    connect(nets[1], rp["2"], cp["1"])
    connect(nets[2], cp["2"])
    return rp, cp


def led_resistor(
    b: object,
    supply: object,
    led: object,
    *,
    current: Range,
    vf: Range | Quantity,
    vs: Range | Quantity,
    name: str | None = None,
) -> Part:
    """The series resistor of an LED, from ``supply`` to ``led`` (the net of the LED's anode), whose
    worst-case current ``(VS − VF) / R`` lies within ``current`` and whose power rating covers the worst
    dissipation. ``vs`` is the supply range and ``vf`` the forward-voltage range (until change c0252 gives
    rails and LED records a voltage)."""
    call = "led_resistor()"
    container = _container(b, call)
    top, bottom = _net(supply, f"{call}: supply"), _net(led, f"{call}: led")
    inputs: list[tuple[str, object, str]] = [
        ("current", _range(current, "ampere", f"{call}: current", quantity=False), _text(current)),
        ("vf", _range(vf, "volt", f"{call}: vf"), _text(vf)),
        ("vs", _range(vs, "volt", f"{call}: vs"), _text(vs)),
    ]
    leaf = name if name is not None else f"{bottom.name.rpartition('/')[2]}_R"
    part_name = _free(container, leaf, call)
    constraints = _constraints(container, "resistor", {}, call)
    group = _group(container, leaf)
    values, text = _request("led_resistor", group, inputs, constraints, "resistor")
    part = _make(
        container,
        part_name,
        "resistor",
        GeneratorRequest("led_resistor", group, "r", values, text),
        constraints,
    )
    connect(top, part["1"])
    connect(bottom, part["2"])
    return part


def i2c_pull_ups(
    b: object,
    bus: object,
    supply: object,
    *,
    bus_capacitance: Range,
    vdd: Range | Quantity,
    mode: str | None = None,
    name: str = "PU",
) -> tuple[Part, Part]:
    """One pull-up value for both lines of ``bus`` (an ``I2C``), from ``supply``: the largest series value
    whose worst-case span lies in the window of the I2C specification for ``mode`` (``standard``, ``fast``
    — the default — or ``fast-plus``), ``bus_capacitance`` and the supply range ``vdd``. The parts are
    ``<name>_sda`` and ``<name>_scl``."""
    call = "i2c_pull_ups()"
    container = _container(b, call)
    if not isinstance(bus, I2C):
        raise DslError(f"{call}: bus is an I2C interface, not {bus!r}")
    rail = _net(supply, f"{call}: supply")
    chosen = mode if mode is not None else "fast"
    if chosen not in MODES:
        raise DslError(f"{call}: mode is one of {', '.join(MODES)}, not {mode!r}")
    inputs: list[tuple[str, object, str]] = [
        (
            "bus_capacitance",
            _range(bus_capacitance, "farad", f"{call}: bus_capacitance", quantity=False),
            _text(bus_capacitance),
        ),
        ("vdd", _range(vdd, "volt", f"{call}: vdd"), _text(vdd)),
        ("mode", chosen, chosen),
    ]
    names = (_free(container, f"{name}_sda", call), _free(container, f"{name}_scl", call))
    constraints = _constraints(container, "resistor", {}, call)
    group = _group(container, name)
    values, text = _request("i2c_pull_ups", group, inputs, constraints, "resistor")
    parts: list[Part] = []
    for role, part_name in zip(("sda", "scl"), names, strict=True):
        part = _make(
            container,
            part_name,
            "resistor",
            GeneratorRequest("i2c_pull_ups", group, role, values, text),
            constraints,
        )
        connect(rail, part["1"])
        connect(bus.members[role], part["2"])
        parts.append(part)
    return parts[0], parts[1]


def shunt(
    b: object,
    hi: object,
    lo: object,
    *,
    current: Range,
    full_scale: Range | Quantity,
    name: str = "SHUNT",
) -> Part:
    """A current-sense resistor from ``hi`` to ``lo``: the largest row value whose worst-case drop at the
    largest ``current`` stays within the smallest ``full_scale`` input and whose power rating covers the
    dissipation. The part gets the class ``shunt`` for net roles (``part_class``, change c0222)."""
    call = "shunt()"
    container = _container(b, call)
    top, bottom = _net(hi, f"{call}: hi"), _net(lo, f"{call}: lo")
    if isinstance(current, Quantity):
        raise DslError(
            f"{call}: current must be a range of the load current, such as between(amp(0), amp(5))"
        )
    if (
        not isinstance(current, Range)  # pyright: ignore[reportUnnecessaryIsInstance]
        or current.unit != "ampere"
        or current.low is None
        or current.high is None
    ):
        raise DslError(f"{call}: current must be a bounded range in ampere, not {current!r}")
    inputs: list[tuple[str, object, str]] = [
        ("current", Bounds("ampere", current.low, current.high, current.nominal_value), _text(current)),
        ("full_scale", _range(full_scale, "volt", f"{call}: full_scale"), _text(full_scale)),
    ]
    part_name = _free(container, name, call)
    constraints = _constraints(container, "resistor", {}, call)
    group = _group(container, name)
    values, text = _request("shunt", group, inputs, constraints, "resistor")
    part = _make(
        container, part_name, "resistor", GeneratorRequest("shunt", group, "r", values, text), constraints
    )
    connect(top, part["1"])
    connect(bottom, part["2"])
    design = container.design
    assert design is not None
    design.part_class(part, "shunt")
    return part


__all__ = ["MODES", "i2c_pull_ups", "led_resistor", "rc_lowpass", "shunt", "voltage_divider"]
