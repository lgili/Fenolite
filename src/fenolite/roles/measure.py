# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The measures of the net roles, taken by the analyses of ``fenolite.analysis`` (change c0222; capability
net-roles, "Role measures come from the analyses"; ``docs/roles.md``, "What measures what").

Phase 0 writes no measuring kernel: this module turns the roles into the inputs of the analyses (derived
``[[loop]]``, ``[[neck]]`` and path rows, the victim and reference nets), calls them on the ``Design`` that a
backend gives, and hands their rows to ``fenolite.roles.checks``. Every measure names the analysis and the
copper state (``saved_fill``, ``simulated``, ``outline``, or ``tracks`` for nets without a zone) it came
from. The analyses' own input warnings pass through unchanged, except the inputs of the capacity fit when no
temperature rise is given: the rule of thumb then judges, and needs none of them.

| role measure | analysis |
|---|---|
| hot loop, gate loop, Kelvin pair area | ``shapes.loop_areas``, one row per group |
| current of tracks, fills and via groups | ``power.analyze_power`` and ``network.path_network`` |
| share of a parallel element | ``split.analyze_split`` with ``--split`` |
| pour narrowings of a power net | ``shapes.analyze_necks``, one row of the required width |
| copper near switching copper | ``analyze_distances``, ``analyze_returns``, ``analyze_coupling`` |
| return gaps of gate and sensitive nets | ``returns.analyze_returns`` with the ground nets as reference |
| a sense net of its own that touches other copper | ``ties.analyze_ties`` with ``sense`` |
| high-voltage distances | ``distance.analyze_distances`` with the user's rows |
| Kelvin attachment, gate return | ``network.path_network`` and the walk of ``roles.kelvin`` |
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from fenolite.analysis.boundary import BoardBoundary, board_boundary
from fenolite.analysis.copper import ARC_TOL_NM, NetCopper, net_copper
from fenolite.analysis.coupling import analyze_coupling
from fenolite.analysis.distance import analyze_distances
from fenolite.analysis.network import path_network
from fenolite.analysis.pour import DEFAULT_GRID_NM, PourCopper, covers, pour_copper
from fenolite.analysis.power import PathElement, PowerReport, analyze_power
from fenolite.analysis.report import LOWERING, DistanceRow
from fenolite.analysis.requirements import LoopReq, NeckReq, NetSelector, Requirements
from fenolite.analysis.returns import analyze_returns
from fenolite.analysis.shapes import NeckRow, analyze_necks, loop_areas
from fenolite.analysis.split import analyze_split
from fenolite.analysis.ties import analyze_ties
from fenolite.backends.base import BoardPad
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import area2
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.rules import GateLoop, KelvinPair, NetRole, RoleSet
from fenolite.roles import profile
from fenolite.roles.classify import Classified
from fenolite.roles.kelvin import Attachment, gate_return, kelvin_attachments, pad_name

ANALYSES = (
    "loop_areas",
    "analyze_power",
    "analyze_split",
    "analyze_necks",
    "analyze_distances",
    "analyze_returns",
    "analyze_coupling",
    "analyze_ties",
    "path_network",
)
"""The functions of ``fenolite.analysis`` that measure roles; a measure names one of them."""
CURRENT_KINDS = ("power", "switch_node", "ground")
FIT_INPUTS = ("temperature rise", "copper thickness", "via plating")
ROUNDING_NM = 1000
"""An overlap of a victim with switching fills below a micrometre is the rounding of the span ends of
``analyze_returns`` (rounded outward), not copper over copper."""
"""The inputs of the capacity fit; without a rise, ``analyze_power``'s warnings about them are not passed."""


@dataclass(frozen=True, slots=True)
class Inputs:
    """The measuring options that ``fenolite roles --check`` shares with ``fenolite analyze``."""

    requirements: Requirements | None = None
    temp_rise_mk: int | None = None
    copper_thickness: Mapping[str, Nm] | None = None
    via_plating: Nm | None = None
    board_thickness: Nm | None = None
    pour_grid: Nm | None = None
    split: bool = False
    arc_tol: int = ARC_TOL_NM


@dataclass(frozen=True, slots=True)
class Measure:
    """One measure: what (``kind``: ``loop``, ``path``, ``neck``, ``near``, ``return``, ``distance``,
    ``sense``, ``attachment``, ``gate_return``), of what (``subject``, a group or a net), by which analysis,
    on which copper states, and its values (integers, texts and lists of them)."""

    kind: str
    subject: str
    analysis: str
    copper: tuple[str, ...]
    values: Mapping[str, Any] = field(default_factory=lambda: {})

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "analysis": self.analysis,
            "copper": list(self.copper),
            "values": dict(self.values),
        }


