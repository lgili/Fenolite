# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designs generated from a seed for the netlist acceptance test (capability kicad-oracle, "Own netlists
equal kicad-cli's"; change c0063).

Every design is made here by a seeded generator over the authored CC0 mini library: one to twelve parts
(resistors, LEDs, the two-gate part with its power unit, the 32-pin IC), some in a module, some with a
pin-pad map, their pins joined to nets at random, marked as not connected, or left open, with or without
a power interface, and with net names that hold a slash. Nothing is read from a file and nothing comes
from another project. Two calls with equal arguments give equal designs.

With ``modules=True`` (change c0070, "Hierarchical schematics pass the oracles") a module may lie inside
another, and each 32-pin IC gets one or two resistors of its own on dedicated nets, in the module of the
IC: the parts a readable sheet draws beside the IC pins. The designs of ``modules=False`` are unchanged.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.dsl import Design, Module, Net, Part, Power, connect, mm, no_connect, to_model

SEED = 20261004
MODULE_SEED = 20261005
"""The seed of the acceptance set with nested modules and satellites (``modules=True``)."""
COUNT = 25
MAX_PARTS = 12
MAX_ICS = 2
CELL_MM = 14
"""The pitch of the placement grid: the largest footprint of the library is 9 mm wide."""
COLUMNS = 4
SWAP = {"1": "2", "2": "1"}
"""The pin-pad map of a two-pin part whose pads are exchanged."""
SUPPLIES: tuple[tuple[str, str], ...] = (("VCC", "GND"), ("+3V3", "GND"), ("VIN", "PGND"))
SCOPES: tuple[str, ...] = ("mod", "bus", "a/b")
"""Prefixes of the net names that hold a slash."""
MODULES: tuple[str, ...] = ("mod", "io")
SUB = "sub"
"""The name of a module inside a module, with ``modules=True``."""
SNAP_PINS: tuple[str, ...] = ("3", "6", "14", "19", "22", "27", "30")
"""The IC pins that may get a resistor of their own with ``modules=True``: none is a supply pin."""


@dataclass(frozen=True)
class Kind:
    """A part of the mini library: reference prefix, symbol, footprint, value, pin numbers, the pins of
    its supply as (high, low), and how often it is drawn."""

    prefix: str
    symbol: str
    footprint: str
    value: str
    pins: tuple[str, ...]
    supply: tuple[str, str] | None
    weight: int
    mappable: bool = False


KINDS: tuple[Kind, ...] = (
    Kind("R", "Mini:Mini_R", "Mini:Mini_R_0603", "1k", ("1", "2"), None, 4, mappable=True),
    Kind("D", "Mini:Mini_LED", "Mini:Mini_LED_THT_3mm", "LED", ("1", "2"), None, 3, mappable=True),
    Kind(
        "U",
        "Mini:Mini_DualGate",
        "Mini:Mini_QFP-32_7x7mm_P0.8mm",
        "GATE",
        ("1", "2", "3", "4", "5", "6", "7", "14"),
        ("14", "7"),
        2,
    ),
    Kind(
        "U",
        "Mini:Mini_QFP32_IC",
        "Mini:Mini_QFP-32_7x7mm_P0.8mm",
        "MCU",
        tuple(str(number) for number in range(1, 33)),
        ("9", "10"),
        1,
    ),
)
IC = KINDS[3]


def _kinds(rng: random.Random, count: int) -> list[Kind]:
    chosen: list[Kind] = []
    for _ in range(count):
        pool = [k for k in KINDS if k is not IC or sum(1 for c in chosen if c is IC) < MAX_ICS]
        chosen.append(rng.choices(pool, weights=[k.weight for k in pool])[0])
    return chosen


def _part_count(rng: random.Random, index: int) -> int:
    """One part for the first design and twelve for the second, so both ends of the range are there."""
    return {0: 1, 1: MAX_PARTS}.get(index, rng.randint(1, MAX_PARTS))


def _holder(found: dict[str, Module], path: str) -> Module:
    """The module at ``path``, made with the modules above it when it is new."""
    if path not in found:
        found[path] = Module(path.rpartition("/")[2])
        above = path.rpartition("/")[0]
        if above:
            _holder(found, above).add(found[path])
    return found[path]


