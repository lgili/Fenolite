# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Serialized public documents, before unit conversion or parsing into domain objects.

These declarations describe files, not the domain objects returned by their readers. Readers retain
their semantic validation (cross references, ranges, licensing, hashes and dimension grammar). Writers
keep their current IDs until that format is deliberately activated. The generator binds the root
``schema`` property to each target ID; the device and family dialects remain distinct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from fenolite.cli.results import checks, discovery
from fenolite.cli.results.blocks import BlockData
from fenolite.core.errors import Issue
from fenolite.exports.assembly import BomTemplate, CsvOptions, SideNames
from fenolite.importer.source import InputFile, Upgrade
from fenolite.library.items import Depend
from fenolite.model.circuit import Circuit
from fenolite.model.rules import RoleSet, RuleSet
from fenolite.placement.constraints import PlacementConstraints, PlacementObjective
from fenolite.schematic.composition import Attachment, Visible
from fenolite.verify.kit.steps import Step
from fenolite.view.review import ReviewMark

Number = int | float
Pair = tuple[Number, Number]
LengthPair = tuple[str, str]


@dataclass(frozen=True, kw_only=True)
class Document:
    schema: str


@dataclass(frozen=True, kw_only=True)
class NetSelector:
    net: str = ""
    netclass: str = ""


@dataclass(frozen=True, kw_only=True)
class CurrentRequirement:
    select: NetSelector
    milliamps: int = field(metadata={"optional": True})
    temp_rise_mk: int = field(metadata={"optional": True})
    current: str = ""
    temp_rise: str = ""
    source: str = ""


@dataclass(frozen=True, kw_only=True)
class DistanceValues:
    clearance_nm: int = field(metadata={"optional": True})
    creepage_nm: int = field(metadata={"optional": True})
    embedded_nm: int = field(metadata={"optional": True})
    insulation_nm: int = field(metadata={"optional": True})
    clearance: str = ""
    creepage: str = ""
    embedded: str = ""
    insulation: str = ""
    source: str = ""


@dataclass(frozen=True, kw_only=True)
class DistanceRequirement(DistanceValues):
    a: NetSelector
    b: NetSelector
    millivolts: int = field(metadata={"optional": True})
    groove_nm: int = field(metadata={"optional": True})
    voltage: str = ""
    groove: str = ""


@dataclass(frozen=True, kw_only=True)
class DistanceStep(DistanceValues):
    up_to_mv: int = field(metadata={"optional": True})
    up_to: str = ""


@dataclass(frozen=True, kw_only=True)
class PathRequirement:
    from_: list[str] = field(metadata={"name": "from"})
    to: list[str]
    milliamps: int = field(metadata={"optional": True})
    temp_rise_mk: int = field(metadata={"optional": True})
    drop_mv: int = field(metadata={"optional": True})
    current: str = ""
    temp_rise: str = ""
    drop: str = ""
    source: str = ""


@dataclass(frozen=True, kw_only=True)
class DecouplingRequirement:
    parts: str
    max_distance_nm: int = field(metadata={"optional": True})
    max_distance: str = ""
    source: str = ""


@dataclass(frozen=True, kw_only=True)
class BodyCopperRequirement:
    netclass: str
    parts: str
    layers: list[str]
    source: str = ""


@dataclass(frozen=True, kw_only=True)
class NeckRequirement:
    select: NetSelector
    min_width_nm: int = field(metadata={"optional": True})
    min_width: str = ""
    source: str = ""


@dataclass(frozen=True, kw_only=True)
class LoopRequirement:
    name: str
    pads: list[str]
    max_area_nm2: int = field(metadata={"optional": True})
    max_area: str = ""
    source: str = ""


@dataclass(frozen=True, kw_only=True)
class RequirementsFile(Document):
    current: list[CurrentRequirement] = field(default_factory=lambda: [])
    distance: list[DistanceRequirement] = field(default_factory=lambda: [])
    step: list[DistanceStep] = field(default_factory=lambda: [])
    path: list[PathRequirement] = field(default_factory=lambda: [])
    decoupling: list[DecouplingRequirement] = field(default_factory=lambda: [])
    body_copper: list[BodyCopperRequirement] = field(default_factory=lambda: [])
    neck: list[NeckRequirement] = field(default_factory=lambda: [])
    loop: list[LoopRequirement] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class DrawingPage:
    paper: str = "auto"
    portrait: bool = False
    drawing_sheet: str = ""
    text_size: str = ""
    gap: str = ""
    notes_width: str = ""


