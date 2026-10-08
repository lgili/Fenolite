# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The output job (``.OutJob``) written (capability altium-project-reader, "Output job written"; changes
c0087 and c0138).

``write_outjob`` writes groups, containers and outputs in the form ``read.outjob.read_outjob`` reads, and
``from_preset`` gives the job of a build: the containers ``fab`` and ``doc`` and one output per kind of
``OUTPUT_KINDS``. Fenolite runs no output: the job is a file for the user to run in Altium.

Only keys that ``docs/formats/altium/output-job.md`` records are written. Since change c0138 every output
holds ``OutputDefault<i>=0``, and a Gerber output holds the complete settings record (``GERBER_FIELDS``,
``gerber_record``): without one Altium Designer 26 plots no layer. The record is whole or the job is not
written. No other output kind holds a setting, so those keep Altium's defaults, and ``unmapped`` names the
options of an export preset that the job does not carry. The board outline is not among the plotted layers
(``OUTLINE_REASON``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

import fenolite.backends.altium.libboard as libboard
import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.read.outjob import (
    FIELD_SEPARATOR,
    JOB_SECTION,
    JobOutput,
    OutputGroup,
    OutputMedium,
    OutputSetting,
    record_fields,
)
from fenolite.core.evidence import Evidence, Level

VERSION = "1.0"
LINE_END = b"\n"
"""A saved output job has LF line ends (``output-job.md``)."""
SETTINGS_SECTIONS = ("PublishSettings", "GeneratedFilesSettings")
"""The two sections every saved job holds; written empty, because no key of them has a recorded meaning."""
FOLDER_TYPE = "GeneratedFiles"
PDF_TYPE = "Publish"
FOLDER_MEDIUM = "fab"
PDF_MEDIUM = "doc"
NO_VARIANT = "[No Variations]"
OUTPUT_DEFAULT = "0"
"""``OutputDefault<i>`` of every output of the three public jobs; written after the output's last container
key. What Altium does with the value is not stated by a source (``output-job.md``)."""
OUTJOB_KIND = "altium_outjob"
"""The write kind of ``<name>.OutJob``."""
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-OUTJOB-GERBER-ACCEPT",
        "H-A-OUTJOB-GERBER-LAYERS",
        "H-A-OUTJOB-GERBER-RECORD",
        "H-A-OUTJOB-OPEN",
        "H-A-OUTJOB-READBACK",
        "H-A-OUTJOB-RUN-2",
    ),
)
"""Own readback is supporting data; that Altium opens the job, takes the Gerber record and runs the outputs
waits for Part O of the author report (session 2)."""
MAPPED_OPTIONS: frozenset[str] = frozenset({"gerbers.precision"})
"""The options of an export preset (``table.key``) that the writer maps to a field of the job: the Gerber
precision, which is ``NumberOfDecimals`` of the Gerber record (change c0138)."""
PRESET_TABLES = ("gerbers", "drill", "pos")
"""The tables of an export preset (``fenolite.export-preset.v0``)."""

Document = str
"""How an output names its source: ``"pcb"`` for the PCB document, ``"project"`` for an empty path."""

# --- the Gerber settings record (change c0138; output-job.md, "The Gerber settings record") --------------

