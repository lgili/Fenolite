# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read issues and strict mode of the PCB reader (capability altium-pcb-reader, "Read issues and strict
mode" and "PCB document reading", change c0041)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from _altium_long import block, document, long_pad, long_track, long_via

from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PCB_READ_ISSUE_CODES, PcbReadError, TrackRecord
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = ROOT / "src" / "fenolite" / "backends" / "altium" / "read"
MODULES = ("pcbprops", "pcbprims", "pcbstack", "pcb", "pcblib")
WHERE = re.compile(r"^[^#@]+/[^#@]+(#\d+)?(@\d+)?$")


def test_header_count_differs() -> None:
    doc = read_pcbdoc(document({"Tracks6": (5, b"".join(long_track(49) for _ in range(4)))}))
    assert len(doc.tracks) == 4
    (problem,) = doc.issues
    assert problem.code == "altium.pcb-read.count-mismatch" and problem.severity == "warning"
    assert problem.where == "Tracks6/Header"


def test_index_past_the_nets() -> None:
    nets = [block(f"|NAME=N{i}") for i in range(3)]
    doc = read_pcbdoc(document({"Nets6": nets, "Tracks6": [long_track(49, net=9), long_track(36, net=9)]}))
    assert len(doc.tracks) == 2 and doc.net_name(9) is None
    (problem,) = doc.issues
    assert problem.code == "altium.pcb-read.bad-index" and problem.where == "Tracks6/Data"
    assert "2 records in Tracks6" in problem.message


def test_bad_component_and_polygon_index() -> None:
    track = long_track(36, component=4)
    doc = read_pcbdoc(document({"Tracks6": [track]}))
    assert [i.code for i in doc.issues] == ["altium.pcb-read.bad-index"]
    assert "component" in doc.issues[0].message


def test_wrong_type() -> None:
    doc = read_pcbdoc(document({"Tracks6": [long_track(36), long_pad(114, 0)]}))
    assert [i.code for i in doc.issues] == ["altium.pcb-read.wrong-type"]
    assert len(doc.tracks) == 1 and isinstance(doc.tracks[0], TrackRecord)
    assert len(doc.others["Tracks6"]) == 1
    assert doc.rebuild("Tracks6") == long_track(36) + long_pad(114, 0)


def test_lenient_and_strict() -> None:
    whole = long_pad(114, 0)
    cut = long_pad(194, 651)[:-100]
    data = document({"Pads6": (2, whole + cut)})
    doc = read_pcbdoc(data)
    assert len(doc.pads) == 1
    (problem,) = doc.issues
    assert problem.code == "altium.pcb-read.truncated" and problem.severity == "error"
    assert problem.where == f"Pads6/Data#1@{len(whole)}"
    assert doc.trailing("Pads6") == cut and doc.rebuild("Pads6") == whole + cut
    with pytest.raises(PcbReadError) as raised:
        read_pcbdoc(data, strict=True, file="board.PcbDoc")
    assert isinstance(raised.value, FormatError)
    assert raised.value.locator == "Pads6/Data" and raised.value.offset == len(whole)
    assert raised.value.file == "board.PcbDoc"


def test_warnings_do_not_raise_in_strict_mode() -> None:
    doc = read_pcbdoc(document({"Tracks6": (5, long_track(36))}), strict=True)
    assert [i.code for i in doc.issues] == ["altium.pcb-read.count-mismatch"]


def test_codes_are_closed() -> None:
    emitted: set[str] = set()
    for module in MODULES:
        emitted |= set(re.findall(r'"(altium\.pcb-read\.[a-z-]+)"', (PACKAGE / f"{module}.py").read_text()))
    assert emitted == set(PCB_READ_ISSUE_CODES)
    assert PCB_READ_ISSUE_CODES == {
        "altium.pcb-read.truncated": "error",
        "altium.pcb-read.unknown-type": "error",
        "altium.pcb-read.missing-stream": "error",
        "altium.pcb-read.bad-stack": "error",
        "altium.pcb-read.short-record": "warning",
        "altium.pcb-read.count-mismatch": "warning",
        "altium.pcb-read.bad-index": "warning",
        "altium.pcb-read.wrong-type": "warning",
        "altium.pcb-read.bad-frame": "warning",
        "altium.pcb-read.bad-value": "warning",
        "altium.pcb-read.unlisted-footprint": "info",
    }


def test_where_form_and_messages_hold_no_file_value() -> None:
    secret = "SECRETNETNAME"
    nets = [block(f"|NAME={secret}|UNIQUEID=ZZQQZZQQ")]
    components = [block(f"|SOURCEDESIGNATOR={secret}|X=notmil")]
    doc = read_pcbdoc(
        document(
            {
                "Nets6": nets,
                "Components6": components,
                "Tracks6": (3, long_track(20) + long_track(36, net=7) + b"\x09"),
                "Vias6": (2, long_via(321, net=8)),
                "Classes6": [block("|NAME=X|KIND=x")],
            },
            board="|KIND=Protel_Advanced_PCB|FILENAME=D:\\boards\\someone\\secret.PcbDoc|LAYER1NAME=T|LAYER1NEXT=5",
        )
    )
    codes = {i.code for i in doc.issues}
    assert codes >= {
        "altium.pcb-read.short-record",
        "altium.pcb-read.unknown-type",
        "altium.pcb-read.bad-index",
        "altium.pcb-read.bad-value",
        "altium.pcb-read.bad-stack",
        "altium.pcb-read.count-mismatch",
    }
    for found in doc.issues:
        assert WHERE.match(found.where), found.where
        for value in (secret, "ZZQQZZQQ", "someone", "notmil", "secret.PcbDoc"):
            assert value not in found.message and value not in found.where