@dataclass(frozen=True, kw_only=True)
class FabricationDrawing:
    title: str = ""
    tables: list[str] = field(default_factory=lambda: [])
    dimensions: bool = True
    dimension_offset: str = ""
    dimension_precision: int = 2
    notes: list[str] = field(default_factory=lambda: [])
    at: dict[str, LengthPair] = field(
        default_factory=lambda: {}, metadata={"description": "Drawing block name to corner in length units."}
    )


@dataclass(frozen=True, kw_only=True)
class AssemblyDrawing:
    title_top: str = ""
    title_bottom: str = ""
    sides: list[str] = field(default_factory=lambda: [])
    dnp: Literal["crossout", "hide", "show"] = "crossout"
    values: bool = False
    pads: bool = False
    designators: bool = True
    designator_size: str = ""
    notes: list[str] = field(default_factory=lambda: [])
    at: dict[str, LengthPair] = field(
        default_factory=lambda: {}, metadata={"description": "Drawing block name to corner in length units."}
    )


@dataclass(frozen=True, kw_only=True)
class DrawingSpecFile(Document):
    page: DrawingPage = field(default_factory=DrawingPage)
    fab: FabricationDrawing = field(default_factory=FabricationDrawing)
    assembly: AssemblyDrawing = field(default_factory=AssemblyDrawing)


@dataclass(frozen=True, kw_only=True)
class GerberPreset:
    layers: list[str] = field(default_factory=lambda: [])
    protel_extensions: bool = False
    x2: bool = True
    netlist_attributes: bool = True
    aperture_macros: bool = True
    precision: Literal[5, 6] = 6
    subtract_soldermask: bool = False
    use_drill_file_origin: bool = False
    include_border_title: bool = False
    exclude_refdes: bool = False
    exclude_value: bool = False


@dataclass(frozen=True, kw_only=True)
class DrillPreset:
    format: Literal["excellon", "gerber"] = "excellon"
    units: Literal["mm", "in"] = "mm"
    separate_th: bool = True
    mirror_y: bool = False
    minimal_header: bool = False
    origin: Literal["absolute", "plot"] = "absolute"
    zeros: Literal["decimal", "suppressleading", "suppresstrailing", "keep"] = "decimal"
    oval_format: Literal["route", "alternate"] = "route"
    map: Literal["none", "pdf", "gerberx2", "ps", "dxf", "svg"] = "none"
    gerber_precision: Literal[5, 6] = 6


@dataclass(frozen=True, kw_only=True)
class PositionPreset:
    format: Literal["csv", "ascii", "gerber"] = "csv"
    units: Literal["mm", "in"] = "mm"
    side: Literal["front", "back", "both"] = "both"
    exclude_dnp: bool = False
    exclude_fp_th: bool = False
    smd_only: bool = False
    use_drill_file_origin: bool = False
    bottom_negate_x: bool = False


@dataclass(frozen=True, kw_only=True)
class ExportPresetFile(Document):
    gerbers: GerberPreset = field(default_factory=GerberPreset)
    drill: DrillPreset = field(default_factory=DrillPreset)
    pos: PositionPreset = field(default_factory=PositionPreset)


@dataclass(frozen=True, kw_only=True)
class SideRotation:
    sign: Literal[-1, 1] = 1
    offset: Number = 0


@dataclass(frozen=True, kw_only=True)
class FootprintRotation:
    match: str
    offset: Number


@dataclass(frozen=True, kw_only=True)
class RotationRule:
    top: SideRotation = field(default_factory=SideRotation)
    bottom: SideRotation = field(default_factory=SideRotation)
    footprint: list[FootprintRotation] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class PlacementTemplate:
    columns: list[AssemblyColumn] = field(default_factory=lambda: [])
    units: Literal["mm", "in", "mil"] = "mm"
    decimals: int = 4
    rotation_decimals: int = 2
    origin: Literal["page", "outline"] = "page"
    y_axis: Literal["up", "down"] = "up"
    sides: SideNames = field(default_factory=SideNames)
    exclude_dnp: bool = True
    smd_only: bool = False
    rotation: RotationRule = field(default_factory=RotationRule)
    fiducials: bool = True