GERBER_TYPE = "Gerber"
"""The type of the one output kind that carries a settings record."""
SETTING_NAME = "OutputConfigurationParameter1"
"""``Configuration<i>_Name1`` of a Gerber output in both public jobs."""
LAYER_SET_HEAD = "SerializeLayerHash.Version~2,ClassName~TLayerToBoolean"
"""What the three layer sets of the record start with; ``Mirror.Set`` and ``AddToAllPlots.Set`` hold
nothing else."""
GERBER_UNIT = "Metric"
"""A stated choice: Fenolite's lengths are metric and the export preset has no Gerber unit."""
DEFAULT_DECIMALS = 4
"""``NumberOfDecimals`` without ``gerbers.precision``: the value a public job holds beside ``Metric``."""
DECIMALS = (4, 5, 6)
"""The decimals the writer writes: the default and the two values ``gerbers.precision`` allows. Only 4 is
seen beside ``Metric`` in a public job (``H-A-OUTJOB-GERBER-DECIMALS``); nothing is clamped."""
MECHANICAL_BASE = 56
"""Mechanical layer n is the numbered layer ``56 + n`` (``pcb-library.md``, "Long layer ids")."""
PLOT_ABOVE = (33, 35, 37)
"""Top Overlay, Top Paste, Top Solder: the entries before the copper, in the order of both public jobs."""
PLOT_BELOW = (38, 36, 34)
"""Bottom Solder, Bottom Paste, Bottom Overlay: the entries after the copper."""
OUTLINE_REASON = (
    "the PCB document holds the board outline as the board shape and on no layer, and no public source "
    "gives the entry of the board shape among the plotted layers; turn the outline on in the Gerber setup "
    "in Altium"
)
"""Why the Gerber set of a written job holds no plot of the board outline (``result.outjob.gerber``)."""

CONSTANT, CHOICE, UNIT, DECIMALS_RULE, LAYERS = "constant", "choice", "unit", "decimals", "layers"
"""The rules of ``GERBER_FIELDS``: a value both public jobs hold; a value one of the two holds, chosen by
the writer; the unit; the decimals; the plotted layers."""


@dataclass(frozen=True, slots=True)
class GerberField:
    """One field of the Gerber record: its name, the rule its value comes from, and the value of a
    ``constant``, ``choice`` or ``unit`` field (``decimals`` and ``layers`` have none: they come from the
    preset and from the board)."""

    name: str
    rule: str
    value: str = ""


def _fields() -> tuple[GerberField, ...]:
    false, true = "False", "True"
    table: tuple[tuple[str, str, str, int], ...] = (
        ("AddToAllLayerClasses.Set", CONSTANT, " ", 1),
        ("AddToAllPlots.Set", CONSTANT, LAYER_SET_HEAD, 1),
        ("CentrePlots", CONSTANT, false, 1),
        ("DrillDrawingSymbol", CONSTANT, "GraphicsSymbol", 1),
        ("DrillDrawingSymbolSize", CONSTANT, "200000", 1),
        ("EmbeddedApertures", CONSTANT, true, 1),
        ("FilmBorderSize", CONSTANT, "10000000", 1),
        ("FilmXSize", CONSTANT, "200000000", 1),
        ("FilmYSize", CONSTANT, "160000000", 1),
        ("FlashAllFills", CONSTANT, false, 1),
        ("FlashPadShapes", CONSTANT, true, 1),
        ("G54OnApertureChange", CONSTANT, false, 1),
        ("GenerateDRCRulesFile", CONSTANT, true, 2),
        ("GenerateReliefShapes", CONSTANT, true, 1),
        ("GerberUnit", UNIT, GERBER_UNIT, 2),
        ("IncludeUnconnectedMidLayerPads", CONSTANT, false, 1),
        ("LayerClassesMirror.Set", CONSTANT, " ", 1),
        ("LayerClassesPlot.Set", CHOICE, " ", 1),
        ("LeadingAndTrailingZeroesMode", CONSTANT, "SuppressLeadingZeroes", 1),
        ("MaxApertureSize", CONSTANT, "2500000", 1),
        ("MinusApertureTolerance", CHOICE, "39", 2),
        ("Mirror.Set", CONSTANT, LAYER_SET_HEAD, 1),
        ("MirrorDrillDrawingPlots", CONSTANT, false, 1),
        ("MirrorDrillGuidePlots", CONSTANT, false, 1),
        ("NoRegularPolygons", CONSTANT, false, 1),
        ("NumberOfDecimals", DECIMALS_RULE, "", 2),
        ("OptimizeChangeLocationCommands", CONSTANT, true, 2),
        ("OriginPosition", CONSTANT, "Relative", 1),
        ("Panelize", CONSTANT, false, 1),
        ("Plot.Set", LAYERS, "", 1),
        ("PlotPositivePlaneLayers", CONSTANT, false, 1),
        ("PlotUsedDrillDrawingLayerPairs", CHOICE, false, 1),
        ("PlotUsedDrillGuideLayerPairs", CHOICE, false, 1),
        ("PlusApertureTolerance", CHOICE, "39", 2),
        ("Record", CONSTANT, "GerberView", 1),
        ("SoftwareArcs", CHOICE, false, 1),
        ("Sorted", CONSTANT, false, 2),
    )
    return tuple(GerberField(name, rule, value) for name, rule, value, times in table for _ in range(times))


