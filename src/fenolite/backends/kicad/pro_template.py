# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Declared project JSON/resource policy; native data stays owned by the KiCad backend (c0351)."""

# evidence: see pro

from __future__ import annotations

from pathlib import PurePosixPath

from fenolite.backends.kicad import _json, pro
from fenolite.backends.kicad.versions import FutureFormatError, UnsupportedFormatError, VersionStatus
from fenolite.core.errors import FormatError

RESOURCE_POINTERS = ("/pcbnew/page_layout_descr_file", "/schematic/page_layout_descr_file")


def validate_project_template(
    text: str, *, file: str = "project_template", managed_frame: bool = False
) -> None:
    """Exact backend JSON/version policy; known native resources need explicit managed inputs."""
    info = pro.read_project(text, file=file)
    if info.status == VersionStatus.FUTURE:
        raise FutureFormatError(
            "declared native project has unsupported future versions",
            file=file,
            hint="review a project saved by supported KiCad and update its declared digest",
        )
    if (info.meta_version, info.net_settings_version) not in pro.PROJECT_VERSIONS.values():
        raise UnsupportedFormatError(
            "declared native project version pair is read-only for this writer",
            file=file,
            hint="save the declared input with supported KiCad and review its new digest",
        )
    for pointer in RESOURCE_POINTERS:
        value = _json.get(info.data, pointer)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            raise FormatError("native drawing-sheet reference is not text", file=file, locator=pointer)
        relative = value.replace("\\", "/")
        if relative.startswith("${KIPRJMOD}/"):
            relative = relative[len("${KIPRJMOD}/") :]
        parts = PurePosixPath(relative).parts
        if (
            not relative
            or relative.startswith("/")
            or ":" in parts[0]
            or ".." in parts
            or "${" in relative
            or "$(" in relative
            or any(ord(char) < 32 for char in relative)
        ):
            raise FormatError(
                "native drawing-sheet resource must be portable within the project",
                file=file,
                locator=pointer,
            )
        if not managed_frame:
            raise FormatError(
                "native drawing sheet requires an explicit design.sheet(drawing_sheet=...) input",
                file=file,
                locator=pointer,
            )