@dataclass(frozen=True, kw_only=True)
class AssemblyColumn:
    name: str
    field: str


@dataclass(frozen=True, kw_only=True)
class AssemblyTemplateFile(Document):
    csv: CsvOptions = field(default_factory=CsvOptions)
    bom: BomTemplate = field(default_factory=BomTemplate)
    placement: PlacementTemplate = field(default_factory=PlacementTemplate)


@dataclass(frozen=True, kw_only=True)
class PlacementRequestFile(Document):
    constraints: PlacementConstraints = field(default_factory=PlacementConstraints)
    objectives: tuple[PlacementObjective, ...] = ()


@dataclass(frozen=True, kw_only=True)
class ReviewFile(Document):
    marks: tuple[ReviewMark, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Placement:
    x: Number
    y: Number
    rotation: Number = 0
    side: Literal["top", "bottom"] = "top"
    locked: bool = False


@dataclass(frozen=True, kw_only=True)
class PlacementsFile(Document):
    part: dict[str, Placement] = field(
        default_factory=lambda: {},
        metadata={"description": "Component path to pose; lengths in millimetres and angles in degrees."},
    )


@dataclass(frozen=True, kw_only=True)
class EditedValues:
    x: Number = field(metadata={"optional": True})
    y: Number = field(metadata={"optional": True})
    rotation: Number = field(metadata={"optional": True})
    side: Literal["top", "bottom"] = field(metadata={"optional": True})
    ref: str = ""
    value: str = ""
    footprint: str = ""
    description: str = ""
    datasheet: str = ""
    dnp: bool = False
    properties: dict[str, str] = field(
        default_factory=lambda: {}, metadata={"description": "User property name to text."}
    )


@dataclass(frozen=True, kw_only=True)
class OverValues(EditedValues):
    unplaced: Literal[True] = True


@dataclass(frozen=True, kw_only=True)
class PartEdits(EditedValues):
    locked: bool = False
    over: OverValues = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class EditsFile(Document):
    part: dict[str, PartEdits] = field(
        default_factory=lambda: {},
        metadata={"description": "Component path to edited values and their recorded script values."},
    )


@dataclass(frozen=True, kw_only=True)
class LockPin:
    kind: str
    option: str
    alternative: int
    pins: dict[str, str]
    choice: str = ""


@dataclass(frozen=True, kw_only=True)
class LockLibrary:
    index: str
    path: str
    release: str
    spdx: str
    tree: str
    version: str


@dataclass(frozen=True, kw_only=True)
class LockLibraries:
    items: dict[str, LockLibrary] = field(default_factory=lambda: {})


@dataclass(frozen=True, kw_only=True)
class LockFile(Document):
    design: str
    refs: dict[str, str] = field(default_factory=lambda: {})
    picks: dict[str, str | dict[str, str]] = field(
        default_factory=lambda: {},
        metadata={
            "description": "Picked query key to recorded identity; readers validate each supported binding."
        },
    )
    pins: dict[str, LockPin] = field(default_factory=lambda: {})
    blocks: dict[str, str] = field(default_factory=lambda: {})
    library: LockLibraries = field(default_factory=LockLibraries)


@dataclass(frozen=True, kw_only=True)
class BuildLayoutSource:
    folder: str
    name: str


@dataclass(frozen=True, kw_only=True)
class BuildLayout:
    poses: dict[str, tuple[int, int, int] | tuple[int, int, int, str]]
    digest: str
    sources: dict[str, BuildLayoutSource] = field(default_factory=lambda: {})
    files: dict[str, dict[str, str]] = field(default_factory=lambda: {})


@dataclass(frozen=True, kw_only=True)
class BuildSchematic:
    source: str
    file: str


@dataclass(frozen=True, kw_only=True)
class BuildRecordFile(Document):
    design: str
    files: dict[str, str]
    target: int | str = "kicad"
    source: dict[str, str] = field(default_factory=lambda: {})
    layout: BuildLayout = field(metadata={"optional": True})
    schematic: BuildSchematic = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class FileDigest:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, kw_only=True)
