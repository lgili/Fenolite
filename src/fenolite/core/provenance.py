# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where an imported object came from."""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.core.evidence import Evidence


@dataclass(frozen=True, slots=True)
class Provenance:
    """Origin of an imported object. ``locator`` is opaque outside the originating backend."""

    backend: str
    file: str
    file_sha256: str = field(metadata={"pattern": r"^[0-9a-f]{64}$"})
    locator: str
    evidence: Evidence = Evidence()


__all__ = ["Provenance"]