@dataclass(frozen=True, slots=True)
class RoleBoard:
    """What the measures read: the board model, its pads in the board frame, the resolved roles (with their
    currents), the part classes, and the circuit to read pins from."""

    design: Design
    pads: tuple[BoardPad, ...]
    roles: RoleSet
    classes: Mapping[str, Classified]


@dataclass(slots=True)
class Measured:
    """Every measure, the attachments, the issues the analyses gave (to pass through), and the evidences."""

    measures: list[Measure] = field(default_factory=lambda: [])
    attachments: list[tuple[KelvinPair, tuple[Attachment, ...]]] = field(default_factory=lambda: [])
    returns: list[tuple[GateLoop, Attachment]] = field(default_factory=lambda: [])
    issues: list[Issue] = field(default_factory=lambda: [])
    evidences: list[Evidence] = field(default_factory=lambda: [])
    analyses: set[str] = field(default_factory=lambda: set())


def glob_escape(name: str) -> str:
    """A glob that matches the net name ``name`` only."""
    return "".join(f"[{char}]" if char in "*?[]" else char for char in name)


# --- pads, nets and power pads ------------------------------------------------------------------------------


def pad_nets(pads: Sequence[BoardPad]) -> dict[str, str | None]:
    return {pad_name(record): record.net for record in pads}


def _pin_of(component: Component | None, pad: str) -> str:
    if component is None:
        return pad
    for pin, number in component.pin_pad_map:
        if number == pad:
            return pin
    return pad


def power_pads(board: RoleBoard) -> dict[str, tuple[str, ...]]:
    """The power pads of each net: the pads of transistors' drains and sources, of inductors, connectors and
    shunts (a four-terminal shunt's force pads), and of the capacitors of the hot loops."""
    components = {component.ref: component for component in board.design.circuit.components}
    hot = {pad for loop in board.roles.loops for pad in loop.pads}
    found: dict[str, list[str]] = defaultdict(list)
    for record in board.pads:
        if record.net is None:
            continue
        name = pad_name(record)
        found_class = board.classes.get(record.ref)
        cls = found_class.cls if found_class is not None else "other"
        pin = _pin_of(components.get(record.ref), record.number)
        keep = False
        if cls == "transistor" and found_class is not None:
            keep = pin in (*found_class.pins("drain"), *found_class.pins("source"))
        elif cls in ("inductor", "connector"):
            keep = True
        elif cls == "shunt" and found_class is not None:
            keep = pin in found_class.pins("force") if found_class.pins("force") else True
        elif cls == "capacitor":
            keep = name in hot
        if keep:
            found[record.net].append(name)
    return {net: tuple(sorted(set(names))) for net, names in found.items()}


def classes_of(board: RoleBoard, net: str) -> dict[str, list[str]]:
    """The power pads of ``net`` by the class of their part."""
    found: dict[str, list[str]] = defaultdict(list)
    for name in power_pads(board).get(net, ()):
        ref = name.rpartition("-")[0]
        found_class = board.classes.get(ref)
        found[found_class.cls if found_class is not None else "other"].append(name)
    return found


def copper_states(pour: PourCopper, nets: Sequence[str]) -> tuple[str, ...]:
    states = sorted({state for net in nets for state in pour.states_of(net)})
    return tuple(states) or ("tracks",)


# --- loops --------------------------------------------------------------------------------------------------


def _group_net(names: Sequence[str], nets: Mapping[str, str | None], roles: RoleSet, kind: str) -> str | None:
    """The net of a group for its limits: the first net of its pads whose role is ``kind``."""
    for name in names:
        net = nets.get(name)
        role = roles.role_of(net) if net is not None else None
        if role is not None and role.kind == kind:
            return net
    return None


