# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The binary schematic form (capability altium-schematic-writer, "Binary schematic form" and the scenario
"Round trip of the sample" of "Compound files read back"; change c0033; hypotheses ``H-A-SCHBIN-FRAME`` and
``H-A-SCHBIN-STORAGE``).

Containers are read with ``tests/_cfb_read.py``, written from the fact pages and not from the writer.
"""

from __future__ import annotations

import struct
from functools import cache
from typing import get_args

import pytest
from _altium import hier_model, sample_model
from _cfb_read import CfbError, deframe, read_compound

from fenolite.backends.altium import binary, project
from fenolite.backends.altium.ascii import format_record
from fenolite.backends.altium.binary import (
    EVIDENCE,
    HEADER_TEXT,
    MAX_PAYLOAD,
    additional_stream,
    file_header_stream,
    frame_record,
    header_record,
    storage_stream,
    write_schdoc_binary,
)
from fenolite.backends.altium.cfb import SIGNATURE
from fenolite.backends.altium.hierarchy import plan_sheets
from fenolite.backends.altium.project import DEFAULT_FORM, plan_sheet, write_project
from fenolite.backends.altium.schdoc import additional_records, schdoc_records
from fenolite.core.evidence import Level


@cache
def sample_streams() -> dict[str, bytes]:
    return read_compound(write_schdoc_binary(plan_sheet(sample_model())))


def test_constants_and_evidence() -> None:
    assert HEADER_TEXT == "Protel for Windows - Schematic Capture Binary File Version 5.0"
    assert binary.STORAGE_HEADER_TEXT == "Icon storage"
    assert MAX_PAYLOAD == 65535
    assert EVIDENCE.level is Level.INFERRED
    assert set(EVIDENCE.hypotheses) == {
        "H-A-SCHBIN-AD",
        "H-A-SCHBIN-CFB",
        "H-A-SCHBIN-FRAME",
        "H-A-SCHBIN-STORAGE",
        "H-A-SCHBIN-VIEWER",
    }
    assert header_record(3) == (("HEADER", HEADER_TEXT), ("WEIGHT", "3"))
    with pytest.raises(ValueError):
        header_record(-1)


def test_frame_record() -> None:
    framed = frame_record((("RECORD", "31"), ("FONTIDCOUNT", "1")))
    text = b"|RECORD=31|FONTIDCOUNT=1"
    assert framed == struct.pack("<I", len(text) + 1) + text + b"\0"
    assert deframe(framed) == [[("RECORD", "31"), ("FONTIDCOUNT", "1")]]


def test_payload_limit() -> None:
    # "|K=" + value + NUL: a value of 65 531 characters gives a payload of 65 535 bytes
    assert len(frame_record((("K", "v" * 65531),))) == 4 + 65535
    with pytest.raises(ValueError):
        frame_record((("K", "v" * 65532),))


def test_frame_refuses_what_ascii_refuses() -> None:
    for fields in ((("K", "a|b"),), (("K", "café"),), (("K", "a\r\nb"),), ()):
        with pytest.raises(ValueError):
            frame_record(fields)


def test_header_record_of_the_binary_sample() -> None:
    records = deframe(sample_streams()["FileHeader"])
    assert len(records) == 123
    head = sample_streams()["FileHeader"]
    (word,) = struct.unpack_from("<I", head, 0)
    first = head[4 : 4 + (word & 0xFFFFFF)]
    assert first == b"|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=122\0"
    assert records[1][0] == ("RECORD", "31")
    second = head[4 + len(first) + 4 :]
    assert second.startswith(b"|RECORD=31|")


def test_same_records_in_both_forms() -> None:
    model = sample_model()
    ascii_bytes = write_project(model, name="altium_sample", form="ascii")["altium_sample.SchDoc"]
    head = sample_streams()["FileHeader"]
    payloads: list[bytes] = []
    offset = 0
    while offset < len(head):
        (word,) = struct.unpack_from("<I", head, offset)
        assert word >> 24 == 0, "no record of another type is written"
        payload = head[offset + 4 : offset + 4 + (word & 0xFFFFFF)]
        assert payload.endswith(b"\0")
        payloads.append(payload[:-1])
        offset += 4 + len(payload)
    assert offset == len(head)
    joined = b"".join(p + b"\r\n" for p in payloads[1:])
    assert joined == ascii_bytes.split(b"\r\n", 1)[1]
    assert b"\r" not in head and b"\n" not in head


def test_pins_stay_text_records() -> None:
    records = deframe(sample_streams()["FileHeader"])
    pins = [r for r in records if r[0] == ("RECORD", "2")]
    assert pins, "the sample has pins"
    assert all(dict(r).get("DESIGNATOR") for r in pins)


def test_storage_stream() -> None:
    storage = sample_streams()["Storage"]
    assert len(storage) == 25
    assert storage == struct.pack("<I", 21) + b"|HEADER=Icon storage\0"
    assert storage == storage_stream()
    assert deframe(storage) == [[("HEADER", "Icon storage")]]


def test_round_trip_of_the_sample() -> None:
    """The root holds exactly the two streams, and the records after the header equal the plan's."""
    model = sample_model()
    streams = sample_streams()
    assert sorted(streams) == ["FileHeader", "Storage"]
    records = deframe(streams["FileHeader"])
    expected = [list(r) for r in schdoc_records(plan_sheet(model))]
    assert records[0] == [("HEADER", HEADER_TEXT), ("WEIGHT", str(len(expected)))]
    assert records[1:] == expected
    assert streams["FileHeader"] == file_header_stream(schdoc_records(plan_sheet(model)))


