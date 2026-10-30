# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The route decision record (change c0280; capability cli-contract, "Route decision record", scenario "A
stable record")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.routing.decisions import (
    SCHEMA,
    Decisions,
    Locked,
    RecordCorridor,
    RecordEnd,
    RecordTrack,
    RecordVia,
    Rejected,
    dumps,
    loads,
    read,
    record_path,
    with_entries,
)


def _record() -> Decisions:
    track = RecordTrack("F.Cu", 250_000, (Point(52_100_000, 9_600_000), Point(52_100_000, 10_650_000)))
    via = RecordVia(Point(52_100_000, 10_650_000), 600_000, 300_000, ("F.Cu", "B.Cu"))
    ends = (
        RecordEnd("pad", "C3-2", Point(52_100_000, 9_600_000), ("F.Cu",)),
        RecordEnd("zone", "role.ground.GND.B.Cu", None, ("B.Cu",)),
    )
    corridor = RecordCorridor(
        "role.corridor.kelvin_R1.VA", ("F.Cu",), (Point(0, 0), Point(1, 0), Point(1, 1))
    )
    return Decisions(
        "buck.kicad_pcb",
        (
            Locked(
                "c-ffff000000000000",
                "p-2",
                "join:VL:a~b",
                "VL",
                (),
                (track,),
                (corridor,),
                ("keep-away=clearance",),
                "1",
            ),
            Locked(
                "c-9b1e0d77a4c2f310",
                "p-1",
                "fanout:GND:C3-2",
                "GND",
                ends,
                (track, via),
                (),
                (),
                "5e1d0c3b2a491807",
            ),
        ),
        (Rejected("c-0a6f2d3e9c1b4d58", "connection:SDA:U1-5~R7-1", "crosses the gate loop"),),
    )


def test_a_stable_record(tmp_path: Path) -> None:
    """Writing, reading and writing again gives equal bytes; entries are sorted by subject, then id."""
    data = dumps(_record())
    again = dumps(loads(data))
    assert again == data and data.endswith(b"\n")
    held = json.loads(data)
    assert held["schema"] == SCHEMA and [e["subject"] for e in held["locked"]] == [
        "fanout:GND:C3-2",
        "join:VL:a~b",
    ]
    assert "at" not in held["locked"][0]["ends"][1]
    path = tmp_path / "r.json"
    path.write_bytes(data)
    assert read(path, board="buck.kicad_pcb") == loads(data)
    assert read(tmp_path / "none.json", board="x.kicad_pcb") == Decisions("x.kicad_pcb")


@pytest.mark.parametrize(
    ("change", "pointer"),
    [
        (lambda d: d.update(extra=1), "/extra"),
        (lambda d: d.update(schema="other"), "/schema"),
        (lambda d: d["locked"][0].update(score=3), "/locked/0/score"),
        (lambda d: d["locked"][0]["items"][0].update(width="wide"), "/locked/0/items/0/width"),
        (lambda d: d["rejected"][0].pop("reason"), "/rejected/0"),
    ],
)
def test_a_malformed_record_is_refused(change: object, pointer: str) -> None:
    """A record with an unknown key, another schema or a wrong value raises the error ``route`` maps to
    ``FEN-3004``, naming the JSON pointer."""
    data = json.loads(dumps(_record()))
    change(data)  # type: ignore[operator]
    with pytest.raises(FormatError) as raised:
        loads(json.dumps(data), file="r.json")
    assert raised.value.locator == pointer and raised.value.file == "r.json"
    with pytest.raises(FormatError):
        loads(b"{not json", file="r.json")


def test_paths_and_entries(tmp_path: Path) -> None:
    board = tmp_path / "b.kicad_pcb"
    assert record_path(board, built=True) == tmp_path / ".fenolite" / "route-decisions.json"
    assert record_path(board, built=False) == tmp_path / "b.route-decisions.json"
    record = _record()
    dropped = with_entries(record, forget=["c-9b1e0d77a4c2f310", "c-0a6f2d3e9c1b4d58"])
    assert [e.candidate for e in dropped.locked] == ["c-ffff000000000000"] and dropped.rejected == ()
    added = with_entries(dropped, rejected=[Rejected("p-1", "fanout:GND:C3-2", "")])
    assert [e.id for e in added.rejected] == ["p-1"]