GERBER_FIELDS: tuple[GerberField, ...] = _fields()
"""The 44 fields of the Gerber record in their order, which is the order of the names by code point; the
seven names a saved record holds twice stand twice, one after the other. Equal to the field table of
``output-job.md`` (a unit test compares them). ``DocumentPath``, which one public job adds, is not a field:
its value is an absolute path."""


def plot_layer_numbers(copper: Sequence[int]) -> tuple[int, ...]:
    """The plotted layers of a board whose copper layers have the Altium ids ``copper``, from top to bottom,
    as numbered layers and in the order of ``Plot.Set``: Top Overlay, Top Paste, Top Solder; each layer of
    ``copper``, a signal layer and an internal plane alike; Bottom Solder, Bottom Paste, Bottom Overlay;
    Mechanical 13 to 16 (``libboard.ENABLED_MECHANICAL``). Only layers the board has; the board outline is
    on no layer and is not among them. ``ValueError`` for a stack ``libboard.valid_stack`` refuses."""
    stack = tuple(copper)
    if not libboard.valid_stack(stack):
        raise ValueError(f"{list(stack)} is not a copper stack of a written PCB document")
    mechanical = tuple(MECHANICAL_BASE + n for n in libboard.ENABLED_MECHANICAL)
    return (*PLOT_ABOVE, *stack, *PLOT_BELOW, *mechanical)


def plot_layers(copper: Sequence[int]) -> tuple[int, ...]:
    """The long ids of ``plot_layer_numbers(copper)`` (``libboard.long_id``), in the same order."""
    return tuple(libboard.long_id(layer) for layer in plot_layer_numbers(copper))


def gerber_record(layers: Sequence[int], *, decimals: int) -> str:
    """The complete Gerber record: the 44 fields of ``GERBER_FIELDS`` as ``Name=Value`` joined by ``|``.
    ``GerberUnit`` is ``Metric`` and ``NumberOfDecimals`` is ``decimals``, each in both of its places, and
    ``Plot.Set`` is the head and ``,<long id>~1`` for each layer of ``layers`` in the order given.
    ``ValueError`` for ``decimals`` outside ``DECIMALS``, for no layer and for a repeated one."""
    if isinstance(decimals, bool) or decimals not in DECIMALS:
        raise ValueError(f"the Gerber decimals are {decimals!r}; the writer writes one of {list(DECIMALS)}")
    ids = tuple(layers)
    if not ids:
        raise ValueError("a Gerber record without a plotted layer")
    if len(set(ids)) != len(ids):
        raise ValueError("a layer is repeated among the plotted layers of the Gerber record")
    values = {
        UNIT: GERBER_UNIT,
        DECIMALS_RULE: str(decimals),
        LAYERS: LAYER_SET_HEAD + "".join(f",{layer}~1" for layer in ids),
    }
    parts = [f"{field.name}={values.get(field.rule, field.value)}" for field in GERBER_FIELDS]
    return FIELD_SEPARATOR.join(parts)


def plotted_layers(item: str) -> tuple[int, ...]:
    """The long ids of the entries of ``Plot.Set`` in the record ``item``, in its order."""
    for name, value in record_fields(item):
        if name == "Plot.Set":
            entries = value.removeprefix(LAYER_SET_HEAD).split(",")
            return tuple(int(entry.partition("~")[0]) for entry in entries if entry)
    return ()


