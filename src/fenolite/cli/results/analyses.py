# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wire records for analyses results; producers retain their existing payloads."""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.analysis import coupling as coupling_rows
from fenolite.analysis import crossings as crossing_rows
from fenolite.analysis import length as length_rows
from fenolite.analysis import pour as pour_rows
from fenolite.analysis import power as power_rows
from fenolite.analysis import practice as practice_rows
from fenolite.analysis import report as report_rows
from fenolite.analysis import returns as return_rows
from fenolite.analysis import shapes as shape_rows
from fenolite.analysis import split as split_rows
from fenolite.analysis import ties as tie_rows
from fenolite.cli.results import common as wire
from fenolite.cli.results.common import (
    DistanceRow,
    ProtocolResult,
)
from fenolite.core.requirement_table import Corner


@dataclass(frozen=True, kw_only=True)
class AnalyzeInputsBoundary:
    band: int
    cutouts: int
    source: str


@dataclass(frozen=True, kw_only=True)
class AnalyzeInputsStackup:
    copper: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    thickness: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeInputs:
    aggressors: list[str] = field(metadata={"optional": True})
    arc_tol: int
    barriers: list[str] = field(metadata={"optional": True})
    board_thickness: int | None
    board_thickness_source: None | str
    boundary: AnalyzeInputsBoundary
    clearance: int = field(metadata={"optional": True})
    copper_thickness: None | dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    cuts: list[str] = field(metadata={"optional": True})
    dead_distance: int = field(metadata={"optional": True})
    domains: dict[str, list[str]] | None = field(metadata={"optional": True})
    from_: list[str] = field(metadata={"optional": True, "name": "from"})
    groove_nm: int | None
    kicad_version: int = field(metadata={"optional": True})
    kinds: list[str]
    loop_baseline: str = field(metadata={"optional": True})
    nets: list[str] = field(metadata={"optional": True})
    pairs: list[list[str]]
    paths: list[list[list[str]]]
    pour_grid: int = field(metadata={"optional": True})
    reference: list[str] = field(metadata={"optional": True})
    requirements: None | str
    resistivity_pohm_m: int | None
    sense: list[str] = field(metadata={"optional": True})
    split: bool = field(metadata={"optional": True})
    stackup: None | AnalyzeInputsStackup
    temp_rise_mk: int | None
    ties: list[str] = field(metadata={"optional": True})
    via_distance: int | None = field(metadata={"optional": True})
    via_plating: int | None
    victims: list[str] = field(metadata={"optional": True})
    width: int = field(metadata={"optional": True})
    within: int | None


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryBalance:
    one_sided: int
    parts: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryBodies:
    rows: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryConnectivity:
    nets: int
    outline: int
    simulated: int
    split: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryCoupling:
    heights: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    note: str
    pairs: int
    victims: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryCrossings:
    cuts: int
    short: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryCurrentNetsValue:
    capacity_ma: int
    where: str


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryCurrent:
    fit: str
    nets: dict[str, AnalyzeSummaryCurrentNetsValue] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    rows: int
    skipped: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryDead:
    dropped: int
    far: int
    islands: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryDecoupling:
    far: int
    pins: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryDistancesGroovesValue:
    bridged: int
    counted: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryDistances:
    missing: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Missing geometry and stack-up inputs counted by input kind.",
        }
    )
    boundary: str
    faces_alone: int
    grooves: dict[str, AnalyzeSummaryDistancesGroovesValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    pairs: int
    unsupported: dict[str, int]


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryDomains:
    islands: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryLength:
    count_vias: bool | None
    major: int | None
    nets: int
    stackup: None | str


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryLoops:
    above: int
    loops: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryNecks:
    necks: int
    nets: int
    skipped: int
    slivers: int
    tips: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryPower:
    elements: int
    fit: str
    missing: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    paths: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryRelief:
    pads: int
    simulated: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryReturns:
    edge: int
    nets: int
    split: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummarySplit:
    grid: int
    paths: int
    unsolved: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummaryTies:
    sense: int
    shared: int
    split: int
    ties: int


@dataclass(frozen=True, kw_only=True)
class AnalyzeSummary:
    balance: AnalyzeSummaryBalance = field(metadata={"optional": True})
    bodies: AnalyzeSummaryBodies = field(metadata={"optional": True})
    connectivity: AnalyzeSummaryConnectivity = field(metadata={"optional": True})
    coupling: AnalyzeSummaryCoupling = field(metadata={"optional": True})
    crossings: AnalyzeSummaryCrossings = field(metadata={"optional": True})
    current: AnalyzeSummaryCurrent = field(metadata={"optional": True})
    dead: AnalyzeSummaryDead = field(metadata={"optional": True})
    decoupling: AnalyzeSummaryDecoupling = field(metadata={"optional": True})
    distances: AnalyzeSummaryDistances = field(metadata={"optional": True})
    domains: AnalyzeSummaryDomains = field(metadata={"optional": True})
    length: AnalyzeSummaryLength = field(metadata={"optional": True})
    loops: AnalyzeSummaryLoops = field(metadata={"optional": True})
    necks: AnalyzeSummaryNecks = field(metadata={"optional": True})
    power: AnalyzeSummaryPower = field(metadata={"optional": True})
    relief: AnalyzeSummaryRelief = field(metadata={"optional": True})
    returns: AnalyzeSummaryReturns = field(metadata={"optional": True})
    split: AnalyzeSummarySplit = field(metadata={"optional": True})
    ties: AnalyzeSummaryTies = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class AnalyzeResult(ProtocolResult):
    balance: list[shape_rows.BalanceRow] = field(metadata={"optional": True})
    bodies: list[practice_rows.BodyRow] = field(metadata={"optional": True})
    connectivity: list[practice_rows.NetGroups] = field(metadata={"optional": True})
    coupling: list[coupling_rows.CouplingRow] = field(metadata={"optional": True})
    coupling_victims: list[coupling_rows.VictimRow] = field(metadata={"optional": True})
    crossings: list[crossing_rows.CrossingRow] = field(metadata={"optional": True})
    current: list[report_rows.CurrentRow] = field(metadata={"optional": True})
    dead: list[practice_rows.DeadRow] = field(metadata={"optional": True})
    decoupling: list[practice_rows.DecouplingRow] = field(metadata={"optional": True})
    distances: list[DistanceRow] = field(metadata={"optional": True})
    domains: list[tie_rows.Island] = field(metadata={"optional": True})
    inputs: AnalyzeInputs = field(metadata={"optional": True})
    lengths: list[length_rows.LengthRow] = field(metadata={"optional": True})
    loops: list[shape_rows.LoopRow] = field(metadata={"optional": True})
    necks: list[shape_rows.NeckRow] = field(metadata={"optional": True})
    pairs: list[length_rows.PairRow] = field(metadata={"optional": True})
    pours: list[pour_rows.ZoneLayer] = field(metadata={"optional": True})
    power: list[power_rows.PathRow] = field(metadata={"optional": True})
    relief: list[practice_rows.ReliefRow] = field(metadata={"optional": True})
    returns: list[return_rows.ReturnRow] = field(metadata={"optional": True})
    sense: list[tie_rows.SenseRow] = field(metadata={"optional": True})
    split: list[split_rows.SplitRow] = field(metadata={"optional": True})
    summary: AnalyzeSummary = field(metadata={"optional": True})
    ties: list[tie_rows.TieRow] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ImpedanceCounts:
    estimated: int
    left_out: int
    rows: int
    targets: int


@dataclass(frozen=True, kw_only=True)
class ImpedanceRowsItemEstimate:
    form: str
    in_range: bool | None
    mohm: int | None
    reason: str
    suggested_width: int | None


@dataclass(frozen=True, kw_only=True)
class ImpedanceRowsItem:
    classes: list[str]
    epsilon_r: str
    estimate: ImpedanceRowsItemEstimate = field(metadata={"optional": True})
    gap: int | None
    heights: list[int] | None
    kind: str
    layer: str
    nets: list[str]
    ohms: str
    references: list[str]
    structure: str
    target: str
    tolerance_percent: str
    width: int


@dataclass(frozen=True, kw_only=True)
class ImpedanceResult(ProtocolResult):
    columns: list[str] = field(metadata={"optional": True})
    counts: ImpedanceCounts = field(metadata={"optional": True})
    rows: list[ImpedanceRowsItem] = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class NeighborsNeighborsItem:
    distance: int
    overlap: bool
    ref: str
    shared_nets: list[str]
    side: str


@dataclass(frozen=True, kw_only=True)
class NeighborsPartBox:
    x0: int
    x1: int
    y0: int
    y1: int


@dataclass(frozen=True, kw_only=True)
class NeighborsPartPosition:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class NeighborsPart:
    box: NeighborsPartBox
    position: NeighborsPartPosition
    ref: str
    rotation: int
    side: str


@dataclass(frozen=True, kw_only=True)
class NeighborsResult(ProtocolResult):
    neighbors: list[NeighborsNeighborsItem] = field(metadata={"optional": True})
    part: NeighborsPart = field(metadata={"optional": True})
    radius: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class NetNetBox:
    x0: int
    x1: int
    y0: int
    y1: int


@dataclass(frozen=True, kw_only=True)
class NetNetCopperItem:
    arcs: int
    layer: str
    length: int
    tracks: int


@dataclass(frozen=True, kw_only=True)
class NetNetOpenItemAPosition:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class NetNetOpenItemA:
    kind: str
    layers: list[str]
    position: NetNetOpenItemAPosition
    where: str


@dataclass(frozen=True, kw_only=True)
class NetNetOpenItemBPosition:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class NetNetOpenItemB:
    kind: str
    layers: list[str]
    position: NetNetOpenItemBPosition
    where: str


@dataclass(frozen=True, kw_only=True)
class NetNetOpenItem:
    a: NetNetOpenItemA
    b: NetNetOpenItemB
    length: int


@dataclass(frozen=True, kw_only=True)
class NetNetPadsItemPosition:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class NetNetPadsItem:
    layers: list[str]
    position: NetNetPadsItemPosition
    where: str


@dataclass(frozen=True, kw_only=True)
class NetNetViasItemPosition:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class NetNetViasItem:
    diameter: int
    drill: int
    layers: list[str]
    position: NetNetViasItemPosition


@dataclass(frozen=True, kw_only=True)
class NetNetZonesItem:
    filled: bool
    layers: list[str]
    name: str


@dataclass(frozen=True, kw_only=True)
class NetNet:
    box: NetNetBox
    class_: str | None = field(metadata={"name": "class"})
    copper: list[NetNetCopperItem]
    fill_islands: int
    islands: int
    name: str
    open: list[NetNetOpenItem]
    pads: list[NetNetPadsItem]
    vias: list[NetNetViasItem]
    zones: list[NetNetZonesItem]


@dataclass(frozen=True, kw_only=True)
class NetNetsItem:
    class_: str | None = field(metadata={"name": "class"})
    islands: int
    length: int
    name: str
    open: int
    pads: int
    tracks: int
    vias: int
    zones: int


@dataclass(frozen=True, kw_only=True)
class NetResult(ProtocolResult):
    net: NetNet = field(metadata={"optional": True})
    nets: list[NetNetsItem] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class NetlistComponentsItem:
    footprint: str
    properties: dict[str, str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    ref: str
    value: str


@dataclass(frozen=True, kw_only=True)
class NetlistCounts:
    below_min_pins: int
    components: int
    nets: int
    pins: int
    unconnected: int


@dataclass(frozen=True, kw_only=True)
class NetlistNetsItemPinsItem:
    pin: str
    ref: str
    type: str


@dataclass(frozen=True, kw_only=True)
class NetlistNetsItem:
    class_: str = field(metadata={"name": "class"})
    name: str
    pins: list[NetlistNetsItemPinsItem]
    unconnected: bool


@dataclass(frozen=True, kw_only=True)
class NetlistResult(ProtocolResult):
    components: list[NetlistComponentsItem] = field(metadata={"optional": True})
    counts: NetlistCounts = field(metadata={"optional": True})
    nets: list[NetlistNetsItem] = field(metadata={"optional": True})
    schematic: str = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PadsPadsItem:
    box: list[int] | None
    drill: int | None
    index: int
    kind: str
    layers: list[str]
    net: None | str
    number: str
    position: list[int]
    ref: str
    rotation: int
    side: str
    where: str


@dataclass(frozen=True, kw_only=True)
class PadsResult(ProtocolResult):
    count: int = field(metadata={"optional": True})
    origin: list[int] = field(metadata={"optional": True})
    pads: list[PadsPadsItem] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RegionBox:
    x0: int
    x1: int
    y0: int
    y1: int


@dataclass(frozen=True, kw_only=True)
class RegionCounts:
    arc: int = field(metadata={"optional": True})
    footprint: int = field(metadata={"optional": True})
    pad: int = field(metadata={"optional": True})
    text: int = field(metadata={"optional": True})
    track: int
    via: int = field(metadata={"optional": True})
    zone: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RegionItemsItemBox:
    x0: int
    x1: int
    y0: int
    y1: int


@dataclass(frozen=True, kw_only=True)
class RegionItemsItem:
    box: RegionItemsItemBox
    kind: str
    layer: str
    net: None | str
    where: str


@dataclass(frozen=True, kw_only=True)
class RegionResult(ProtocolResult):
    box: RegionBox = field(metadata={"optional": True})
    counts: RegionCounts = field(metadata={"optional": True})
    items: list[RegionItemsItem] = field(metadata={"optional": True})
    layer: None | str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class TestpointsCounts:
    fiducials_bottom: int
    fiducials_top: int
    holes: int
    test_points: int
    tooling_holes: int


@dataclass(frozen=True, kw_only=True)
class TestpointsCoverage:
    covered: int
    eligible: int
    uncovered: list[str]


@dataclass(frozen=True, kw_only=True)
class TestpointsFiducialsItem:
    path: str
    position: list[int]
    ref: str
    scope: str
    side: str
    size: list[int]


@dataclass(frozen=True, kw_only=True)
class TestpointsHolesItem:
    drill: int
    length: int | None
    path: str
    position: list[int]
    ref: str
    tooling: bool


@dataclass(frozen=True, kw_only=True)
class TestpointsTestPointsItem:
    access: str
    drill: int | None
    net: str
    pad: str
    path: str
    position: list[int]
    ref: str
    shape: str
    side: str
    size: list[int]


@dataclass(frozen=True, kw_only=True)
class TestpointsResult(ProtocolResult):
    place: wire.ProbePlacement = field(metadata={"optional": True})
    counts: TestpointsCounts = field(metadata={"optional": True})
    coverage: TestpointsCoverage = field(metadata={"optional": True})
    fiducials: list[TestpointsFiducialsItem] = field(metadata={"optional": True})
    holes: list[TestpointsHolesItem] = field(metadata={"optional": True})
    origin: str = field(metadata={"optional": True})
    side: str = field(metadata={"optional": True})
    template: str = field(metadata={"optional": True})
    test_points: list[TestpointsTestPointsItem] = field(metadata={"optional": True})
    units: str = field(metadata={"optional": True})
    y_axis: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RolesClassesValue:
    class_: str = field(metadata={"name": "class"})
    confidence: str
    evidence: str
    terminals: dict[str, list[str]] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )


@dataclass(frozen=True, kw_only=True)
class RolesGatesItem:
    confidence: str
    drive: str
    gate: str
    name: str
    origin: str
    resistor: list[str]
    ret: str
    rule: str
    source: str


@dataclass(frozen=True, kw_only=True)
class RolesKelvinsItem:
    confidence: str
    element: list[str]
    force: list[str]
    name: str
    origin: str
    receiver: list[str]
    rule: str


@dataclass(frozen=True, kw_only=True)
class RolesLoopsItem:
    confidence: str
    name: str
    origin: str
    pads: list[str]
    rule: str


@dataclass(frozen=True, kw_only=True)
class RolesMeasuresItemValues:
    analyses: list[str] = field(metadata={"optional": True})
    area_nm2: int = field(metadata={"optional": True})
    bound_nm2: int = field(metadata={"optional": True})
    broadside: int = field(metadata={"optional": True})
    capacity_ma: int | None = field(metadata={"optional": True})
    element: str = field(metadata={"optional": True})
    gap: int = field(metadata={"optional": True})
    group: str = field(metadata={"optional": True})
    hull_free: bool = field(metadata={"optional": True})
    items: int = field(metadata={"optional": True})
    layer: str = field(metadata={"optional": True})
    legs: list[list[int | str]] = field(metadata={"optional": True})
    length: int = field(metadata={"optional": True})
    method: str = field(metadata={"optional": True})
    milliamps: int = field(metadata={"optional": True})
    net: None | str = field(metadata={"optional": True})
    node: str = field(metadata={"optional": True})
    offsets: list[int] = field(metadata={"optional": True})
    open: list[tuple[str, str]] = field(metadata={"optional": True})
    over_fill: int = field(metadata={"optional": True})
    pad: str = field(metadata={"optional": True})
    pads: list[str] = field(metadata={"optional": True})
    path: list[list[str]] = field(metadata={"optional": True})
    path_source: str = field(metadata={"optional": True})
    points: list[list[int]] = field(metadata={"optional": True})
    power_source: str = field(metadata={"optional": True})
    ratio_permille: int = field(metadata={"optional": True})
    required_vias: int = field(metadata={"optional": True})
    required_width: int = field(metadata={"optional": True})
    rise_source: str | None = field(metadata={"optional": True})
    score: int = field(metadata={"optional": True})
    section: int | None = field(metadata={"optional": True})
    series: bool = field(metadata={"optional": True})
    share_ma: int | None = field(metadata={"optional": True})
    shared: list[str] = field(metadata={"optional": True})
    splits: list[wire.ReturnSpan] = field(metadata={"optional": True})
    starts: list[str] = field(metadata={"optional": True})
    temp_rise_mk: int | None = field(metadata={"optional": True})
    two_ports: bool | None = field(metadata={"optional": True})
    unreferenced: int = field(metadata={"optional": True})
    via_limit: str = field(metadata={"optional": True})
    vias: int | None = field(metadata={"optional": True})
    victim: str = field(metadata={"optional": True})
    where: str = field(metadata={"optional": True})
    width: int | None = field(metadata={"optional": True})
    width_limit: str = field(metadata={"optional": True})
    zones: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RolesMeasuresItem:
    analysis: str
    copper: list[str]
    kind: str
    subject: str
    values: RolesMeasuresItemValues


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemCornersItem:
    corner: str
    status: str
    text: str


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemLimitRangeHigh:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemLimitRangeLow:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemLimitRange:
    high: RolesRequirementsItemLimitRangeHigh = field(metadata={"optional": True})
    low: RolesRequirementsItemLimitRangeLow = field(metadata={"optional": True})
    unit: str


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemLimit:
    basis: str
    evidence: str
    kind: str
    range: None | RolesRequirementsItemLimitRange
    source: str
    text: str


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemValueOrigin:
    kind: str


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemValueRangeHigh:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemValueRangeLow:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemValueRange:
    high: RolesRequirementsItemValueRangeHigh
    low: RolesRequirementsItemValueRangeLow = field(metadata={"optional": True})
    unit: str


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItemValue:
    basis: str
    origin: RolesRequirementsItemValueOrigin = field(metadata={"optional": True})
    range: RolesRequirementsItemValueRange
    source: str
    text: str


@dataclass(frozen=True, kw_only=True)
class RolesRequirementsItem:
    check: str
    corners: list[RolesRequirementsItemCornersItem]
    decidable: str
    digest: str
    entities: list[str]
    id: str
    limit: RolesRequirementsItemLimit
    missing: str
    quantity: str
    severity: None | str
    status: str
    subject: str
    unit: str
    value: None | RolesRequirementsItemValue
    waiver: str | None


@dataclass(frozen=True, kw_only=True)
class RolesRolesItem:
    confidence: str
    kind: str
    milliamps: int | None
    net: str
    pads: list[str]
    rule: str
    sensitive: bool
    source: str
    working_mv: int | None


@dataclass(frozen=True, kw_only=True)
class RolesStore:
    built: bool
    file: str
    read: None | str


@dataclass(frozen=True, kw_only=True)
class RolesSummaryDeferred:
    route: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItemLimitRangeHigh:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItemLimitRangeLow:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItemLimitRange:
    high: RolesSummaryRequirementsItemLimitRangeHigh = field(metadata={"optional": True})
    low: RolesSummaryRequirementsItemLimitRangeLow = field(metadata={"optional": True})
    unit: str


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItemLimit:
    basis: str
    evidence: str
    kind: str
    range: RolesSummaryRequirementsItemLimitRange
    source: str
    text: str


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItemValueRangeHigh:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItemValueRangeLow:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItemValueRange:
    high: RolesSummaryRequirementsItemValueRangeHigh
    low: RolesSummaryRequirementsItemValueRangeLow = field(metadata={"optional": True})
    unit: str


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItemValue:
    basis: str
    range: RolesSummaryRequirementsItemValueRange
    source: str
    text: str


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRequirementsItem:
    check: str
    corners: list[Corner]
    decidable: str
    digest: str
    entities: list[str]
    id: str
    limit: RolesSummaryRequirementsItemLimit
    missing: str
    quantity: str
    severity: None | str
    status: str
    subject: str
    unit: str
    value: None | RolesSummaryRequirementsItemValue
    waiver: str | None


@dataclass(frozen=True, kw_only=True)
class RolesSummaryRoles:
    declared: int = field(metadata={"optional": True})
    inferred: int


@dataclass(frozen=True, kw_only=True)
class RolesSummary:
    analyses: list[str]
    codes: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    deferred: RolesSummaryDeferred
    measures: int
    requirements: list[RolesSummaryRequirementsItem]
    roles: RolesSummaryRoles


@dataclass(frozen=True, kw_only=True)
class RolesResult(ProtocolResult):
    classes: dict[str, RolesClassesValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    gates: list[RolesGatesItem] = field(metadata={"optional": True})
    kelvins: list[RolesKelvinsItem] = field(metadata={"optional": True})
    loops: list[RolesLoopsItem] = field(metadata={"optional": True})
    measures: list[RolesMeasuresItem] = field(metadata={"optional": True})
    requirements: list[RolesRequirementsItem] = field(metadata={"optional": True})
    roles: list[RolesRolesItem] = field(metadata={"optional": True})
    store: RolesStore = field(metadata={"optional": True})
    summary: RolesSummary = field(metadata={"optional": True})