def test_forms_of_write_project() -> None:
    model = sample_model()
    binary_files = write_project(model, name="altium_sample", form="binary")
    ascii_files = write_project(model, name="altium_sample", form="ascii")
    assert binary_files["altium_sample.SchDoc"].startswith(SIGNATURE)
    assert ascii_files["altium_sample.SchDoc"].startswith(b"|HEADER=")
    assert binary_files["altium_sample.PrjPcb"] == ascii_files["altium_sample.PrjPcb"]
    assert write_project(model, name="altium_sample") == write_project(
        model, name="altium_sample", form=DEFAULT_FORM
    )
    assert DEFAULT_FORM in ("binary", "ascii")
    with pytest.raises(ValueError):
        write_project(model, name="altium_sample", form="xml")  # type: ignore[arg-type]


def test_deframe_rejects_bad_records() -> None:
    good = frame_record((("K", "v"),))
    with pytest.raises(CfbError, match="NUL"):
        deframe(good[:4] + good[4:-1] + b"x")
    with pytest.raises(CfbError, match="type"):
        deframe(struct.pack("<I", 1 << 24 | 5) + b"|K=v\0")
    assert format_record((("K", "v"),)) == "|K=v"
    assert get_args(project.SchematicForm) == ("binary", "ascii")


# --- the Additional stream (change c0037) -----------------------------------------------------------


def hier_binary(sheets: str = "modules") -> dict[str, dict[str, bytes]]:
    """File name → the streams of each binary sheet of the hierarchy sample."""
    found = plan_sheets(hier_model(), name="altium_hier", sheets=sheets, form="binary")  # type: ignore[arg-type]
    return {sheet.file: read_compound(write_schdoc_binary(sheet.plan)) for sheet in found.sheets}


def test_no_additional_stream_without_harnesses() -> None:
    """Scenario "No Additional stream without harnesses"."""
    assert sorted(sample_streams()) == ["FileHeader", "Storage"]
    (flat,) = hier_binary("flat").values()
    assert sorted(flat) == ["FileHeader", "Storage"]


def test_additional_stream_of_the_hierarchy_sample() -> None:
    """Scenario "Additional stream of the hierarchy sample"."""
    streams = hier_binary()["altium_hier.SchDoc"]
    assert sorted(streams) == ["Additional", "FileHeader", "Storage"]
    stream = streams["Additional"]
    records = deframe(stream)
    assert len(records) == 2
    (word,) = struct.unpack_from("<I", stream, 0)
    first = stream[4 : 4 + (word & 0xFFFFFF)]
    assert first == b"|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=1\0"
    assert [dict(r)["RECORD"] for r in records[1:]] == ["218"], "one signal harness line and no connector"
    assert b"\r" not in stream and b"\n" not in stream
    module = hier_binary()["altium_hier_mcu.SchDoc"]["Additional"]
    records = deframe(module)
    (word,) = struct.unpack_from("<I", module, 0)
    first = module[4 : 4 + (word & 0xFFFFFF)]
    assert first == b"|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=7\0"
    assert [dict(r)["RECORD"] for r in records[1:]] == ["215", *["216"] * 4, "217", "218"]


def test_additional_streams_of_the_module_sheets() -> None:
    plans = plan_sheets(hier_model(), name="altium_hier", sheets="modules", form="binary")
    for sheet in plans.modules:
        streams = read_compound(write_schdoc_binary(sheet.plan))
        assert sorted(streams) == ["Additional", "FileHeader", "Storage"]
        expected = [list(r) for r in additional_records(sheet.plan)]
        records = deframe(streams["Additional"])
        assert records[0] == [("HEADER", HEADER_TEXT), ("WEIGHT", "7")] and records[1:] == expected
        assert streams["Additional"] == additional_stream(additional_records(sheet.plan))
        header = deframe(streams["FileHeader"])
        assert header[1:] == [list(r) for r in schdoc_records(sheet.plan)]
        assert not any(dict(r)["RECORD"] in ("215", "216", "217", "218") for r in header[1:])
        assert streams["Storage"] == storage_stream()


def test_additional_stream_framing() -> None:
    records = [(("RECORD", "215"), ("OWNERPARTID", "-1"))]
    assert additional_stream(records) == frame_record(header_record(1)) + frame_record(records[0])