def layer_name(long: int) -> str:
    """The name of the numbered layer whose long id is ``long``, as ``pcbrecords.LAYER_NAMES`` gives it.
    ``ValueError`` for an id that no numbered layer has."""
    for number, name in rec.LAYER_NAMES.items():
        try:
            if libboard.long_id(number) == long:
                return name
        except ValueError:
            continue
    raise ValueError(f"no numbered layer has the long id {long}")


def gerber_setting(groups: Sequence[OutputGroup]) -> OutputSetting | None:
    """The setting of the first Gerber output of ``groups``, or ``None``."""
    for group in groups:
        for output in group.outputs:
            if output.type == GERBER_TYPE and output.settings:
                return output.settings[0]
    return None


@dataclass(frozen=True, slots=True)
class OutputKind:
    """One kind of output the writer knows: the type, name and category Altium saves for it, the document
    it is bound to and the container it is sent to."""

    key: str
    type: str
    name: str
    category: str
    document: Document
    medium: str


OUTPUT_KINDS: Mapping[str, OutputKind] = MappingProxyType(
    {
        kind.key: kind
        for kind in (
            OutputKind("gerbers", "Gerber", "Gerber Files", "Fabrication", "pcb", FOLDER_MEDIUM),
            OutputKind("drill", "NC Drill", "NC Drill Files", "Fabrication", "pcb", FOLDER_MEDIUM),
            OutputKind("pos", "Pick Place", "Pick and Place", "Assembly", "pcb", FOLDER_MEDIUM),
            OutputKind("bom", "BOM_PartType", "Bill of Materials", "Report", "project", FOLDER_MEDIUM),
            OutputKind(
                "schematic_print",
                "Schematic Print",
                "Schematic Prints",
                "Documentation",
                "project",
                PDF_MEDIUM,
            ),
            OutputKind("pcb_print", "PCB Print", "PCB Prints", "Documentation", "pcb", PDF_MEDIUM),
        )
    }
)
"""The closed table of output kinds, in the order they are written. Types, names and categories are those
of the public saved jobs (``output-job.md``, "Outputs and containers as saved"). There is no assembly
drawing: no public file gives its type."""


class PresetOptions(Protocol):
    """What ``unmapped`` reads of an export preset (``fenolite.exports.preset.Preset``): the keys each
    table sets."""

    @property
    def gerbers(self) -> Mapping[str, object]: ...

    @property
    def drill(self) -> Mapping[str, object]: ...

    @property
    def pos(self) -> Mapping[str, object]: ...


def unmapped(preset: PresetOptions | None) -> tuple[str, ...]:
    """``table.key`` of every option ``preset`` sets and the job does not carry, sorted. The user sets these
    in the setup of the output in Altium."""
    if preset is None:
        return ()
    found = {f"{table}.{key}" for table in PRESET_TABLES for key in getattr(preset, table)} - MAPPED_OPTIONS
    return tuple(sorted(found))


