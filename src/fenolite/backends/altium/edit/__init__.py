# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Edit sessions of saved Altium documents and their integrity check (capability altium-edit; change c0241).

``open(path)`` gives a ``Session`` on a PCB document (``session.Session``) or a schematic document
(``schematic.SchematicSession``); its operations are queued and made by ``commit(out)``, which reads the
result back, refuses what was not declared and writes atomically. Every operation is behind its gate in
``GATES`` (all off); ``integrity.check_pcbdoc`` is the read-only stage ``altium.integrity`` of
``fenolite check``. Nothing here is ``ALTIUM-VERIFIED``: Part J phase B decides each gate
(``docs/evidence/altium-edit.md``).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fenolite.backends.altium.edit.ops import (
    Arc,
    Comment,
    Component,
    Designator,
    Fill,
    Polygon,
    Region,
    Text,
    Track,
    Via,
    Vias,
)
from fenolite.backends.altium.edit.schematic import SCHEMATIC_GATES, Part, SchematicSession, open_schematic
from fenolite.backends.altium.edit.session import (
    EVIDENCE,
    GATES,
    OPERATIONS,
    ROWS,
    Receipt,
    Session,
    open_document,
)


def open(  # noqa: A001
    path: str | Path, *, gates: Mapping[str, bool] | None = None, project: str | Path | None = None
) -> Session | SchematicSession:
    """A session on the Altium PCB document or schematic document at ``path``, by its suffix; ``project``
    names the ``.PrjPcb`` whose sheets a schematic session checks designators against (change c0499)."""
    target = Path(path)
    if target.suffix.lower() == ".schdoc":
        return open_schematic(target, gates=gates, project=project)
    if target.suffix.lower() == ".pcbdoc":
        return open_document(target, gates=gates)
    raise ValueError(f"{target.name}: an edit session opens a .PcbDoc or a .SchDoc")


__all__ = [
    "EVIDENCE",
    "GATES",
    "OPERATIONS",
    "ROWS",
    "SCHEMATIC_GATES",
    "Arc",
    "Comment",
    "Component",
    "Designator",
    "Fill",
    "Part",
    "Polygon",
    "Receipt",
    "Region",
    "SchematicSession",
    "Session",
    "Text",
    "Track",
    "Via",
    "Vias",
    "open",
]
