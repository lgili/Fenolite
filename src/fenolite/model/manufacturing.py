# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Manufacturing layer: the artefact manifest and pick-and-place rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, Udeg
from fenolite.model.base import Entity

ArtefactState = Literal["generated", "checked", "roundtrip-ok", "oracle-verified", "native-verified"]


@dataclass(frozen=True, slots=True)
class Artefact:
    """A generated file with the tool that produced it and how far it was verified."""

    path: str
    sha256: str = field(metadata={"pattern": r"^[0-9a-f]{64}$"})
    tool: str
    tool_version: str = ""
    revision: str = ""
    variant: str = ""
    evidence: Evidence = Evidence()
    state: ArtefactState = "generated"


@dataclass(frozen=True, slots=True)
class Manifest(Entity):
    """The manufacturing layer of a design (``manufacturing.json``)."""

    artefacts: tuple[Artefact, ...] = ()


@dataclass(frozen=True, slots=True)
class PnpRow:
    """One pick-and-place row (positions in nm, rotation in µdeg)."""

    ref: str
    value: str
    footprint: str
    x: Nm
    y: Nm
    rotation: Udeg
    side: Literal["top", "bottom"]


__all__ = ["Artefact", "ArtefactState", "Manifest", "PnpRow"]