def from_preset(
    preset: PresetOptions | None, *, name: str, copper: Sequence[int], disabled: Sequence[str] = ()
) -> tuple[OutputGroup, ...]:
    """The job of the project ``name``: one group named ``<name>.OutJob`` with the containers ``fab``
    (folder) and ``doc`` (PDF) and one output per kind of ``OUTPUT_KINDS``. A kind of ``disabled`` is
    listed with ``enabled`` false and no container, so the user sees it.

    The Gerber output holds the complete record, disabled or not: the plotted layers are those of the board
    whose copper layers are ``copper`` (Altium ids from top to bottom, ``StackSpec.copper``), and the
    decimals are ``gerbers.precision`` of ``preset`` when it sets one, else ``DEFAULT_DECIMALS``. No other
    option is mapped (``MAPPED_OPTIONS``); ``unmapped(preset)`` names what is left to Altium's defaults.
    ``ValueError`` for an unknown kind, for a stack that is not one, and for decimals outside ``DECIMALS``."""
    precision = None if preset is None else preset.gerbers.get("precision")
    decimals = DEFAULT_DECIMALS if precision is None else precision
    if not isinstance(decimals, int):
        raise ValueError(f"gerbers.precision is {decimals!r}, not a whole number")
    record = OutputSetting(1, SETTING_NAME, gerber_record(plot_layers(copper), decimals=decimals))
    unknown = sorted(set(disabled) - set(OUTPUT_KINDS))
    if unknown:
        raise ValueError(f"unknown output kind(s) {', '.join(unknown)}; known: {', '.join(OUTPUT_KINDS)}")
    media = (OutputMedium(1, FOLDER_MEDIUM, FOLDER_TYPE), OutputMedium(2, PDF_MEDIUM, PDF_TYPE))
    index_of = {medium.name: medium.index for medium in media}
    outputs: list[JobOutput] = []
    for index, kind in enumerate(OUTPUT_KINDS.values(), start=1):
        enabled = kind.key not in disabled
        outputs.append(
            JobOutput(
                index=index,
                type=kind.type,
                name=kind.name,
                category=kind.category,
                document_path=f"{name}.PcbDoc" if kind.document == "pcb" else "",
                variant_name="",
                enabled=enabled,
                enabled_media=(index_of[kind.medium],) if enabled else (),
                settings=(record,) if kind.type == GERBER_TYPE else (),
            )
        )
    return (OutputGroup(1, f"{name}.OutJob", "", NO_VARIANT, media, tuple(outputs)),)


def kind_of(output: JobOutput) -> str | None:
    """The key of ``OUTPUT_KINDS`` whose type ``output`` has, or ``None``."""
    for kind in OUTPUT_KINDS.values():
        if kind.type == output.type:
            return kind.key
    return None


def _value(text: str, what: str) -> str:
    """``text`` as the value of a key, kept as it is: printable 7-bit ASCII, so no line end."""
    if any(not 0x20 <= ord(ch) <= 0x7E for ch in text):
        raise ValueError(f"{what} {text!r} holds a character outside printable 7-bit ASCII")
    return text


def _numbered(indexes: Sequence[int], what: str) -> None:
    if any(index < 1 for index in indexes):
        raise ValueError(f"{what}: an index below 1")
    if len(set(indexes)) != len(indexes):
        raise ValueError(f"{what}: an index is repeated")


def _setting_lines(output: JobOutput, where: str) -> list[str]:
    """The configuration keys of ``output``: two lines for a Gerber output with the complete record, none
    for another output. ``ValueError`` for a Gerber output whose settings are not exactly the one record
    with the fields of ``GERBER_FIELDS`` in order, and for a setting on any other output: a record with a
    part of its fields is a guess about the others and is never written."""
    i = output.index
    if output.type != GERBER_TYPE:
        if output.settings:
            raise ValueError(
                f"{where}: output {i} of the type {output.type!r} has a setting; only a Gerber output "
                "carries a settings record"
            )
        return []
    if len(output.settings) != 1:
        raise ValueError(
            f"{where}: the Gerber output {i} has {len(output.settings)} settings; it carries exactly one, "
            "the complete record (outjob.gerber_record)"
        )
    (setting,) = output.settings
    if setting.index != 1 or setting.name != SETTING_NAME:
        raise ValueError(
            f"{where}: the setting of the Gerber output {i} is not setting 1 named {SETTING_NAME}"
        )
    names = [name for name, _value in record_fields(setting.item)]
    wanted = [field.name for field in GERBER_FIELDS]
    if names != wanted:
        missing = sorted(set(wanted) - set(names))
        extra = sorted(set(names) - set(wanted))
        raise ValueError(
            f"{where}: the record of the Gerber output {i} is not the complete record of {len(wanted)} "
            f"fields in order (found {len(names)}; missing {missing}; not a field {extra})"
        )
    return [
        f"Configuration{i}_Name1={_value(setting.name, 'the setting name')}",
        f"Configuration{i}_Item1={_value(setting.item, 'the Gerber record')}",
    ]


