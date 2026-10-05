# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The output job (``.OutJob``) read byte for byte (capability altium-project-reader, change c0042).

``read_outjob`` lists the output groups, their containers (media) and their outputs. It runs no
output. Facts: ``docs/formats/altium/output-job.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fenolite.backends.altium.read.ini import IniDocument, IniSection, parse_ini
from fenolite.backends.altium.read.textfile import text_issue
from fenolite.core.errors import FormatError, Issue

JOB_SECTION = "OutputJobFile"
OUTPUT_KEYS = (
    "OutputType",
    "OutputName",
    "OutputCategory",
    "OutputDocumentPath",
    "OutputVariantName",
    "OutputEnabled",
)
_OUTPUT_KEY = re.compile("(" + "|".join(OUTPUT_KEYS) + r")([1-9][0-9]*)")
_MEDIUM_KEY = re.compile(r"OutputMedium([1-9][0-9]*)")
_ENABLED_MEDIUM_KEY = re.compile(r"OutputEnabled([1-9][0-9]*)_OutputMedium([1-9][0-9]*)")


@dataclass(frozen=True, slots=True)
class OutputMedium:
    """A container of a group: ``OutputMedium<j>`` (its name) and ``OutputMedium<j>_Type``."""

    index: int
    name: str
    type: str


@dataclass(frozen=True, slots=True)
class JobOutput:
    """Output ``i`` of a group. ``enabled`` is true only for ``OutputEnabled<i>=1``; ``enabled_media``
    holds each ``j`` whose ``OutputEnabled<i>_OutputMedium<j>`` is not ``0``, in ascending order."""

    index: int
    type: str
    name: str
    category: str
    document_path: str
    variant_name: str
    enabled: bool
    enabled_media: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class OutputGroup:
    """One section ``OutputGroup<n>``."""

    index: int
    name: str
    description: str
    variant_name: str
    media: tuple[OutputMedium, ...]
    outputs: tuple[JobOutput, ...]


@dataclass(frozen=True, slots=True)
class OutJobFile:
    """An output job: its INI view, ``Version`` of ``[OutputJobFile]``, its groups and its issues."""

    ini: IniDocument
    version: str | None
    groups: tuple[OutputGroup, ...]
    issues: tuple[Issue, ...]

    def to_bytes(self) -> bytes:
        return self.ini.to_bytes()


def _group(index: int, section: IniSection, file: str, issues: list[Issue]) -> OutputGroup:
    media: list[OutputMedium] = []
    outputs: set[int] = set()
    enabled_media: dict[int, set[int]] = {}
    for entry in section.entries:
        medium = _MEDIUM_KEY.fullmatch(entry.key)
        if medium:
            j = int(medium.group(1))
            if all(m.index != j for m in media):
                media.append(OutputMedium(j, entry.value, section.get(f"{entry.key}_Type") or ""))
            continue
        output = _OUTPUT_KEY.fullmatch(entry.key)
        if output:
            outputs.add(int(output.group(2)))
            continue
        pair = _ENABLED_MEDIUM_KEY.fullmatch(entry.key)
        if pair and entry.value != "0":
            enabled_media.setdefault(int(pair.group(1)), set()).add(int(pair.group(2)))
    listed: list[JobOutput] = []
    for i in sorted(outputs):
        kind = section.get(f"OutputType{i}")
        if kind is None:
            issues.append(
                text_issue(
                    "altium.outjob.output-incomplete",
                    f"output group {index}, output {i}: no OutputType{i}; listed with an empty type",
                    file,
                )
            )
        listed.append(
            JobOutput(
                index=i,
                type=kind or "",
                name=section.get(f"OutputName{i}") or "",
                category=section.get(f"OutputCategory{i}") or "",
                document_path=section.get(f"OutputDocumentPath{i}") or "",
                variant_name=section.get(f"OutputVariantName{i}") or "",
                enabled=section.get(f"OutputEnabled{i}") == "1",
                enabled_media=tuple(sorted(enabled_media.get(i, set()))),
            )
        )
    return OutputGroup(
        index=index,
        name=section.get("Name") or "",
        description=section.get("Description") or "",
        variant_name=section.get("VariantName") or "",
        media=tuple(media),
        outputs=tuple(listed),
    )


def read_outjob(data: bytes, *, file: str = "") -> OutJobFile:
    """Read the output job ``data``; ``to_bytes()`` of the result equals ``data``. ``FormatError`` when
    the section ``OutputJobFile`` is missing, or for a compound file or a NUL byte. Warning
    ``altium.outjob.output-incomplete`` for an output without its type."""
    ini = parse_ini(data, file=file)
    job = ini.section(JOB_SECTION)
    if job is None:
        raise FormatError(
            f"not an output job: the section [{JOB_SECTION}] is missing", file=file, locator=JOB_SECTION
        )
    issues = list(ini.issues)
    groups = tuple(_group(index, section, file, issues) for index, section in ini.numbered("OutputGroup"))
    return OutJobFile(ini=ini, version=job.get("Version"), groups=groups, issues=tuple(issues))


__all__ = [
    "JOB_SECTION",
    "OUTPUT_KEYS",
    "JobOutput",
    "OutJobFile",
    "OutputGroup",
    "OutputMedium",
    "read_outjob",
]
