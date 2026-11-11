# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic placement suggestions for oscillators and explicitly typed signal paths."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from fenolite.model.circuit import PinRef
from fenolite.placement.decoupling import Capacitor
from fenolite.placement.topology import Incidence


@dataclass(frozen=True, slots=True)
class OscillatorPort:
    key: str
    input: PinRef
    output: PinRef
    return_pin: PinRef
    source: str


@dataclass(frozen=True, slots=True)
class Resonator:
    component_id: str
    first_pin: str
    second_pin: str
    kind: Literal["crystal", "resonator", "clock_module", "rc"]
    dnp: bool = False


@dataclass(frozen=True, slots=True)
class OscillatorMatch:
    port: OscillatorPort
    resonator_input: Incidence
    resonator_output: Incidence
    input_loads: tuple[tuple[Incidence, Incidence], ...]
    output_loads: tuple[tuple[Incidence, Incidence], ...]


@dataclass(frozen=True, slots=True)
class OscillatorSuggestion:
    component_id: str
    state: Literal["suggested", "ambiguous", "unmatched", "unresolved", "excluded"]
    matches: tuple[OscillatorMatch, ...] = ()
    unresolved_ports: tuple[str, ...] = ()
    rule_version: str = "oscillator-terminals.v0"


def suggest_oscillators(
    incidences: tuple[Incidence, ...],
    ports: tuple[OscillatorPort, ...],
    resonators: tuple[Resonator, ...],
    capacitors: tuple[Capacitor, ...],
) -> tuple[OscillatorSuggestion, ...]:
    """Match resolved terminals and report possible load capacitors on each distinct branch."""
    terminals = {row.terminal: row for row in incidences if row.problem is None and row.pads}
    loads: dict[tuple[str, str], list[tuple[Incidence, Incidence]]] = defaultdict(list)
    for cap in sorted(capacitors, key=lambda row: row.component_id):
        if cap.dnp or cap.function != "unknown":
            continue
        first = terminals.get(PinRef(cap.component_id, cap.first_pin))
        second = terminals.get(PinRef(cap.component_id, cap.second_pin))
        if first is not None and second is not None and first.net_id != second.net_id:
            loads[first.net_id, second.net_id].append((first, second))
            loads[second.net_id, first.net_id].append((second, first))

    port_index: dict[tuple[str, str], list[tuple[OscillatorPort, str]]] = defaultdict(list)
    unresolved: list[str] = []
    for port in sorted(ports, key=lambda row: row.key):
        inp, out, ret = (terminals.get(pin) for pin in (port.input, port.output, port.return_pin))
        if inp is None or out is None or ret is None or len({inp.net_id, out.net_id, ret.net_id}) != 3:
            unresolved.append(port.key)
        else:
            port_index[inp.net_id, out.net_id].append((port, ret.net_id))

    result: list[OscillatorSuggestion] = []
    for part in sorted(resonators, key=lambda row: row.component_id):
        ident = part.component_id
        if part.dnp or part.kind not in ("crystal", "resonator"):
            result.append(OscillatorSuggestion(ident, "excluded"))
            continue
        first = terminals.get(PinRef(ident, part.first_pin))
        second = terminals.get(PinRef(ident, part.second_pin))
        if first is None or second is None:
            result.append(OscillatorSuggestion(ident, "unresolved"))
            continue
        matches = tuple(
            OscillatorMatch(
                port,
                inp,
                out,
                tuple(loads.get((inp.net_id, ret), ())),
                tuple(loads.get((out.net_id, ret), ())),
            )
            for inp, out in ((first, second), (second, first))
            for port, ret in port_index.get((inp.net_id, out.net_id), ())
            if ident not in {port.input.component_id, port.output.component_id, port.return_pin.component_id}
        )
        state = (
            "ambiguous"
            if len(matches) > 1
            or any(len(match.input_loads) > 1 or len(match.output_loads) > 1 for match in matches)
            else "unresolved"
            if unresolved
            else "suggested"
            if matches
            else "unmatched"
        )
        result.append(OscillatorSuggestion(ident, state, matches, tuple(unresolved)))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class SignalPort:
    terminal: PinRef
    direction: Literal["source", "sink", "bidirectional", "unknown"]


@dataclass(frozen=True, slots=True)
class SeriesElement:
    first: PinRef
    second: PinRef
    function: Literal["series", "source_termination"]


@dataclass(frozen=True, slots=True)
class Protection:
    signal: PinRef
    return_pin: PinRef
    reference: PinRef


@dataclass(frozen=True, slots=True)
class SignalPath:
    key: str
    source: SignalPort
    sink: SignalPort
    provenance: str
    series: tuple[SeriesElement, ...] = ()
    protection: tuple[Protection, ...] = ()
    connector: PinRef | None = None


@dataclass(frozen=True, slots=True)
class SignalSuggestion:
    path: SignalPath
    state: Literal["suggested", "ambiguous_direction", "unresolved", "disconnected"]
    links: tuple[tuple[Incidence, Incidence], ...] = ()
    protection_links: tuple[tuple[Incidence, Incidence], ...] = ()
    rule_version: str = "signal-terminal-chain.v0"


def suggest_signal_path(incidences: tuple[Incidence, ...], path: SignalPath) -> SignalSuggestion:
    """Check a declared series order and connector-side protection against resolved nets."""
    if path.source.direction != "source" or path.sink.direction != "sink":
        return SignalSuggestion(path, "ambiguous_direction")
    terminals = {row.terminal: row for row in incidences if row.problem is None and row.pads}
    start = terminals.get(path.source.terminal)
    end = terminals.get(path.sink.terminal)
    if start is None or end is None:
        return SignalSuggestion(path, "unresolved")
    if start.terminal == end.terminal:
        return SignalSuggestion(path, "disconnected")
    links: list[tuple[Incidence, Incidence]] = []
    seen = {start.net_id}
    current = start
    for index, element in enumerate(path.series):
        first, second = terminals.get(element.first), terminals.get(element.second)
        if first is None or second is None:
            return SignalSuggestion(path, "unresolved")
        if (
            first.terminal.component_id != second.terminal.component_id
            or first.net_id == second.net_id
            or (element.function == "source_termination" and index != 0)
        ):
            return SignalSuggestion(path, "disconnected")
        if current.net_id == second.net_id:
            first, second = second, first
        if current.net_id != first.net_id or second.net_id in seen:
            return SignalSuggestion(path, "disconnected")
        links.append((current, first))
        seen.add(second.net_id)
        current = second
    if current.net_id != end.net_id:
        return SignalSuggestion(path, "disconnected")
    links.append((current, end))

    protection_links: list[tuple[Incidence, Incidence]] = []
    connector = terminals.get(path.connector) if path.connector is not None else None
    for protection in path.protection:
        signal = terminals.get(protection.signal)
        ret = terminals.get(protection.return_pin)
        ref = terminals.get(protection.reference)
        if connector is None or signal is None or ret is None or ref is None:
            return SignalSuggestion(path, "unresolved")
        if (
            connector.terminal not in (start.terminal, end.terminal)
            or signal.terminal.component_id != ret.terminal.component_id
            or signal.net_id != connector.net_id
            or ret.net_id != ref.net_id
            or signal.net_id == ret.net_id
        ):
            return SignalSuggestion(path, "disconnected")
        protection_links.extend(((connector, signal), (ret, ref)))
    return SignalSuggestion(path, "suggested", tuple(links), tuple(protection_links))
