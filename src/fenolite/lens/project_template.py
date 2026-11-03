# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Checked declared native project input, never ambient discovery or a canonical field (c0351)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.kicad.pro_template import ProjectResource, read_project_resources
from fenolite.backends.kicad.pro_template import validate_project_template as validate_project_template
from fenolite.core.errors import FormatError
from fenolite.lens import native_project_context
from fenolite.lens.native_rule_context import CERTIFICATE, Binding, read_binding


@dataclass(frozen=True, slots=True)
class ProjectTemplate:
    path: Path
    text: str
    sha256: str
    resources: tuple[ProjectResource, ...] = ()
    rules: Binding | None = None
    rule_inputs: tuple[Path, ...] = ()
    context: native_project_context.Binding | None = None


def read_project_template(
    script: Path, request: tuple[str, str], *, managed_frame: bool = False
) -> ProjectTemplate:
    """Read the explicit input and its bounded exact worksheet dependencies."""
    named, expected = request
    normalized = named.replace("\\", "/")
    parts = normalized.split("/")
    if (
        normalized.startswith("/")
        or ":" in parts[0]
        or any(part in {"", ".", ".."} for part in parts)
        or not normalized.lower().endswith(".kicad_pro")
    ):
        raise FormatError("native project input must stay inside the script folder", file=named)
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise FormatError("native project input requires its declared SHA-256 digest", file=named)
    folder = script.resolve().parent
    path = folder / normalized
    if not path.resolve().is_relative_to(folder):
        raise FormatError("native project input leaves the script folder", file=named)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise FormatError("declared native project input is missing or unreadable", file=named) from error
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise FormatError(
            "declared native project digest differs; review the input and update its explicit digest",
            file=named,
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError("declared native project is not UTF-8", file=named) from error
    resources = read_project_resources(path, text, managed_frame=managed_frame)
    binding = read_binding(path, raw)
    context = native_project_context.read_binding(path, raw)
    rule_inputs = tuple(
        given
        for given in (
            path.with_suffix(".kicad_dru"),
            path.with_name(CERTIFICATE),
            path.with_name(native_project_context.CERTIFICATE),
        )
        if given.is_file() or given.is_symlink()
    )
    return ProjectTemplate(path, text, actual, resources, binding, rule_inputs, context)