class SizedFile:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True, kw_only=True)
class SnapshotFile(Document):
    source: str
    files: list[FileDigest]


@dataclass(frozen=True, kw_only=True)
class RolesFile(Document):
    roles: RoleSet = field(default_factory=RoleSet)


@dataclass(frozen=True, kw_only=True)
class OwnedCopper:
    key: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class RoleCopperFile(Document):
    items: list[OwnedCopper]


@dataclass(frozen=True, kw_only=True)
class BlockFile(Document, BlockData):
    pass


@dataclass(frozen=True, kw_only=True)
class BlockItemFile(Document):
    id: str
    version: str
    namespace: str
    fenolite: str
    record: BlockData


@dataclass(frozen=True, kw_only=True)
class BlockGoldenFile(Document):
    block: str
    version: str | None
    usage: str
    seed: int
    timestamp: str
    circuit: Circuit
    rules: RuleSet


@dataclass(frozen=True, kw_only=True)
class LayoutPart:
    at: LengthPair
    rotation: str
    side: Literal["top", "bottom"]
    footprint: str


@dataclass(frozen=True, kw_only=True)
class LayoutTrack:
    net: str
    start: LengthPair
    end: LengthPair
    width: str
    layer: str
    pads: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class LayoutArc(LayoutTrack):
    mid: LengthPair


@dataclass(frozen=True, kw_only=True)
class LayoutVia:
    net: str
    at: LengthPair
    size: str
    drill: str
    layers: list[str]
    via_type: str = "through"
    pads: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class LayoutHatch:
    orientation: str = ""
    gap: str = ""
    thickness: str = ""
    smoothing_level: int = 0
    smoothing_value: str = ""
    border: str = ""
    min_hole_area: str = ""


@dataclass(frozen=True, kw_only=True)
class LayoutZoneSettings:
    clearance: str = ""
    min_thickness: str = ""
    thermal_gap: str = ""
    thermal_spoke_width: str = ""
    connection: str = ""
    fill_mode: str = ""
    min_island_area: str = ""
    island_removal: str = ""
    smoothing: str = ""
    smoothing_radius: str = ""
    hatch: LayoutHatch = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class LayoutZone:
    net: str
    outline: list[LengthPair]
    layers: list[str]
    name: str = ""
    priority: int = 0
    settings: LayoutZoneSettings = field(metadata={"optional": True})
    pads: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class BlockLayoutFile(Document):
    block: str
    block_version: str
    parts_digest: str
    nets_digest: str
    licence: str
    evidence: str
    captured_from: str = ""
    parts: dict[str, LayoutPart] = field(default_factory=lambda: {})
    tracks: list[LayoutTrack] = field(default_factory=lambda: [])
    arcs: list[LayoutArc] = field(default_factory=lambda: [])
    vias: list[LayoutVia] = field(default_factory=lambda: [])
    zones: list[LayoutZone] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class DrawnFont:
    size: Pair = field(metadata={"optional": True})
    thickness: Number = field(metadata={"optional": True})
    bold: bool = field(metadata={"optional": True})
    italic: bool = field(metadata={"optional": True})
    face: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class DrawnField:
    at: Pair
    rotation: Number = 0
    justify: str = ""
    hide: bool = False

    font: DrawnFont = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class DrawnSheetProperty(DrawnField):
    text: str


@dataclass(frozen=True, kw_only=True)
class DrawnSymbol:
    part: str
    at: Pair
    unit: int = 1
    rotation: Number = 0
    mirror: str = ""
    fields: dict[str, DrawnField] = field(default_factory=lambda: {})
    symbol: str = ""


@dataclass(frozen=True, kw_only=True)
class DrawnPower:
    symbol: str
    net: str
    at: Pair
    rotation: Number = 0
    fields: dict[str, DrawnField] = field(default_factory=lambda: {})

    mirror: str = ""


@dataclass(frozen=True, kw_only=True)
class Polyline:
    pts: list[Pair]


@dataclass(frozen=True, kw_only=True)
class DrawnAt:
    at: Pair


@dataclass(frozen=True, kw_only=True)
class DrawnBusEntry(DrawnAt):
    size: Pair