def measure_loops(board: RoleBoard, pour: PourCopper, done: Measured) -> None:
    """One derived ``[[loop]]`` row per hot loop, gate loop and Kelvin pair, measured by ``loop_areas``, with
    the placement bound and the open legs."""
    groups: list[tuple[str, str, tuple[str, ...], str | None]] = []
    nets = pad_nets(board.pads)
    for loop in board.roles.loops:
        groups.append(("hot", loop.name, loop.pads, _group_net(loop.pads, nets, board.roles, "switch_node")))
    for gate in board.roles.gates:
        groups.append(("gate", gate.name, gate.pads, nets.get(gate.gate)))
    for pair in board.roles.kelvins:
        groups.append(("kelvin", pair.name, pair.pads, None))
    if not groups:
        return
    rows = tuple(LoopReq(f"{kind}:{name}", pads) for kind, name, pads, _ in groups)
    measured, issues = loop_areas(
        board.design, pads=board.pads, pour=pour, requirements=Requirements(loops=rows)
    )
    done.issues += issues
    done.analyses.add("loop_areas")
    positions = {pad_name(record): record.position for record in board.pads}
    for (kind, name, pads, net), row in zip(groups, measured, strict=True):
        known = [positions.get(pad) for pad in pads]
        bound = (
            abs(area2([point for point in known if point is not None])) // 2 if None not in known else None
        )
        open_legs = [
            [leg.start, leg.end]
            for leg in row.legs
            if leg.kind == "straight"
            and nets.get(leg.start) is not None
            and nets.get(leg.start) == nets.get(leg.end)
        ]
        legs = [[leg.start, leg.end, leg.kind, leg.length] for leg in row.legs]
        loop_nets = sorted({found for pad in pads if (found := nets.get(pad)) is not None})
        values: dict[str, Any] = {
            "group": kind,
            "pads": list(pads),
            "area_nm2": row.area_nm2,
            "bound_nm2": bound,
            "ratio_permille": None if row.area_nm2 is None or not bound else row.area_nm2 * 1000 // bound,
            "legs": legs,
            "open": open_legs,
            "net": net,
        }
        done.measures.append(Measure("loop", name, "loop_areas", copper_states(pour, loop_nets), values))


# --- current ------------------------------------------------------------------------------------------------


def _rise(board: RoleBoard, role: NetRole, inputs: Inputs) -> tuple[int | None, str]:
    """The temperature rise for a role's current and where it comes from: a role limit, the option, then the
    ``[[current]]`` row of the requirements file; ``None`` without one (the rule of thumb judges)."""
    limit = profile.resolve("temp_rise_mk", board.roles.limits, net=role.net, kind=role.kind)
    if limit.value is not None:
        return limit.value, "override"
    if inputs.temp_rise_mk is not None:
        return inputs.temp_rise_mk, "requirements"
    requirements = inputs.requirements
    net = next((found for found in board.design.circuit.nets if found.name == role.net), None)
    row = requirements.current_for(net, board.design.circuit) if requirements is not None and net else None
    return (row.temp_rise_mk, "requirements") if row is not None else (None, "profile")


def _paths(
    board: RoleBoard, role: NetRole, inputs: Inputs
) -> tuple[list[tuple[tuple[str, ...], tuple[str, ...]]], str]:
    """The paths of a role net: its ``[[path]]`` rows, else one derived path from its connector and inductor
    pads (else its shunt's pads) to its other power pads (a net of switches only: from the first switch's
    pad to the others; of connectors only: from the first connector's pad to the others), else none (its
    tracks are then judged one by one)."""
    nets = pad_nets(board.pads)
    rows = inputs.requirements.paths if inputs.requirements is not None else ()
    given = [
        (row.start, row.end)
        for row in rows
        if any(nets.get(pad) == role.net for pad in (*row.start, *row.end))
    ]
    if given:
        return given, "requirements"
    by_class = classes_of(board, role.net)
    start = tuple(sorted(by_class.get("connector", []) + by_class.get("inductor", [])))
    end = tuple(
        sorted(by_class.get("transistor", []) + by_class.get("shunt", []) + by_class.get("capacitor", []))
    )
    if not start:  # a net between a switch and its shunt: the shunt feeds it
        start = tuple(sorted(by_class.get("shunt", [])))
        end = tuple(sorted(by_class.get("transistor", []) + by_class.get("capacitor", [])))
    if not start and len(end) > 1:  # a net between switches only: from the first to the others
        start, end = end[:1], end[1:]
    if start and not end and len(start) > 1:  # a net between connectors only: from the first to the others
        start, end = start[:1], start[1:]
    if start and end:
        return [(start, end)], "derived"
    return [], "tracks"


