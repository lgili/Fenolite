# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the functions of one board import share: the ids, the census, the issues, the layer map and the
nets (change c0043). Plain data; no function here maps a record."""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.backends.altium.adapter.codes import Census
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.adapter.layers import LayerMap
from fenolite.core.errors import Issue
from fenolite.core.provenance import Provenance


@dataclass
class Context:
    """The state of one import of a PCB document or library."""

    ids: Ids
    layers: LayerMap
    file: str
    sha256: str
    census: Census = field(default_factory=Census)
    issues: list[Issue] = field(default_factory=lambda: [])
    net_ids: dict[int, str] = field(default_factory=lambda: {})
    """Net index of the document → model net id."""
    net_names: dict[int, str] = field(default_factory=lambda: {})

    def provenance(self, locator: str) -> Provenance:
        return self.ids.provenance(self.file, self.sha256, locator)

    def net(self, index: int | None) -> str | None:
        return None if index is None else self.net_ids.get(index)

    def net_name(self, index: int | None) -> str | None:
        return None if index is None else self.net_names.get(index)


__all__ = ["Context"]