@dataclass(frozen=True, kw_only=True)
class DrawnJunction(DrawnAt):
    diameter: Number = 0


@dataclass(frozen=True, kw_only=True)
class DrawnLabel(DrawnAt):
    kind: str
    text: str
    rotation: Number = 0
    shape: str = "passive"

    font: DrawnFont = field(metadata={"optional": True})
    justify: str = field(metadata={"optional": True})
    intersheet_refs: DrawnField = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class DrawnAlias:
    name: str
    members: list[str]


@dataclass(frozen=True, kw_only=True)
class DrawnPin(DrawnAt):
    name: str
    shape: str
    rotation: Number = 0

    font: DrawnFont = field(metadata={"optional": True})
    justify: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class DrawnSheetRef(DrawnAt):
    key: str
    sheet: str
    module: str
    name: str
    size: Pair
    file: str = ""
    page: str = ""
    pin: list[DrawnPin] = field(default_factory=lambda: [])

    fields: dict[str, DrawnField] = field(default_factory=lambda: {})
    properties: dict[str, DrawnSheetProperty] = field(default_factory=lambda: {})


@dataclass(frozen=True, kw_only=True)
class DrawnOpaque:
    kicad: str = ""
    altium: str = ""


@dataclass(frozen=True, kw_only=True)
class DrawnTitle:
    title: str = ""
    date: str = ""
    revision: str = ""
    organization: str = ""
    doc_id: str = ""
    responsible: str = ""
    approver: str = ""
    params: dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, kw_only=True)
class DrawnSheet:
    key: str
    paper: str = "A4"
    title_block: DrawnTitle = field(default_factory=DrawnTitle)
    generated: bool = False
    symbol: list[DrawnSymbol] = field(default_factory=lambda: [])
    power: list[DrawnPower] = field(default_factory=lambda: [])
    wire: list[Polyline] = field(default_factory=lambda: [])
    bus: list[Polyline] = field(default_factory=lambda: [])
    bus_entry: list[DrawnBusEntry] = field(default_factory=lambda: [])
    junction: list[DrawnJunction] = field(default_factory=lambda: [])
    no_connect: list[DrawnAt] = field(default_factory=lambda: [])
    label: list[DrawnLabel] = field(default_factory=lambda: [])
    bus_alias: list[DrawnAlias] = field(default_factory=lambda: [])
    sheet_ref: list[DrawnSheetRef] = field(default_factory=lambda: [])
    opaque: list[DrawnOpaque] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class DrawnSchematicFile(Document):
    root: str
    sheet: list[DrawnSheet]


@dataclass(frozen=True, kw_only=True)
class KitSample:
    name: str
    script: str
    script_sha256: str
    digest: str
    files: list[FileDigest]


@dataclass(frozen=True, kw_only=True)
class KitForm(FileDigest):
    schema: str


@dataclass(frozen=True, kw_only=True)
class KitScript:
    path: str
    sha256: str
    procedure: str
    log: str
    calls: dict[str, str]


@dataclass(frozen=True, kw_only=True)
class KitFile(Document):
    kit_version: int
    fenolite_version: str
    seed: int
    timestamp: str
    samples: list[KitSample]
    files: list[FileDigest]
    form: KitForm
    script: KitScript
    steps: list[Step]


@dataclass(frozen=True, kw_only=True)
class RunStep:
    id: str
    kind: str
    outcome: str
    scripted: bool
    pending: list[str]
    source: str


@dataclass(frozen=True, kw_only=True)
class RunHypothesis:
    id: str
    outcome: str
    form: bool


@dataclass(frozen=True, kw_only=True)
class ArchiveDigest:
    name: str
    sha256: str
    size: int


@dataclass(frozen=True, kw_only=True)
class KitRunFile(Document):
    run_id: str
    date: str
    synthetic: bool
    kit_sha256: str
    kit_version: int
    kit_fenolite_version: str
    fenolite_version: str
    altium_version: str
    os_family: str
    samples: dict[str, str]
    script_sha256: str
    steps: list[RunStep]
    hypotheses: list[RunHypothesis]
    results: list[FileDigest]
    privacy_findings: int
    kit_resaved: list[str]
    archive: ArchiveDigest