def _group_lines(group: OutputGroup) -> list[str]:
    where = f"output group {group.index}"
    _numbered([medium.index for medium in group.media], f"{where}, containers")
    _numbered([output.index for output in group.outputs], f"{where}, outputs")
    lines = [
        f"[OutputGroup{group.index}]",
        f"Name={_value(group.name, 'the group name')}",
        f"Description={_value(group.description, 'the group description')}",
        f"VariantName={_value(group.variant_name, 'the variant name')}",
    ]
    known = {medium.index for medium in group.media}
    for medium in group.media:
        if not medium.type:
            raise ValueError(f"{where}: container {medium.index} has no type")
        lines.append(f"OutputMedium{medium.index}={_value(medium.name, 'the container name')}")
        lines.append(f"OutputMedium{medium.index}_Type={_value(medium.type, 'the container type')}")
    position = dict.fromkeys(known, 0)
    for output in group.outputs:
        i = output.index
        if not output.type:
            raise ValueError(f"{where}: output {i} has no type")
        missing = sorted(set(output.enabled_media) - known)
        if missing:
            raise ValueError(f"{where}: output {i} names the container(s) {missing}, which the group lacks")
        if tuple(sorted(set(output.enabled_media))) != output.enabled_media:
            raise ValueError(f"{where}: the containers of output {i} are not ascending and distinct")
        lines += [
            f"OutputType{i}={_value(output.type, 'the output type')}",
            f"OutputName{i}={_value(output.name, 'the output name')}",
            f"OutputCategory{i}={_value(output.category, 'the output category')}",
            f"OutputDocumentPath{i}={_value(output.document_path, 'the document path')}",
            f"OutputVariantName{i}={_value(output.variant_name, 'the variant name')}",
            f"OutputEnabled{i}={'1' if output.enabled else '0'}",
        ]
        for medium in group.media:
            value = 0
            if medium.index in output.enabled_media:
                position[medium.index] += 1
                value = position[medium.index]
            lines.append(f"OutputEnabled{i}_OutputMedium{medium.index}={value}")
        lines.append(f"OutputDefault{i}={OUTPUT_DEFAULT}")
        lines += _setting_lines(output, where)
    return lines


def write_outjob(groups: Sequence[OutputGroup]) -> bytes:
    """The bytes of the output job that holds ``groups``: ``[OutputJobFile]`` with ``Version=1.0``, one
    section per group and the two settings sections, empty; LF line ends, 7-bit ASCII, one empty line after
    each section. Every output holds ``OutputDefault<i>=0`` after its container keys, and a Gerber output
    its two configuration keys after that. ``read_outjob`` of the bytes gives equal groups. ``ValueError``
    for a text a line cannot hold, for an index that is below 1 or repeated, for an output or a container
    without a type, for a container an output names and the group lacks, for a Gerber output without the
    complete record and for a setting on another output."""
    _numbered([group.index for group in groups], "output groups")
    sections = [[f"[{JOB_SECTION}]", f"Version={VERSION}"]]
    sections += [_group_lines(group) for group in groups]
    sections += [[f"[{name}]"] for name in SETTINGS_SECTIONS]
    lines = [line for section in sections for line in (*section, "")]
    return b"".join(line.encode("ascii") + LINE_END for line in lines)


__all__ = [
    "DECIMALS",
    "DEFAULT_DECIMALS",
    "EVIDENCE",
    "FOLDER_MEDIUM",
    "FOLDER_TYPE",
    "GERBER_FIELDS",
    "GERBER_TYPE",
    "GERBER_UNIT",
    "LAYER_SET_HEAD",
    "MAPPED_OPTIONS",
    "NO_VARIANT",
    "OUTJOB_KIND",
    "OUTLINE_REASON",
    "OUTPUT_DEFAULT",
    "OUTPUT_KINDS",
    "PDF_MEDIUM",
    "PDF_TYPE",
    "SETTING_NAME",
    "GerberField",
    "OutputKind",
    "PresetOptions",
    "from_preset",
    "gerber_record",
    "gerber_setting",
    "kind_of",
    "layer_name",
    "plot_layer_numbers",
    "plot_layers",
    "plotted_layers",
    "unmapped",
    "write_outjob",
]
