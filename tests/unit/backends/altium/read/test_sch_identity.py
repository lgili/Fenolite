# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Nothing read is lost (capability altium-schematic-reader, "Nothing read is lost")."""

from __future__ import annotations

import dataclasses
import json
import struct
import zlib
from pathlib import Path

import pytest
from _altium_sch_build import (
    ASCII_HEADER,
    BINARY_HEADER,
    SHEET,
    WORKED_PIN,
    ascii_doc,
    component_text,
    frame_bytes,
    pin_frac_stream,
    schdoc,
    schlib,
    short,
    stream,
)
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "tests" / "data" / "altium"
EMBEDDED = (
    bytes([0xD0]) + short(b"a.bmp") + struct.pack("<I", len(zlib.compress(b"BM"))) + zlib.compress(b"BM")
)


def _fixtures() -> dict[str, bytes]:
    malformed = stream([f"|HEADER={BINARY_HEADER}|WEIGHT=4", SHEET]) + frame_bytes(0, b"|RECORD=27")
    malformed += stream([(1, WORKED_PIN + b"\x01"), (7, b"odd"), "RECORD=28|Text=no leading bar|"])
    return {
        "document": schdoc(
            [SHEET, "|RECORD=1|PARTCOUNT=2", "|RECORD=2|OWNERINDEX=1|NAME=A", "|RECORD=209|X=1"]
        ),
        "harness": schdoc([SHEET], additional=["|RECORD=215", "|RECORD=216|OWNERINDEXADDITIONALLIST=T"]),
        "storage": schdoc(
            [SHEET, "|RECORD=30|FILENAME=a.bmp"], storage=stream(["|HEADER=Icon storage", (1, EMBEDDED)])
        ),
        "opaque": schdoc(
            [SHEET], storage=stream(["|HEADER=Icon storage", (1, b"???")]), extra=[("Extra", b"12")]
        ),
        "malformed": schdoc([], file_header=malformed),
        "mixed case": schdoc(
            [b"|Record=31|FontIdCount=1|Size1=10", b"|Record=25|Text=caf\xe9|%UTF8%Text=caf\xc3\xa9"]
        ),
        "ascii": ascii_doc(
            [
                SHEET,
                "|RECORD=27|LOCATIONCOUNT=1|>",
                "|X1=1|Y1=2",
                "",
                f"|HEADER={ASCII_HEADER}",
                "|RECORD=216",
            ]
        ),
        "ascii lf": b"\xef\xbb\xbf" + ascii_doc([SHEET, "|RECORD=25|TEXT=A"], eol=b"\n").removesuffix(b"\n"),
        "library": schlib(
            [
                (
                    "Q",
                    [component_text("Q"), (1, WORKED_PIN), (1, WORKED_PIN[:-3]), "|RECORD=14"],
                    [("PinFrac", pin_frac_stream([(0, 1, 2, 3)]))],
                ),
                (
                    "R",
                    [component_text("R"), (1, WORKED_PIN + b"tail")],
                    [("PinTextData", b"x"), ("Other", b"y")],
                ),
            ],
            section_keys={"Q": "Q"},
            tail=b"\x01\x02",
        ),
    }


def _read(data: bytes) -> sch.SchDocument | object:
    kind = sch.detect(data)
    return read_schlib(data) if kind == "library" else sch.read_schematic(data)


def _committed() -> list[Path]:
    return sorted(path for path in DATA.rglob("*") if path.suffix.lower() in (".schdoc", ".schlib"))


@pytest.mark.parametrize("name", sorted(_fixtures()))
def test_identity_on_the_authored_fixtures(name: str) -> None:
    result = _read(_fixtures()[name])
    assert sch.check_identity(result) == ()  # type: ignore[arg-type]


@pytest.mark.parametrize("path", _committed(), ids=lambda path: str(path.relative_to(DATA)))
def test_identity_on_the_committed_altium_files(path: Path) -> None:
    result = _read(path.read_bytes())
    assert sch.check_identity(result) == ()  # type: ignore[arg-type]


def test_identity_sees_a_change() -> None:
    document = sch.read_schematic(_fixtures()["document"])
    streams = {**document.streams, "FileHeader": document.streams["FileHeader"] + b"\x00"}
    changed = dataclasses.replace(document, streams=streams)
    assert sch.check_identity(changed) == ("FileHeader",)


