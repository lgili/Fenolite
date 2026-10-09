# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored two-channel project of change c0083 (capability altium-import, "Repeated sheets as
channels", "Channel nets"): a top sheet whose sheet symbol holds a ``Repeat`` statement, and the child
sheet it repeats.

Since change c0146 the two sheets are sheet plans written by the schematic writer itself
(``binary.write_schdoc_binary``), so they carry the sheet record, the colours, the bodies and the pin
lengths of every written sheet and cannot drift from them. No build writes a ``Repeat`` statement; here it
is stated in three values of the top plan and in no record written by hand: the sheet symbol's module name
is the statement, its second crossing is named ``Repeat(OUT)``, and the bus block the writer draws beside
that entry is labelled with the bus identifier instead of the crossing's name.

The top sheet, placed by ``layout.layout_sheet``, holds ``U1`` (pins 1 and 2 on the nets ``OUT1`` and
``OUT2``), ``J1`` (pin 1 on ``VCC``), each pin on a labelled wire, the sheet symbol with the entries ``VCC``
and ``Repeat(OUT)``, and the bus ``OUT[1..2]`` with its two members. The child sheet, placed by hand from
the layout's pieces, holds ``R1`` and ``C12``: ``R1`` pin 2 and ``C12`` pin 1 on wires labelled ``MID``, and
the ports ``VCC`` and ``OUT`` on the ends of ``R1`` pin 1 and ``C12`` pin 2.
``tests/data/altium/channels/two/`` holds the same sheets as files (written by its ``author.py``). Every
value is authored for Fenolite.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping, Sequence

from fenolite.backends.altium.adapter.netlist import SheetInput
from fenolite.backends.altium.altsym import from_generic
from fenolite.backends.altium.binary import write_schdoc_binary
from fenolite.backends.altium.layout import (
    PORT_HEIGHT,
    SHEET_SIZES,
    SIDES,
    Crossing,
    PartSpec,
    PinNet,
    PlacedPart,
    PlacedPort,
    SheetPlan,
    SymbolSpec,
    layout_sheet,
    part_stubs,
    port_width,
)
from fenolite.backends.altium.read.sch import SchDocument, read_schematic
from fenolite.backends.altium.symbols import generic_symbol

TOP = "two.SchDoc"
CHILD = "two_ch.SchDoc"
PROJECT = "two.PrjPcb"
ANNOTATION = "two.Annotation"
"""An annotation file in the form the annotation reader assumes (``docs/formats/altium/project.md``, "The
annotation file"): not listed by the project file, not a file Altium wrote, not handed over in Part R."""
STATEMENT = "Repeat(CH,1,2)"
FORMAT = "$Component_$RoomName"
LIBRARY = "FenoliteChannels.SchLib"
"""The library name of the components. No such file is written: the sheets hold the graphics."""
BUS_MEMBERS = ("OUT1", "OUT2")
"""The nets of the two wires that leave the bus beside the repeated entry: the nets of ``U1``."""
CHILD_Y = 2000
"""The symbol origins of the child sheet lie this far below its top edge, in mils."""
R1_AT = (2000, (1200, 1600, 3400, 2500))
C12_AT = (5000, (4200, 1600, 6400, 2500))
"""The symbol origin (x) and the cell of each component of the child sheet, in mils of the layout frame."""


@dataclasses.dataclass(frozen=True)
class WrittenSheet:
    """A sheet plan and the document the schematic writer makes of it."""

    file: str
    plan: SheetPlan

    def data(self) -> bytes:
        return write_schdoc_binary(self.plan)

    def document(self) -> SchDocument:
        return read_schematic(self.data(), file=self.file)

    def input(self) -> SheetInput:
        """The sheet as a ``SheetInput`` of the adapter."""
        data = self.data()
        return SheetInput(self.file, hashlib.sha256(data).hexdigest(), read_schematic(data, file=self.file))


def part(
    ref: str, symbol: str, comment: str, uid: str, nets: Mapping[str, str], pins: Sequence[str] = ()
) -> PartSpec:
    """A component with the writer's generic body and the pins ``pins`` (those of ``nets`` by default),
    named ``P<designator>``; a pin of ``nets`` (pin designator to net name) is on a labelled wire."""
    body = from_generic(
        generic_symbol([(pin, f"P{pin}") for pin in pins or nets]),
        lib_ref=symbol,
        prefix=ref.rstrip("0123456789"),
        comment=comment,
        footprint=None,
    )
    joined = {pin: PinNet(net, "label") for pin, net in nets.items()}
    return PartSpec(ref, ref, comment, LIBRARY, symbol, None, uid, body, joined)


