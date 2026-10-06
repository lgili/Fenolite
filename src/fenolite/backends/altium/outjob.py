# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The output job (``.OutJob``) written (capability altium-project-reader, "Output job written"; change
c0087).

``write_outjob`` writes groups, containers and outputs in the form ``read.outjob.read_outjob`` reads, and
``from_preset`` gives the job of a build: the containers ``fab`` and ``doc`` and one output per kind of
``OUTPUT_KINDS``. Fenolite runs no output: the job is a file for the user to run in Altium.

Only keys whose meaning ``docs/formats/altium/output-job.md`` records are written. No output setting is
among them, so every output keeps Altium's defaults and ``unmapped`` names the options of an export preset
that the job does not carry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from fenolite.backends.altium.read.outjob import JOB_SECTION, JobOutput, OutputGroup, OutputMedium
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
OUTJOB_KIND = "altium_outjob"
"""The write kind of ``<name>.OutJob``."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-OUTJOB-OPEN", "H-A-OUTJOB-READBACK", "H-A-OUTJOB-RUN"))
"""Own readback is supporting data; that Altium opens and runs the job waits for Part O of the author
report."""
MAPPED_OPTIONS: frozenset[str] = frozenset()
"""The options of an export preset (``table.key``) that the writer maps to a key of the job: none. A
configuration record with some of its fields only is a guess about the others (``H-A-OUTJOB-OPTIONS``)."""
PRESET_TABLES = ("gerbers", "drill", "pos")
"""The tables of an export preset (``fenolite.export-preset.v0``)."""

Document = str
"""How an output names its source: ``"pcb"`` for the PCB document, ``"project"`` for an empty path."""


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
    preset: PresetOptions | None, *, name: str, disabled: Sequence[str] = ()
) -> tuple[OutputGroup, ...]:
    """The job of the project ``name``: one group named ``<name>.OutJob`` with the containers ``fab``
    (folder) and ``doc`` (PDF) and one output per kind of ``OUTPUT_KINDS``. A kind of ``disabled`` is
    listed with ``enabled`` false and no container, so the user sees it. ``preset`` changes nothing yet:
    no option is mapped (``MAPPED_OPTIONS``), and ``unmapped(preset)`` names what is left to Altium's
    defaults. ``ValueError`` for an unknown kind."""
    del preset
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
    return lines


def write_outjob(groups: Sequence[OutputGroup]) -> bytes:
    """The bytes of the output job that holds ``groups``: ``[OutputJobFile]`` with ``Version=1.0``, one
    section per group and the two settings sections, empty; LF line ends, 7-bit ASCII, one empty line after
    each section. ``read_outjob`` of the bytes gives equal groups. ``ValueError`` for a text a line cannot
    hold, for an index that is below 1 or repeated, for an output or a container without a type and for a
    container an output names and the group lacks."""
    _numbered([group.index for group in groups], "output groups")
    sections = [[f"[{JOB_SECTION}]", f"Version={VERSION}"]]
    sections += [_group_lines(group) for group in groups]
    sections += [[f"[{name}]"] for name in SETTINGS_SECTIONS]
    lines = [line for section in sections for line in (*section, "")]
    return b"".join(line.encode("ascii") + LINE_END for line in lines)


__all__ = [
    "EVIDENCE",
    "FOLDER_MEDIUM",
    "FOLDER_TYPE",
    "MAPPED_OPTIONS",
    "NO_VARIANT",
    "OUTJOB_KIND",
    "OUTPUT_KINDS",
    "PDF_MEDIUM",
    "PDF_TYPE",
    "OutputKind",
    "PresetOptions",
    "from_preset",
    "kind_of",
    "unmapped",
    "write_outjob",
]