KEY = st.text(st.sampled_from("ABCXYZ._%0123456789"), min_size=0, max_size=6).map(
    lambda key: key.encode("latin-1")
)
VALUE = st.binary(max_size=8).map(lambda raw: raw.replace(b"|", b"").replace(b"\0", b""))
FIELD = st.one_of(
    st.tuples(KEY, VALUE).map(lambda pair: pair[0] + b"=" + pair[1]),
    KEY,
    st.just(b"RECORD=27"),
    st.just(b"RECORD=2"),
    st.just(b"OWNERINDEX=0"),
)
PROPERTY_LIST = st.lists(FIELD, max_size=8).map(lambda fields: b"|" + b"|".join(fields))
FRAME = st.one_of(
    PROPERTY_LIST.map(lambda text: (0, text + b"\0")),
    PROPERTY_LIST.map(lambda text: (0, text)),
    st.tuples(st.integers(0, 255), st.binary(max_size=40)),
    st.just((1, WORKED_PIN)),
)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(FRAME, max_size=12), st.lists(FRAME, max_size=4))
def test_property_identity_under_mutation(
    main: list[tuple[int, bytes]], extra: list[tuple[int, bytes]]
) -> None:
    file_header = stream([f"|HEADER={BINARY_HEADER}|WEIGHT={len(main)}", *main])
    data = schdoc([], file_header=file_header, additional=extra)
    document = sch.read_schematic(data)
    assert sch.check_identity(document) == ()
    library = read_schlib(schlib([("Q", [component_text("Q"), *main])]))
    assert sch.check_identity(library) == ()


@settings(max_examples=100, deadline=None)
@given(st.lists(PROPERTY_LIST, min_size=1, max_size=8), st.sampled_from([b"\r\n", b"\n"]))
def test_property_identity_of_the_ascii_form(lines: list[bytes], eol: bytes) -> None:
    data = ascii_doc([SHEET, *lines], eol=eol)
    try:
        document = sch.read_schematic(data)
    except FormatError:
        return
    assert sch.encode_stream(document, "ascii") == data


def test_census_holds_no_value() -> None:
    data = schdoc(
        [SHEET, "|RECORD=25|TEXT=SECRET_NET|LOCATION.X=12|LOCATION.X_FRAC=1", "|RECORD=209|AUTHOR=SECRET_NET"]
    )
    document = sch.read_schematic(data)
    dumped = json.dumps(document.census())
    assert "SECRET_NET" not in dumped
    census = document.census()
    assert census["records by id"] == {"209": 1, "25": 1, "31": 1}
    assert census["lengths"] == {"lengths": 1, "lengths not exact in nm": 1, "lengths with a fraction": 1}
    library = read_schlib(schlib([("SECRET_PART", [component_text("SECRET_PART"), (1, WORKED_PIN)])]))
    assert "SECRET_PART" not in json.dumps(library.census())


def test_census_contents() -> None:
    document = sch.read_schematic(_fixtures()["mixed case"])
    census = document.census()
    wanted = (
        "form",
        "header",
        "records by id",
        "unknown record ids",
        "unknown keys by id",
        "duplicated keys by id",
    )
    wanted += ("lengths", "streams", "issues", "key case", "text")
    assert set(wanted) <= set(census)
    assert census["header"] == {"schematic-binary": 1}
    assert census["key case"] == {"mixed-case": 6}
    assert census["text"] == {"non-ASCII value": 1, "twin equal": 1}
    library = read_schlib(_fixtures()["library"])
    lib_census = library.census()
    assert lib_census["binary pin strings"] == {"2": 1, "5": 2}
    assert lib_census["side streams"] == {"PinFrac": 1, "PinTextData": 1}


def test_merge() -> None:
    from fenolite.backends.altium.read.sch.census import merge

    one = sch.read_schematic(_fixtures()["document"]).census()
    total = merge([one, one])
    assert total["files"] == 2
    assert total["records by id"] == {key: 2 * value for key, value in one["records by id"].items()}  # type: ignore[union-attr]
    with pytest.raises(TypeError):
        merge([{"a": "text"}])