def design(seed: int, index: int, modules: bool = False) -> Design:
    """Design ``index`` of the sequence of ``seed``, named ``gen<index>``; ``modules`` adds nested modules
    and resistors on IC pins (the extra draws come from a generator of their own)."""
    rng = random.Random(f"{seed}:{index}")
    kinds = _kinds(rng, _part_count(rng, index))
    extra = random.Random(f"{seed}:{index}:modules")
    beside = [extra.randint(1, 2) if modules and kind is IC else 0 for kind in kinds]
    slots = len(kinds) + sum(beside)
    columns = min(COLUMNS, slots)
    rows = -(-slots // columns)
    made = Design(f"gen{index:02d}")
    made.board(mm(CELL_MM * columns + 4), mm(CELL_MM * rows + 4))

    counters: dict[str, int] = {}
    parts: list[tuple[Part, Kind]] = []
    found: dict[str, Module] = {}
    holders: list[Module | None] = []
    for slot, kind in enumerate(kinds):
        counters[kind.prefix] = counters.get(kind.prefix, 0) + 1
        mapped = kind.mappable and rng.random() < 0.35
        part = Part(
            f"{kind.prefix}{counters[kind.prefix]}",
            kind.symbol,
            footprint=kind.footprint,
            value=kind.value,
            pad_map=SWAP if mapped else None,
        )
        part.place(mm(CELL_MM * (slot % columns) + 9), mm(CELL_MM * (slot // columns) + 9))
        parts.append((part, kind))
        if rng.random() < 0.3:
            name = rng.choice(MODULES)
            if modules and extra.random() < 0.5:
                name = f"{name}/{SUB}"
            _holder(found, name).add(part)
            holders.append(found[name])
        else:
            made.add(part)
            holders.append(None)
    # with ``modules``: resistors on pins of each IC, in the IC's own module, each on a net of its own
    reserved: dict[tuple[int, str], Net] = {}
    satellites: list[Part] = []
    slot = len(kinds)
    for (part, _), holder, count in zip(list(parts), holders, beside, strict=True):
        for pin in extra.sample(SNAP_PINS, count):
            counters["R"] = counters.get("R", 0) + 1
            resistor = Part(f"R{counters['R']}", KINDS[0].symbol, footprint=KINDS[0].footprint, value="10k")
            resistor.place(mm(CELL_MM * (slot % columns) + 9), mm(CELL_MM * (slot // columns) + 9))
            slot += 1
            (holder if holder is not None else made).add(resistor)
            reserved[(id(part), pin)] = Net(f"S{len(reserved) + 1}")
            connect(reserved[(id(part), pin)], part[pin], resistor["1"])
            satellites.append(resistor)
    for name in sorted(found):
        if "/" not in name:
            made.add(found[name])

    total = sum(len(kind.pins) for _, kind in parts)
    signals: list[Net] = []
    for number in range(1, rng.randint(1, min(10, max(1, total // 3))) + 1):
        scope = f"{rng.choice(SCOPES)}/" if rng.random() < 0.3 else ""
        signals.append(Net(f"{scope}N{number}"))
    supply = rng.choice(SUPPLIES) if rng.random() < 0.8 else None
    high, low = (Net(supply[0]), Net(supply[1])) if supply is not None else (None, None)

    used: set[int] = set()
    free: list[tuple[Part, str]] = []
    for part, kind in parts:
        often = 0.8 if len(kind.pins) == 2 else 0.5
        for pin in kind.pins:
            if (id(part), pin) in reserved:
                continue
            draw = rng.random()
            rail = None
            if kind.supply is not None and pin in kind.supply and high is not None and low is not None:
                rail = high if pin == kind.supply[0] else low
            if rail is not None and draw < 0.85:
                connect(rail, part[pin])
                used.add(id(rail))
            elif draw < often:
                net = rng.choice(signals)
                connect(net, part[pin])
                used.add(id(net))
            elif draw < often + 0.25:
                no_connect(part[pin])
            else:
                free.append((part, pin))
    if high is not None and low is not None:
        # a supply needs a pin on each of its nets; a design of two-pin parts only may have none left
        for rail in (high, low):
            if id(rail) not in used and free:
                part, pin = free.pop(rng.randrange(len(free)))
                connect(rail, part[pin])
                used.add(id(rail))
        if id(high) in used and id(low) in used:
            made.add(Power(high, low))
    for resistor in satellites:
        # the far pin of a resistor on an IC pin: on a signal, so no supply net is left with one pin
        connect(extra.choice(signals), resistor["2"])
    return made


def designs(seed: int = SEED, count: int = COUNT, modules: bool = False) -> list[Design]:
    """``count`` designs of the sequence of ``seed``, in order; equal for equal arguments."""
    return [design(seed, index, modules) for index in range(count)]


def features(found: Sequence[Design]) -> dict[str, int]:
    """How many of ``found`` hold each feature the acceptance set asks for."""
    counts = {"units": 0, "pad_map": 0, "no_connect": 0, "power": 0, "slash": 0, "module": 0, "open": 0}
    for made in found:
        model = to_model(made)
        circuit = model.circuit
        marked = {(m.component_id, m.pin) for m in circuit.no_connects}
        joined = {(m.component_id, m.pin) for net in circuit.nets for m in net.members}
        counts["units"] += any(c.lib_symbol_ref == "Mini:Mini_DualGate" for c in circuit.components)
        counts["pad_map"] += any(c.pin_pad_map for c in circuit.components)
        counts["no_connect"] += bool(marked)
        counts["power"] += any(itf.kind == "power" for itf in circuit.interfaces)
        counts["slash"] += any("/" in net.name for net in circuit.nets)
        counts["module"] += any("/" in path for path in made.parts)
        counts["open"] += len(joined | marked) < sum(len(k.pins) for k in _kinds_of(made))
    return counts


def _kinds_of(made: Design) -> list[Kind]:
    by_symbol = {kind.symbol: kind for kind in KINDS}
    return [by_symbol[part.lib_id] for part in made.parts.values()]


__all__ = ["COUNT", "KINDS", "MODULE_SEED", "SEED", "design", "designs", "features"]
