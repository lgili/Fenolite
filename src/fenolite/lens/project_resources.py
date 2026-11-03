# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact, bounded native worksheet dependencies of a declared project (c0354)."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.kicad import _json, pro, wks
from fenolite.backends.kicad.pro_template import RESOURCE_POINTERS, validate_project_template
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import FileKind, VersionStatus, inspect
from fenolite.core.errors import FormatError

MAX_RESOURCE_BYTES = 16 * 1024 * 1024
_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)


@dataclass(frozen=True, slots=True)
class ProjectResource:
    name: str
    path: Path
    data: bytes


def resource_names(text: str) -> tuple[str, ...]:
    """Only the two native worksheet pointers, retaining their independent scopes."""
    validate_project_template(text, managed_frame=True)
    data = pro.read_project(text).data
    names: list[str] = []
    for pointer in RESOURCE_POINTERS:
        value = _json.get(data, pointer)
        if value is None or value == "":
            continue
        assert isinstance(value, str)
        name = value.removeprefix("${KIPRJMOD}/")
        parts = name.split("/")
        if (
            "\\" in name
            or any(
                not part
                or part in {".", ".."}
                or ":" in part
                or part.rstrip(". ") != part
                or part.split(".")[0].upper() in _RESERVED
                for part in parts
            )
            or not name.lower().endswith(".kicad_wks")
        ):
            raise FormatError(
                "native project worksheet resource is not a portable worksheet path", locator=pointer
            )
        if name not in names:
            if name.casefold() in {item.casefold() for item in names}:
                raise FormatError("native worksheet resource paths collide ignoring case", locator=pointer)
            names.append(name)
    return tuple(names)


def validate_resources(
    text: str, resources: Sequence[ProjectResource], *, managed_frame: bool = False
) -> None:
    """Validate snapshots without reading paths; no supplied resource silently becomes output."""
    names = [item.name for item in resources]
    expected: Collection[str] = () if managed_frame else resource_names(text)
    if len(names) != len(set(names)) or set(names) != set(expected):
        raise FormatError("native project worksheet bundle does not match its exact references")
    for item in resources:
        if len(item.data) > MAX_RESOURCE_BYTES:
            raise FormatError("native project worksheet exceeds the resource byte limit", file=item.name)
        try:
            body = item.data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise FormatError("native project worksheet is not UTF-8", file=item.name) from error
        info = inspect(parse(body), file=item.name)
        if info.kind != FileKind.WORKSHEET or info.status == VersionStatus.FUTURE:
            raise FormatError("native project resource is not a supported worksheet", file=item.name)
        wks.read_drawing_sheet(body, file=item.name)
    validate_project_template(text, managed_frame=managed_frame, resource_names=names)


def read_project_resources(
    project: Path, text: str, *, managed_frame: bool = False
) -> tuple[ProjectResource, ...]:
    """Read only exact native references within this project folder, never a search path."""
    if managed_frame:
        validate_project_template(text, managed_frame=True)
        return ()
    folder = project.resolve().parent
    resources: list[ProjectResource] = []
    for name in resource_names(text):
        path = folder / name
        current = folder
        for part in name.split("/"):
            current /= part
            if current.is_symlink():
                raise FormatError("native project worksheet resource is a symlink", file=name)
        if not path.resolve().is_relative_to(folder):
            raise FormatError("native project worksheet leaves the declared project folder", file=name)
        try:
            with path.open("rb") as stream:
                raw = stream.read(MAX_RESOURCE_BYTES + 1)
        except OSError as error:
            raise FormatError(
                "declared native project worksheet is missing or unreadable", file=name
            ) from error
        resources.append(ProjectResource(name, path, raw))
    validate_resources(text, resources)
    return tuple(resources)