@dataclass(frozen=True, kw_only=True)
class LibraryItemFile(Document):
    kind: str
    id: str
    version: str
    title: str
    summary: str
    spdx: str
    tags: list[str]
    files: list[str]
    depends: list[Depend]
    executes: bool


@dataclass(frozen=True, kw_only=True)
class Upstream:
    url: str
    commit: str
    archive_sha256: str | None = None
    path: str = ""
    retrieved: str = ""
    spdx_expression: str = ""
    source_location: str = ""


@dataclass(frozen=True, kw_only=True)
class ConversionTool:
    name: str
    version: str


@dataclass(frozen=True, kw_only=True)
class ConversionStep:
    tool: str
    argv: list[str]


@dataclass(frozen=True, kw_only=True)
class Conversion:
    tools: list[ConversionTool]
    steps: list[ConversionStep]
    outputs_tree: str


@dataclass(frozen=True, kw_only=True)
class FidelityProof:
    derived_cache: checks.DerivedCacheSummary = field(metadata={"optional": True})
    native_project_rules: checks.NativeProjectRulesSummary = field(metadata={"optional": True})
    levels: dict[str, str]
    skipped: dict[str, str] = field(default_factory=lambda: {})
    fenolite: str = ""
    against: dict[str, str] = field(default_factory=lambda: {})
    date: str = ""
    script_sha256: str = ""
    tolerances: checks.VerifySourceTolerances = field(metadata={"optional": True})

    generated_read_files: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "generated read-set paths mapped to SHA-256",
        }
    )


@dataclass(frozen=True, kw_only=True)
class Fidelity:
    accepted: list[checks.VerifySourceNewAcceptedItem] = field(default_factory=lambda: [])
    proof: FidelityProof = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class Trademarks:
    marks: list[str] = field(default_factory=lambda: [])
    restricted: bool = False
    note: str = ""


@dataclass(frozen=True, kw_only=True)
class Featured:
    permission: str
    date: str = ""


@dataclass(frozen=True, kw_only=True)
class LicenceReview:
    by: str
    date: str
    note: str


@dataclass(frozen=True, kw_only=True)
class ImportSource:
    url: str | None
    revision: str | None


@dataclass(frozen=True, kw_only=True)
class ImportProvenanceFile(Document):
    fidelity: Fidelity = field(metadata={"optional": True})
    design: str
    licence: str
    copyright: list[str]
    source: ImportSource
    inputs: list[InputFile]
    upgrade: list[Upgrade]
    fenolite: str
    tools: dict[str, str]
    date: str
    notices: list[str]
    findings: dict[str, int]
    equivalence: checks.ImportEquivalence | None
    copy: bool = True


@dataclass(frozen=True, kw_only=True)
class EmbeddedImport(Document):
    """Earlier provenance containers preserve a sparse import member verbatim."""

    design: str = ""
    licence: str | None = None
    copyright: list[str] = field(default_factory=lambda: [])
    source: ImportSource = field(metadata={"optional": True})
    inputs: list[InputFile] = field(default_factory=lambda: [])
    upgrade: list[Upgrade] = field(default_factory=lambda: [])
    fenolite: str = ""
    tools: dict[str, str] = field(default_factory=lambda: {})
    date: str = ""
    notices: list[str] = field(default_factory=lambda: [])
    findings: dict[str, int] = field(default_factory=lambda: {})
    equivalence: checks.ImportEquivalence | None = None
    copy: bool = True


@dataclass(frozen=True, kw_only=True)
class ProvenanceFile(Document):
    kind: str = field(metadata={"optional": True})
    id: str = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})
    spdx: str = field(metadata={"optional": True})
    origin: Literal["converted", "authored", "seeded"] = field(metadata={"optional": True})
    authors: list[str] = field(metadata={"optional": True})
    modification_notice: str = field(metadata={"optional": True})
    upstream: Upstream | None = None
    copyright: list[str] = field(default_factory=lambda: [])
    licence_text_sha256: str | None = None
    evidence: str = "UNVERIFIED"
    trademarks: Trademarks = field(default_factory=Trademarks)
    featured: Featured | None = None
    licence_review: LicenceReview | None = None
    conversion: Conversion = field(metadata={"optional": True})
    import_: EmbeddedImport = field(metadata={"name": "import", "optional": True})
    fidelity: Fidelity = field(metadata={"optional": True})
    sources: list[str] | None = None
    library: dict[str, Any] = field(
        metadata={
            "optional": True,
            "description": (
                "Caller-supplied library metadata preserved verbatim by verify-source; "
                "its keys and JSON values are not interpreted."
            ),
        }
    )
    replay: dict[str, str | list[str]] = field(default_factory=lambda: {})
    regeneration: dict[str, str | list[str]] = field(default_factory=lambda: {})