def measure_currents(board: RoleBoard, pour: PourCopper, inputs: Inputs, done: Measured) -> None:
    """The elements of the paths of each role with a current, with what each method needs: the width of a
    track or arc, the narrowest section of a fill, the vias of a via group, and with a rise the capacity by
    the fit; with ``--split`` the share of each element. The pours of each such net are screened by
    ``analyze_necks`` at the rule-of-thumb width."""
    for role in board.roles.nets:
        if role.kind not in CURRENT_KINDS or role.milliamps is None:
            continue
        rise, rise_source = _rise(board, role, inputs)
        paths, path_source = _paths(board, role, inputs)
        per_amp = profile.resolve("width_per_amp_nm", board.roles.limits, net=role.net, kind=role.kind)
        per_via = profile.resolve("milliamps_per_via", board.roles.limits, net=role.net, kind=role.kind)
        width = (per_amp.value or 0) * role.milliamps // 1000
        states = copper_states(pour, [role.net])
        if not paths:
            _per_track(board, role, width, per_amp, done, states)
        active: set[str] | None = None if not paths else set()
        for start, end in paths:
            report = analyze_power(
                board.design,
                pads=board.pads,
                paths=((start, end),),
                temp_rise_mk=rise,
                copper_thickness=inputs.copper_thickness,
                via_plating=inputs.via_plating,
                arc_tol=inputs.arc_tol,
            )
            done.analyses.add("analyze_power")
            passed = [
                found
                for found in report.issues
                if rise is not None
                or not (found.code == "analysis.input-missing" and found.where in FIT_INPUTS)
            ]
            done.issues += passed
            evidence = report.evidence
            if rise is None and not any(found.code in LOWERING for found in passed):
                # the rule of thumb needs none of the fit's inputs: their absence leaves nothing out
                evidence = Evidence(Level.INFERRED, hypotheses=evidence.hypotheses)
            done.evidences.append(evidence)
            network = path_network(
                board.design, pads=board.pads, start=start, end=end, arc_tol=inputs.arc_tol
            )
            if active is not None:
                active.update(
                    entity
                    for element in network.elements
                    if element.active and element.kind == "fill"
                    for entity in element.entity_ids
                )
            widths = {element.where: element.width for element in network.elements}
            vias = {group.where: len(group.vias) for group in network.groups}
            ports = {use.region.where: len(use.active_ports) for use in network.regions}
            shares = _shares(board, pour, report, inputs, done) if inputs.split and rise is not None else {}
            for row in report.rows:
                for element in row.elements:
                    done.measures.append(
                        Measure(
                            "path",
                            role.net,
                            "analyze_split" if element.where in shares else "analyze_power",
                            states,
                            _element_values(
                                element,
                                widths,
                                vias,
                                ports,
                                shares,
                                role,
                                rise,
                                rise_source,
                                width,
                                per_amp,
                                per_via,
                                path_source,
                                start,
                                end,
                            ),  # fmt: skip
                        )
                    )
        _necks(board, pour, role, width, per_amp, done, states, active)


