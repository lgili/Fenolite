# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable, backend-neutral schematic block intent (c0165)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Flow = Literal["left-to-right", "top-to-bottom"]


@dataclass(frozen=True)
class BlockIntent:
    key: str
    members: tuple[str, ...]
    title: str
    anchor: str | None = None
    after: str | None = None


@dataclass(frozen=True)
class CompositionIntent:
    flow: Flow = "left-to-right"
    blocks: tuple[BlockIntent, ...] = ()