@dataclass(frozen=True, kw_only=True)
class LibraryIndexItem:
    kind: str
    id: str
    version: str
    title: str
    summary: str
    spdx: str
    tags: list[str]
    depends: list[Depend]
    executes: bool
    family: str
    reciprocal: bool
    authors: list[str]
    upstream: Upstream | None
    notice: str
    path: str
    tree: str
    bytes: int
    files: list[SizedFile]
    evidence: str
    proof: str | None
    gallery: str | None
    archive: str


@dataclass(frozen=True, kw_only=True)
class IndexArchive:
    name: str
    bytes: int
    sha256: str


@dataclass(frozen=True, kw_only=True)
class LibraryIndexFile(Document):
    name: str
    version: str
    commit: str
    requires: dict[str, str]
    items: list[LibraryIndexItem]
    archives: list[IndexArchive]


@dataclass(frozen=True, kw_only=True)
class LibrarySource:
    id: str = ""
    title: str
    url: str
    licence: str
    retrieved: str
    used: str
    note: str = ""


@dataclass(frozen=True, kw_only=True)
class LibrarySourcesFile(Document):
    sources: dict[str, LibrarySource]


@dataclass(frozen=True, kw_only=True)
class LibraryMetadataFile(Document):
    name: str
    version: str = ""
    requires: dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, kw_only=True)
class LibrarySheet:
    id: str
    record_digest: str
    path: str
    sha256: str
    review_sha256: str


@dataclass(frozen=True, kw_only=True)
class LibrarySheetsFile(Document):
    items: list[LibrarySheet]


# These three IDs identify agent-readable command reports; their producers already describe the
# complete union of import/proposal/seed branches in the library result wire class.
LibraryImportFile = discovery.LibraryResult
LibraryProposeFile = discovery.LibraryResult
LibrarySeedFile = discovery.LibraryResult


@dataclass(frozen=True, kw_only=True)
class CompositionEvidence:
    level: str
    native_review: str


@dataclass(frozen=True, kw_only=True)
class CompositionLimits:
    grid: int
    pin_grid: int
    fanout: int
    placement_budget: int
    wire_budget: int
    text_bounds: str


@dataclass(frozen=True, kw_only=True)
class ComposedBlock:
    key: str
    title: str
    bounds: tuple[int, int, int, int]


@dataclass(frozen=True, kw_only=True)
class ComposedPlacement:
    unit: str
    component: str
    part: int
    block: str
    origin: tuple[int, int]
    rotation: int
    bounds: tuple[int, int, int, int]
    visible: list[Visible]


@dataclass(frozen=True, kw_only=True)
class ComposedWire:
    net: str
    start: tuple[str, str]
    end: tuple[str, str]
    points: list[tuple[int, int]]
    bends: int
    crossings: int
    length: int


@dataclass(frozen=True, kw_only=True)
class LabelledConnection:
    unit: str
    pin: str
    net: str
    power: bool


@dataclass(frozen=True, kw_only=True)
class ComposedSheet:
    sheet: str
    flow: str
    preview: str
    region: tuple[int, int, int, int]
    reserved: list[tuple[int, int, int, int]]
    placement_candidates: int
    connection_candidates: int
    wrapped: bool
    blocks: list[ComposedBlock]
    placements: list[ComposedPlacement]
    attachments: list[Attachment]
    wires: list[ComposedWire]
    labelled_connections: list[LabelledConnection]
    issues: list[Issue]


@dataclass(frozen=True, kw_only=True)
class SchematicCompositionFile(Document):
    algorithm: str
    evidence: CompositionEvidence
    units: str
    origin: str
    replayed_sheets: list[str]
    limits: CompositionLimits
    sheets: list[ComposedSheet]
