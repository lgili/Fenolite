# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stack-up file (``.stackup``) read byte for byte (capability altium-project-reader, change c0042).

A stack-up file is one property text. ``read_stackup`` keeps every field and types the entries that
carry a thickness: copper (``COPTHICK``) and dielectrics (``DIELHEIGHT``), from top to bottom. Facts:
``docs/formats/altium/stackup-file.md``.
"""

# evidence: see read.project

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.altium.read.proptext import PropRecord, parse_fields, parse_length
from fenolite.backends.altium.read.textfile import TextBytes, split_text, text_issue
from fenolite.core.errors import FormatError, Issue
from fenolite.core.units import Nm

VERSION_KEY = "STACKUPVERSION"
_LAYER_KEY = re.compile(r"LAYER_V([0-9]+)_([0-9]+)([^0-9].*)", re.DOTALL)
StackEntryKind = Literal["copper", "dielectric"]


@dataclass(frozen=True, slots=True)
class StackEntry:
    """One layer of the stack with a thickness, at position ``index`` of the keys ``LAYER_V<g>_<index>``.
    ``thickness`` is in nanometres (``None`` when it does not parse); ``epsilon_r`` is the ``DIELCONST``
    text as written. An absent key gives ``None`` (numbers) or ``""`` (texts)."""

    index: int
    name: str
    layer_id: int | None
    kind: StackEntryKind
    thickness: Nm | None
    dielectric_type: int | None
    epsilon_r: str
    material: str
    component_placement: int | None


@dataclass(frozen=True, slots=True)
class StackupFile:
    """A stack-up file: its bytes (``form``), every field (``record``), ``STACKUPVERSION`` as text, the
    typed entries from top to bottom and the issues of reading it."""

    form: TextBytes
    record: PropRecord
    version: str
    layers: tuple[StackEntry, ...]
    issues: tuple[Issue, ...]

    def to_bytes(self) -> bytes:
        return self.form.to_bytes()


def _integer(text: str | None) -> int | None:
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def read_stackup(data: bytes, *, file: str = "") -> StackupFile:
    """Read the stack-up file ``data``; ``to_bytes()`` of the result equals ``data``. ``FormatError`` when
    the text does not start with ``|STACKUPVERSION=`` after an optional byte-order mark, or for a
    compound file or a NUL byte. Warnings: ``altium.stackup.unknown-form`` for layer keys of more than
    one generation, ``altium.stackup.length-unreadable`` for a thickness that is not a length."""
    issues: list[Issue] = []
    form = split_text(data, file=file, issues=issues)
    body = data[len(form.bom) :]
    if not body.startswith(f"|{VERSION_KEY}=".encode()):
        raise FormatError(f"not a stack-up file: the text does not start with |{VERSION_KEY}=", file=file)
    record = parse_fields(body.decode(form.encoding, errors="replace"))
    layers: dict[int, dict[int, dict[str, str | None]]] = {}
    for key, value in record.fields:
        match = _LAYER_KEY.fullmatch(key)
        if match:
            entry = layers.setdefault(int(match.group(1)), {}).setdefault(int(match.group(2)), {})
            entry.setdefault(match.group(3), value)
    entries: list[StackEntry] = []
    if layers:
        generation = max(layers)
        if len(layers) > 1:
            found = ", ".join(str(g) for g in sorted(layers))
            issues.append(
                text_issue(
                    "altium.stackup.unknown-form",
                    f"layer keys of more than one generation ({found}); "
                    f"the entries are read from generation {generation}",
                    file,
                )
            )
        for index in sorted(layers[generation]):
            keys = layers[generation][index]
            if "COPTHICK" in keys:
                kind: StackEntryKind = "copper"
                text = keys["COPTHICK"]
            elif "DIELHEIGHT" in keys:
                kind = "dielectric"
                text = keys["DIELHEIGHT"]
            else:
                continue
            thickness = parse_length(text or "")
            if thickness is None:
                issues.append(
                    text_issue(
                        "altium.stackup.length-unreadable",
                        f"layer {index}: the thickness {text!r} is not a length "
                        "(a decimal number and mil or mm)",
                        file,
                    )
                )
            entries.append(
                StackEntry(
                    index=index,
                    name=keys.get("NAME") or "",
                    layer_id=_integer(keys.get("LAYERID")),
                    kind=kind,
                    thickness=thickness,
                    dielectric_type=_integer(keys.get("DIELTYPE")),
                    epsilon_r=keys.get("DIELCONST") or "",
                    material=keys.get("DIELMATERIAL") or "",
                    component_placement=_integer(keys.get("COMPONENTPLACEMENT")),
                )
            )
    return StackupFile(form, record, record.get(VERSION_KEY) or "", tuple(entries), tuple(issues))


__all__ = ["VERSION_KEY", "StackEntry", "StackEntryKind", "StackupFile", "read_stackup"]