def top_plan(statement: str, entry: str, bus: str, members: Sequence[str] = BUS_MEMBERS) -> SheetPlan:
    """The top sheet: ``statement`` is the name of the sheet symbol, ``entry`` the name of its second
    sheet entry and ``bus`` the net label of the bus that entry lies on."""
    symbol = SymbolSpec(statement, CHILD, "SYMBOL01", (Crossing("VCC"), Crossing(entry, bus=tuple(members))))
    parts = [
        part("U1", "DRIVER", "DRV2", "UTOP0001", {"1": "OUT1", "2": "OUT2"}),
        part("J1", "CONN", "CONN1", "JTOP0001", {"1": "VCC"}),
    ]
    plan = layout_sheet(parts, symbols=[symbol])
    (placed,) = plan.symbols
    entries = tuple(
        item if item.bus is None else dataclasses.replace(item, bus=dataclasses.replace(item.bus, label=bus))
        for item in placed.entries
    )
    return dataclasses.replace(plan, symbols=(dataclasses.replace(placed, entries=entries),))


def on_pin(placed: PlacedPart, pin: str, name: str, port_id: str) -> PlacedPort:
    """The port ``name`` with one end on the electrical end of pin ``pin`` of ``placed``, pointing away
    from the body, without a wire and without a label: a net label on the net of a repeated port would name
    the net in every channel, where the sample wants the names that come down from the parent sheet."""
    (found,) = [p for p in placed.spec.body.pins if p.designator == pin]
    hx, hy = found.hot_end
    x, y = placed.x + hx, placed.y - hy
    width = port_width(name)
    left = x - width if SIDES[found.direction] == "left" else x
    cell = (left, y - PORT_HEIGHT // 2, left + width, y + PORT_HEIGHT // 2)
    return PlacedPort(Crossing(name, port_id=port_id), left, y, width, cell)


def child_plan() -> SheetPlan:
    """The sheet that the statement repeats, placed by hand on the A4 sheet: ``R1`` and ``C12`` side by
    side with their inner pins on labelled wires of ``MID``, and the two ports on their outer pins. The
    writer's own layout gives every port a labelled wire, so it is not used here (see ``on_pin``)."""
    r1 = part("R1", "RES", "10k", "RUID0001", {"2": "MID"}, pins=("1", "2"))
    c12 = part("C12", "CAP", "100n", "CUID0001", {"1": "MID"}, pins=("1", "2"))
    placed = [PlacedPart(spec, x, CHILD_Y, cell) for spec, x, cell in ((r1, *R1_AT), (c12, *C12_AT))]
    stubs = [stub for item in placed for stub in part_stubs(item.spec, item.x, item.y)]
    ports = (on_pin(placed[0], "1", "VCC", "TWO00001"), on_pin(placed[1], "2", "OUT", "TWO00002"))
    return SheetPlan(SHEET_SIZES[0], tuple(placed), tuple(stubs), ports=ports)


def sheets(
    statement: str = STATEMENT, *, entry: str = "Repeat(OUT)", bus: str = "OUT[1..2]"
) -> tuple[WrittenSheet, WrittenSheet]:
    """The top sheet and the child sheet; ``statement`` is the designator of the sheet symbol, ``entry``
    the name of its second sheet entry and ``bus`` the net label of the bus that entry lies on."""
    return WrittenSheet(TOP, top_plan(statement, entry, bus)), WrittenSheet(CHILD, child_plan())


def project_text(form: str = FORMAT, style: int = 0) -> str:
    """The project file of the two sheets: the three channel keys of ``[Design]`` and the documents."""
    return (
        "[Design]\r\nVersion=1.0\r\nHierarchyMode=0\r\n"
        f"ChannelRoomNamingStyle={style}\r\nChannelRoomLevelSeperator=_\r\n"
        f"ChannelDesignatorFormatString={form}\r\n\r\n"
        f"[Document1]\r\nDocumentPath={TOP}\r\n\r\n[Document2]\r\nDocumentPath={CHILD}\r\n"
    )


def annotation_text() -> str:
    """Two entries in the assumed form ``<unique-id path>=<designator>``: the top-sheet components ``U1``
    (``\\UTOP0001``) and ``J1`` (``\\JTOP0001``) renamed ``U101`` and ``J101``. A channel of the ``Repeat``
    statement has no recorded path form, so no entry names one."""
    return "\\UTOP0001=U101\r\n\\JTOP0001=J101\r\n"


def files() -> dict[str, bytes]:
    """The files of ``tests/data/altium/channels/two/`` by name."""
    top, child = sheets()
    return {
        PROJECT: project_text().encode("utf-8"),
        TOP: top.data(),
        CHILD: child.data(),
        ANNOTATION: annotation_text().encode("utf-8"),
    }
