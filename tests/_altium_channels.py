# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored two-channel project of change c0083 (capability altium-import, "Repeated sheets as
channels", "Channel nets"): a top sheet whose sheet symbol holds a ``Repeat`` statement, and the child
sheet it repeats. Every record is authored for Fenolite with the record builders of ``_altium_records``.

The top sheet holds ``U1`` (pins 1 and 2 on the nets ``OUT1`` and ``OUT2``), ``J1`` (pin 1 on ``VCC``),
the bus ``OUT[1..2]`` and the sheet symbol with the entries ``VCC`` and ``Repeat(OUT)``. The child sheet
holds ``R1`` and ``C12``: ``R1`` pin 1 on the port ``VCC``, ``R1`` pin 2 and ``C12`` pin 1 on the net label
``MID``, ``C12`` pin 2 on the port ``OUT``. ``tests/data/altium/channels/two/`` holds the same sheets as
files (``tools/gen_altium_channels.py``).
"""

from __future__ import annotations

import _altium_records as rec

TOP = "two.SchDoc"
CHILD = "two_ch.SchDoc"
PROJECT = "two.PrjPcb"
STATEMENT = "Repeat(CH,1,2)"
FORMAT = "$Component_$RoomName"


def sheets(statement: str = STATEMENT, *, entry: str = "Repeat(OUT)", bus: str = "OUT[1..2]") -> tuple[
    rec.Sheet, rec.Sheet
]:  # fmt: skip
    """The top sheet and the child sheet; ``statement`` is the designator of the sheet symbol, ``entry``
    the name of its second sheet entry and ``bus`` the net label of the bus that entry lies on."""
    top = rec.Sheet(TOP)
    top.component("U1", [("1", 10, 10), ("2", 10, 20)], uid="UTOP0001")
    top.component("J1", [("1", 10, 60)], uid="JTOP0001")
    for number, y in (("1", 10), ("2", 20)):
        top.wire((10, y), (40, y))
        top.label(f"OUT{number}", 20, y)
    top.wire((10, 60), (100, 60))
    top.label("VCC", 20, 60)
    top.bus((50, 0), (50, 40), (100, 40))
    top.label(bus, 50, 30)
    top.symbol(statement, CHILD, (100, 70), entries=[("VCC", 0, 1), (entry, 0, 3)], uid="SYMBOL01")
    child = rec.Sheet(CHILD)
    child.component("R1", [("1", 10, 10), ("2", 10, 20)], uid="RUID0001")
    child.component("C12", [("1", 10, 30), ("2", 10, 40)], uid="CUID0001")
    child.wire((10, 10), (50, 10))
    child.port("VCC", 50, 10)
    child.wire((10, 20), (40, 20), (40, 30), (10, 30))
    child.label("MID", 20, 20)
    child.wire((10, 40), (50, 40))
    child.port("OUT", 50, 40)
    return top, child


def project_text(form: str = FORMAT, style: int = 0) -> str:
    """The project file of the two sheets: the three channel keys of ``[Design]`` and the documents."""
    return (
        "[Design]\r\nVersion=1.0\r\nHierarchyMode=0\r\n"
        f"ChannelRoomNamingStyle={style}\r\nChannelRoomLevelSeperator=_\r\n"
        f"ChannelDesignatorFormatString={form}\r\n\r\n"
        f"[Document1]\r\nDocumentPath={TOP}\r\n\r\n[Document2]\r\nDocumentPath={CHILD}\r\n"
    )


def files() -> dict[str, bytes]:
    """The files of ``tests/data/altium/channels/two/`` by name."""
    top, child = sheets()
    return {PROJECT: project_text().encode("utf-8"), TOP: top.data(), CHILD: child.data()}