def _element_values(
    element: PathElement,
    widths: Mapping[str, int | None],
    vias: Mapping[str, int],
    ports: Mapping[str, int],
    shares: Mapping[str, int],
    role: NetRole,
    rise: int | None,
    rise_source: str,
    width: int,
    per_amp: profile.Limit,
    per_via: profile.Limit,
    path_source: str,
    start: tuple[str, ...],
    end: tuple[str, ...],
) -> dict[str, Any]:
    count = vias.get(element.where) if element.kind == "via-group" else None
    share = shares.get(element.where)
    return {
        "element": element.kind,
        "where": element.where,
        "layer": element.layer,
        "series": element.series,
        "two_ports": ports.get(element.where, 2) == 2 if element.kind == "fill" else None,
        "hull_free": element.hull_free,
        "width": widths.get(element.where) if element.kind in ("track", "arc") else None,
        "section": element.section.low if element.section is not None else None,
        "vias": count,
        "capacity_ma": element.capacity_ma,
        "share_ma": None if share is None else share * role.milliamps // 1000 if role.milliamps else None,
        "milliamps": role.milliamps,
        "method": "fit" if rise is not None else "rule-of-thumb",
        "temp_rise_mk": rise,
        "rise_source": rise_source if rise is not None else None,
        "required_width": width,
        "required_vias": -(-(role.milliamps or 0) // per_via.value) if per_via.value else None,
        "width_limit": per_amp.text(),
        "via_limit": per_via.text(),
        "path": [list(start), list(end)],
        "path_source": path_source,
    }


def _shares(
    board: RoleBoard, pour: PourCopper, report: PowerReport, inputs: Inputs, done: Measured
) -> dict[str, int]:
    """The share (per mille) of each element of ``report``'s path by ``analyze_split``, by ``where``; a via
    group takes the sum of its vias."""
    split = analyze_split(
        board.design,
        pads=board.pads,
        pour=pour,
        power=report,
        copper_thickness=inputs.copper_thickness,
        via_plating=inputs.via_plating,
    )
    done.analyses.add("analyze_split")
    done.evidences.append(split.evidence)
    done.issues += split.issues
    found: dict[str, int] = {}
    for row in split.rows:
        for element in row.elements:
            if element.share_permille is not None:
                found[element.where] = found.get(element.where, 0) + element.share_permille
    return found


def _per_track(
    board: RoleBoard,
    role: NetRole,
    width: int,
    per_amp: profile.Limit,
    done: Measured,
    states: tuple[str, ...],
) -> None:
    """A role net without a path: each of its tracks and arcs by its width (the network of its pads gives
    them); no section or via is judged."""
    design = board.design
    assert design.board is not None
    net_id = next((net.id for net in design.circuit.nets if net.name == role.net), None)
    items = [
        (item.id, item.layer, item.width, "track") for item in design.board.tracks if item.net_id == net_id
    ]
    items += [(item.id, item.layer, item.width, "arc") for item in design.board.arcs if item.net_id == net_id]
    for entity, layer, item_width, kind in items:
        done.measures.append(
            Measure(
                "path",
                role.net,
                "analyze_power",
                states,
                {
                    "element": kind,
                    "where": entity,
                    "layer": layer,
                    "series": True,
                    "two_ports": None,
                    "hull_free": True,
                    "width": item_width,
                    "section": None,
                    "vias": None,
                    "capacity_ma": None,
                    "share_ma": None,
                    "milliamps": role.milliamps,
                    "method": "rule-of-thumb",
                    "temp_rise_mk": None,
                    "rise_source": None,
                    "required_width": width,
                    "required_vias": None,
                    "width_limit": per_amp.text(),
                    "via_limit": "",
                    "path": [],
                    "path_source": "tracks",
                },
            )
        )


def _necks(
    board: RoleBoard,
    pour: PourCopper,
    role: NetRole,
    width: int,
    per_amp: profile.Limit,
    done: Measured,
    states: tuple[str, ...],
    active: set[str] | None,
) -> None:
    """Screen the pours of ``role`` at the rule-of-thumb ``width``; with paths, only the fills that carry
    their current (``active``, the zone ids of the active fills of ``path_network``): a plane that only
    touches the net elsewhere carries none of it."""
    if width <= 0 or not any(zone.net == role.net for zone in pour.zones):
        return
    rows = (NeckReq(NetSelector(net=glob_escape(role.net)), width),)
    report = analyze_necks(board.design, pour=pour, requirements=Requirements(necks=rows))
    done.analyses.add("analyze_necks")
    done.evidences.append(report.evidence)
    done.issues += [found for found in report.issues if found.code not in ("analysis.neck-narrow",)]
    fills = [
        shape
        for shape in pour.copper.by_net.get(role.net, ())
        if shape.kind == "fill" and (active is None or shape.entity_id in active)
    ]
    for row in report.rows:
        assert isinstance(row, NeckRow)
        if active is not None and not any(
            shape.layer == row.layer and covers(shape.shape, row.at) for shape in fills
        ):
            continue
        done.measures.append(
            Measure(
                "neck",
                role.net,
                "analyze_necks",
                states,
                {
                    "shape": row.shape,
                    "layer": row.layer,
                    "at": [row.at.x, row.at.y],
                    "width": row.width,
                    "required_width": width,
                    "extent": row.extent,
                    "milliamps": role.milliamps,
                    "width_limit": per_amp.text(),
                },
            )
        )


# --- attachments --------------------------------------------------------------------------------------------


def measure_attachments(board: RoleBoard, copper: NetCopper, inputs: Inputs, done: Measured) -> None:
    """The Kelvin attachment of each sense pad and the return of each gate loop (``roles.kelvin`` on
    ``path_network``)."""
    pads_of = power_pads(board)
    nets = pad_nets(board.pads)
    for pair in board.roles.kelvins:
        found = kelvin_attachments(
            board.design, board.pads, pair, copper=copper, power_pads=pads_of, arc_tol=inputs.arc_tol
        )
        done.attachments.append((pair, found))
        done.analyses.add("path_network")
        for attachment in found:
            done.measures.append(
                Measure(
                    "attachment",
                    pair.name,
                    "path_network",
                    ("tracks",) if attachment.net is None else _states_or_tracks(copper, attachment.net),
                    {
                        "pad": attachment.pad,
                        "net": attachment.net,
                        "points": [[point.x, point.y] for point in attachment.points],
                        "offsets": list(attachment.offsets),
                        "shared": list(attachment.shared),
                        "starts": list(attachment.starts),
                    },
                )
            )
    for gate in board.roles.gates:
        switch = gate.source.rpartition("-")[0]
        found_class = board.classes.get(switch)
        source_net = nets.get(gate.source)
        sources = [name for name in pads_of.get(source_net or "", ()) if name.rpartition("-")[0] == switch]
        power_source = sources[0] if sources else gate.source
        if found_class is not None and not found_class.pins("kelvin_source"):
            power_source = gate.source
        attachment = gate_return(
            board.design,
            board.pads,
            gate,
            copper=copper,
            power_pads=pads_of,
            power_source=power_source,
            stops=tuple(other.source for other in board.roles.gates if other.name != gate.name),
            arc_tol=inputs.arc_tol,
        )
        done.returns.append((gate, attachment))
        done.analyses.add("path_network")
        done.measures.append(
            Measure(
                "gate_return",
                gate.name,
                "path_network",
                ("tracks",) if attachment.net is None else _states_or_tracks(copper, attachment.net),
                {
                    "pad": attachment.pad,
                    "net": attachment.net,
                    "power_source": power_source,
                    "points": [[point.x, point.y] for point in attachment.points],
                    "shared": list(attachment.shared),
                    "starts": list(attachment.starts),
                },
            )
        )


def _states_or_tracks(copper: NetCopper, net: str) -> tuple[str, ...]:
    """``saved_fill`` when the net has stored fills in the copper the walk read, else ``tracks``."""
    return (
        ("saved_fill",) if any(shape.kind == "fill" for shape in copper.by_net.get(net, ())) else ("tracks",)
    )


# --- near switching -----------------------------------------------------------------------------------------


def _subset(
    design: Design, pads: Sequence[BoardPad], net: str, branch: set[str], starts: set[str]
) -> tuple[Design, tuple[BoardPad, ...]]:
    """``design`` with the copper of ``net`` cut down to the tracks, arcs and vias of ``branch``, and the pads
    of ``net`` to ``starts``: the copper of a sense branch that is no net of its own."""
    board = design.board
    assert board is not None
    net_id = next((found.id for found in design.circuit.nets if found.name == net), None)

    def keep(item: Any) -> bool:
        return item.net_id != net_id or item.id in branch

    trimmed = replace(
        board,
        tracks=tuple(item for item in board.tracks if keep(item)),
        arcs=tuple(item for item in board.arcs if keep(item)),
        vias=tuple(item for item in board.vias if keep(item)),
        zones=tuple(zone for zone in board.zones if zone.net_id != net_id),
    )
    kept = tuple(record for record in pads if record.net != net or pad_name(record) in starts)
    return replace(design, board=trimmed), kept


def _two_nets(
    design: Design, pads: Sequence[BoardPad], nets: set[str]
) -> tuple[Design, tuple[BoardPad, ...]]:
    """``design`` and ``pads`` with the copper of ``nets`` only: the gaps between two nets on a layer do not
    depend on other copper, whose conductors would only lengthen the search for a creepage path that the
    switching check does not read."""
    board = design.board
    assert board is not None
    ids = {found.id for found in design.circuit.nets if found.name in nets}
    trimmed = replace(
        board,
        tracks=tuple(item for item in board.tracks if item.net_id in ids),
        arcs=tuple(item for item in board.arcs if item.net_id in ids),
        vias=tuple(item for item in board.vias if item.net_id in ids),
        zones=tuple(zone for zone in board.zones if zone.net_id in ids),
    )
    return replace(design, board=trimmed), tuple(record for record in pads if record.net in nets)


def _switches_of(board: RoleBoard, node: str) -> set[str]:
    """The transistors with a drain or a source on the switch node ``node``."""
    nets = pad_nets(board.pads)
    found: set[str] = set()
    for name in power_pads(board).get(node, ()):
        ref = name.rpartition("-")[0]
        found_class = board.classes.get(ref)
        if found_class is not None and found_class.cls == "transistor" and nets.get(name) == node:
            found.add(ref)
    return found


def victims(board: RoleBoard, done: Measured) -> list[tuple[str, str, set[str] | None, set[str], str]]:
    """The victims of the switching check: ``(label, net, branch items or None for the whole net, branch
    start pads, why)``; each Kelvin branch (a separate sense net whole, else the branch's copper), each gate
    net (judged against the nodes of other switches), and each sensitive signal."""
    found: list[tuple[str, str, set[str] | None, set[str], str]] = []
    whole = {role.net for role in board.roles.nets if role.kind == "kelvin"}
    for net in sorted(whole):
        found.append((net, net, None, set(), "kelvin"))
    for pair, attachments in done.attachments:
        for attachment in attachments:
            if attachment.net is None or attachment.net in whole:
                continue
            label = f"{pair.name}:{attachment.pad}"
            found.append((label, attachment.net, set(attachment.branch), set(attachment.starts), "kelvin"))
    for role in board.roles.nets:
        if role.kind == "gate":
            found.append((role.net, role.net, None, set(), "gate"))
        elif role.kind == "signal" and role.sensitive:
            found.append((role.net, role.net, None, set(), "sensitive"))
    return found


def _gate_switches(board: RoleBoard, net: str) -> set[str]:
    nets = pad_nets(board.pads)
    found: set[str] = set()
    for gate in board.roles.gates:
        if net in (nets.get(gate.gate), nets.get(gate.drive)) or any(
            nets.get(p) == net for p in gate.resistor
        ):
            found.add(gate.gate.rpartition("-")[0])
    for record in board.pads:
        found_class = board.classes.get(record.ref)
        if record.net == net and found_class is not None and record.number in found_class.pins("gate"):
            found.add(record.ref)
    return found


def measure_switching(
    board: RoleBoard, pour: PourCopper, boundary: BoardBoundary, inputs: Inputs, done: Measured
) -> None:
    """For each victim and each switch node: the least gap on a layer (``analyze_distances``), the length
    over the node's fills on a neighbouring layer (``analyze_returns`` with the node as reference) and the
    broadside overlap of tracks (``analyze_coupling``). A gate net is no victim of its own switch's node."""
    nodes = sorted(role.net for role in board.roles.nets if role.kind == "switch_node")
    if not nodes:
        return
    for label, net, branch, starts, why in victims(board, done):
        if branch is not None and not branch:
            continue
        design, pads = board.design, board.pads
        if branch is not None:
            design, pads = _subset(board.design, board.pads, net, branch, starts)
        own: set[str] = _gate_switches(board, net) if why == "gate" else set()
        for node in nodes:
            if node == net or (own and own & _switches_of(board, node)):
                continue
            pair_design, pair_pads = _two_nets(design, pads, {net, node})
            distances = analyze_distances(
                pair_design, pads=pair_pads, boundary=boundary, pairs=((net, node),), arc_tol=inputs.arc_tol
            )
            returns = analyze_returns(
                design, pads=pads, nets=(glob_escape(net),), reference=(node,), arc_tol=inputs.arc_tol
            )
            coupling = analyze_coupling(
                design,
                pads=pads,
                aggressors=(glob_escape(node),),
                victims=(glob_escape(net),),
                board_thickness=boundary.thickness,
                arc_tol=inputs.arc_tol,
            )
            done.analyses |= {"analyze_distances", "analyze_returns", "analyze_coupling"}
            done.evidences += [distances.evidence, returns.evidence, coupling.evidence]
            gaps: list[tuple[int, str]] = []
            for row in distances.rows:
                if isinstance(row, DistanceRow):
                    gaps += [(gap.low, gap.layer) for gap in row.gaps]
            over = sum(row.length - row.unreferenced for row in returns.rows)
            over = over if over >= ROUNDING_NM else 0
            broadside = sum(row.broadside for row in coupling.rows)
            score = max((row.score or 0 for row in coupling.rows), default=None)
            least = min(gaps) if gaps else None
            done.measures.append(
                Measure(
                    "near",
                    label,
                    "analyze_distances",
                    copper_states(pour, [net, node]),
                    {
                        "net": net,
                        "node": node,
                        "victim": why,
                        "gap": None if least is None else least[0],
                        "layer": None if least is None else least[1],
                        "over_fill": over,
                        "broadside": broadside,
                        "score": score,
                        "analyses": ["analyze_distances", "analyze_returns", "analyze_coupling"],
                    },
                )
            )


# --- returns, high voltage and sense nets -------------------------------------------------------------------


def measure_returns(board: RoleBoard, pour: PourCopper, inputs: Inputs, done: Measured) -> None:
    """The spans of each gate net and sensitive signal without its ground under it (``analyze_returns`` with
    the ground nets as reference)."""
    grounds = tuple(role.net for role in board.roles.nets if role.kind == "ground")
    if not grounds:
        return
    for role in board.roles.nets:
        if not (role.kind == "gate" or (role.kind == "signal" and role.sensitive)):
            continue
        report = analyze_returns(
            board.design,
            pads=board.pads,
            nets=(glob_escape(role.net),),
            reference=grounds,
            arc_tol=inputs.arc_tol,
        )
        done.analyses.add("analyze_returns")
        done.evidences.append(report.evidence)
        done.issues += [found for found in report.issues if found.code not in ("analysis.return-split",)]
        for row in report.rows:
            spans = [
                {"layer": span.layer, "where": span.where, "start": [span.start.x, span.start.y],
                 "end": [span.end.x, span.end.y], "length": span.length}
                for span in row.spans
                if span.kind == "split"
            ]  # fmt: skip
            done.measures.append(
                Measure(
                    "return",
                    role.net,
                    "analyze_returns",
                    copper_states(pour, [role.net, *grounds]),
                    {
                        "net": role.net,
                        "length": row.length,
                        "unreferenced": row.unreferenced,
                        "splits": spans,
                    },
                )
            )


def high_voltage_nets(board: RoleBoard) -> list[str]:
    """The nets judged for distances as high-voltage nets: ``high_voltage`` roles, and ``power`` roles whose
    working voltage is at or above the ``high_voltage_mv`` in force for them; with no such limit, every
    ``power`` role with a working voltage (the profile ships none: the user's ``working_mv`` decides)."""
    found: list[str] = []
    for role in board.roles.nets:
        if role.kind == "high_voltage":
            found.append(role.net)
        elif role.kind == "power" and role.working_mv is not None:
            limit = profile.resolve("high_voltage_mv", board.roles.limits, net=role.net, kind=role.kind)
            if limit.value is None or role.working_mv >= limit.value:
                found.append(role.net)
    return found


def measure_high_voltage(
    board: RoleBoard, pour: PourCopper, boundary: BoardBoundary, inputs: Inputs, done: Measured
) -> None:
    """For each high-voltage net, the distances to the nets that the user's rows pair it with
    (``analyze_distances``, whose findings keep their codes), or a measure without rows."""
    circuit = board.design.circuit
    nets = {net.name: net for net in circuit.nets}
    requirements = inputs.requirements
    for name in high_voltage_nets(board):
        net = nets.get(name)
        rows = tuple(
            row
            for row in (requirements.distances if requirements is not None else ())
            if net is not None and any(row.matches(net, other, circuit) for other in circuit.nets)
        )
        if not rows or requirements is None:
            done.measures.append(
                Measure(
                    "distance",
                    name,
                    "analyze_distances",
                    copper_states(pour, [name]),
                    {"net": name, "rows": 0},
                )
            )
            continue
        report = analyze_distances(
            board.design,
            pads=board.pads,
            boundary=boundary,
            requirements=Requirements(distances=rows, steps=requirements.steps),
            arc_tol=inputs.arc_tol,
        )
        done.analyses.add("analyze_distances")
        done.evidences.append(report.evidence)
        done.issues += report.issues
        pairs = [
            {
                "net_a": row.net_a,
                "net_b": row.net_b,
                "clearance": None if row.clearance is None else row.clearance.low,
                "creepage": None if row.creepage is None else row.creepage.low,
            }
            for row in report.rows
            if isinstance(row, DistanceRow) and name in (row.net_a, row.net_b)
        ]
        done.measures.append(
            Measure(
                "distance",
                name,
                "analyze_distances",
                copper_states(pour, [name]),
                {"net": name, "rows": len(rows), "pairs": pairs},
            )
        )


def measure_sense(board: RoleBoard, inputs: Inputs, done: Measured) -> None:
    """The separate sense nets of the Kelvin pairs: ``analyze_ties(sense=...)`` gives the copper of another
    net that each one touches."""
    nets = pad_nets(board.pads)
    sense = sorted(
        {
            net
            for pair in board.roles.kelvins
            for pad in pair.element
            if (net := nets.get(pad)) is not None and (role := board.roles.role_of(net)) is not None
            and role.kind == "kelvin"
        }
    )  # fmt: skip
    if not sense:
        return
    report = analyze_ties(board.design, pads=board.pads, sense=tuple(sense), arc_tol=inputs.arc_tol)
    done.analyses.add("analyze_ties")
    done.evidences.append(report.evidence)
    done.issues += [found for found in report.issues if found.code != "analysis.sense-shared"]
    for row in report.sense:
        done.measures.append(
            Measure(
                "sense",
                row.net,
                "analyze_ties",
                ("tracks",),
                {
                    "net": row.net,
                    "items": row.items,
                    "shared": [[item.kind, item.where, item.net] for item in row.shared],
                },
            )
        )


def measure(board: RoleBoard, inputs: Inputs) -> Measured:
    """Every measure of the roles of ``board``."""
    done = Measured()
    design = board.design
    if design.board is None:
        return done
    boundary = board_boundary(design.board, thickness=inputs.board_thickness)
    pour = pour_copper(
        design,
        pads=board.pads,
        boundary=boundary,
        grid=DEFAULT_GRID_NM if inputs.pour_grid is None else inputs.pour_grid,
        arc_tol=inputs.arc_tol,
    )
    copper = net_copper(design, pads=board.pads, arc_tol=inputs.arc_tol)
    measure_loops(board, pour, done)
    measure_currents(board, pour, inputs, done)
    measure_attachments(board, copper, inputs, done)
    measure_sense(board, inputs, done)
    measure_switching(board, pour, boundary, inputs, done)
    measure_returns(board, pour, inputs, done)
    measure_high_voltage(board, pour, boundary, inputs, done)
    done.issues = list(dict.fromkeys(done.issues))
    return done


__all__ = [
    "ANALYSES",
    "CURRENT_KINDS",
    "RoleBoard",
    "Inputs",
    "Measure",
    "Measured",
    "glob_escape",
    "high_voltage_nets",
    "measure",
    "pad_nets",
    "power_pads",
]
