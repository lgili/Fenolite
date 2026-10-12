# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored native template records: preservation and index/font rebasing (c0164)."""

import pytest

from fenolite.backends.altium.binary import additional_stream, file_header_stream, storage_stream
from fenolite.backends.altium.cfb import write_compound
from fenolite.backends.altium.native_template import TEMPLATE_REFERENCE, NativeTemplate
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.sch import read_schematic


def template() -> bytes:
    return write_compound(
        (
            (
                "FileHeader",
                file_header_stream(
                    [
                        [
                            ("RECORD", "31"),
                            ("FONTIDCOUNT", "2"),
                            ("FONTNAME1", "Arial"),
                            ("SIZE1", "12"),
                            ("FONTNAME2", "Courier New"),
                            ("SIZE2", "7"),
                            ("SYSTEMFONT", "1"),
                            ("SHEETSTYLE", "1"),
                            ("AREACOLOR", "123"),
                            ("CUSTOMMARGINWIDTH", "23"),
                            ("BORDERON", "T"),
                            ("REFERENCEZONESON", "T"),
                            ("OPAQUESETTING", "retained"),
                        ],
                        [("RECORD", "4"), ("FONTID", "2"), ("TEXT", "=Title"), ("LOCATION.X", "17")],
                        [("RECORD", "6"), ("OWNERINDEX", "1"), ("COLOR", "42")],
                        [("RECORD", "41"), ("NAME", "Title"), ("TEXT", "Default"), ("FONTID", "1")],
                    ]
                ),
            ),
            ("Storage", storage_stream()),
            ("OpaqueStream", b"authored opaque bytes"),
        )
    )


def circuit() -> bytes:
    return write_compound(
        (
            (
                "FileHeader",
                file_header_stream(
                    [
                        [("RECORD", "31"), ("FONTIDCOUNT", "1"), ("FONTNAME1", "Arial"), ("SIZE1", "10")],
                        [("RECORD", "41"), ("NAME", "Title"), ("TEXT", "Generated")],
                        [("RECORD", "1"), ("LIBREFERENCE", "Authored")],
                        [("RECORD", "34"), ("OWNERINDEX", "2"), ("TEXT", "R1"), ("FONTID", "1")],
                    ]
                ),
            ),
            ("Storage", storage_stream()),
        )
    )


def test_preserves_sheet_storage_and_owned_records() -> None:
    source = template()
    applied = NativeTemplate.read(source).apply(circuit())
    doc = read_schematic(applied)
    assert doc.sheet is not None
    sheet = doc.sheet.props
    assert sheet.text("OPAQUESETTING") == "retained"
    assert sheet.int("SHEETSTYLE") == 1
    assert sheet.int("AREACOLOR") == 123
    assert sheet.int("CUSTOMMARGINWIDTH") == 23
    assert sheet.bool("REFERENCEZONESON")
    assert sheet.int("SYSTEMFONT") == 1
    assert sheet.int("FONTIDCOUNT") == 3
    assert sheet.text("FONTNAME2") == "Courier New"
    assert sheet.int("SIZE2") == 7
    assert sheet.int("SIZE3") == 10
    assert sheet.text("TEMPLATEFILENAME") == TEMPLATE_REFERENCE
    assert sheet.bool("SHOWTEMPLATEGRAPHICS")
    assert doc.records[1].props.bool("ISNOTACCESIBLE")
    assert doc.records[2].props.int("OWNERINDEX") == 1
    assert doc.records[3].props.int("OWNERINDEX") == 2
    assert doc.records[2].props.int("FONTID") == 2
    assert doc.records[4].props.text("TEXT") == "Generated"
    for index, record in enumerate(doc.records):
        owner = record.props.int("OWNERINDEX", -1)
        assert owner < index
    params = [r for r in doc.records if r.props.int("RECORD") == 41]
    assert len(params) == 1
    assert doc.records[6].props.int("OWNERINDEX") == 5
    assert doc.records[6].props.int("FONTID") == 3
    assert not [i for i in doc.issues if i.severity == "error"]
    before, after = open_compound(source), open_compound(applied)
    for name in ("Storage", "OpaqueStream"):
        assert before.read(name) == after.read(name)


def test_storage_payload_is_preserved_without_decoding() -> None:
    # Storage can include compressed or opaque payloads; native application must not rebuild it.
    base = open_compound(template())
    storage = storage_stream() + b"\x03\x00\x00\x01abc"
    source = write_compound(tuple((p, storage if p == "Storage" else base.read(p)) for p in base.streams()))
    assert open_compound(NativeTemplate.read(source).apply(circuit())).read("Storage") == storage


@pytest.mark.parametrize("record", [1, 2, 15, 22, 39])
def test_rejects_circuits_and_nested_templates(record: int) -> None:
    data = write_compound(
        (
            (
                "FileHeader",
                file_header_stream(
                    [
                        [("RECORD", "31")],
                        [("RECORD", str(record))],
                    ]
                ),
            ),
        )
    )
    with pytest.raises(ValueError, match="circuits or nested"):
        NativeTemplate.read(data)


def test_rejects_ascii() -> None:
    with pytest.raises(ValueError, match="binary"):
        NativeTemplate.read(
            b"|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0\r\n|RECORD=31\r\n"
        )


def test_harness_fonts_move_and_additional_owners_stay_local() -> None:
    source = open_compound(circuit())
    additional = additional_stream(
        [
            [("RECORD", "215"), ("TEXTFONTID", "1")],
            [
                ("RECORD", "216"),
                ("OWNERINDEX", "0"),
                ("OWNERINDEXADDITIONALLIST", "T"),
                ("FONTID", "1"),
                ("NAME", "AUTHORED"),
            ],
        ]
    )
    generated = write_compound((*((p, source.read(p)) for p in source.streams()), ("Additional", additional)))
    doc = read_schematic(NativeTemplate.read(template()).apply(generated))
    assert doc.additional[0].props is not None and doc.additional[1].props is not None
    assert doc.additional[0].props.int("TEXTFONTID") == 3
    assert doc.additional[1].props.int("FONTID") == 3
    assert doc.additional[1].props.int("OWNERINDEX") == 0


@pytest.mark.parametrize(
    "bad", [[("RECORD", "4"), ("OWNERINDEX", "50")], [("RECORD", "4"), ("FONTID", "99")]]
)
def test_invalid_owner_or_font_is_refused(bad: list[tuple[str, str]]) -> None:
    data = write_compound(
        (
            (
                "FileHeader",
                file_header_stream(
                    [
                        [("RECORD", "31"), ("FONTIDCOUNT", "1")],
                        bad,
                    ]
                ),
            ),
        )
    )
    with pytest.raises(ValueError):
        NativeTemplate.read(data)


def test_unknown_template_properties_keep_exact_bytes() -> None:
    before = open_compound(template())
    raw = before.read("FileHeader")
    # Same-length raw non-ASCII value, deliberately not decoded by composition.
    changed = raw.replace(b"OPAQUESETTING=retained", b"OPAQUESETTING=\xe7\xe3\xffvalue")
    data = write_compound(
        tuple((p, changed if p == "FileHeader" else before.read(p)) for p in before.streams())
    )
    doc = read_schematic(NativeTemplate.read(data).apply(circuit()))
    assert doc.sheet is not None
    assert doc.sheet.props.raw("OPAQUESETTING") == b"\xe7\xe3\xffvalue"


def test_explicit_parameters_override_template_defaults() -> None:
    doc = read_schematic(
        NativeTemplate.read(template()).apply(circuit(), parameters=(("Title", "Override"),))
    )
    params = [r for r in doc.records if r.props is not None and r.props.int("RECORD") == 41]
    assert len(params) == 1
    assert params[0].props is not None and params[0].props.text("TEXT") == "Override"


def test_native_root_stream_names_are_case_insensitive() -> None:
    source = open_compound(template())
    data = write_compound(tuple((path.upper(), source.read(path)) for path in source.streams()))
    doc = read_schematic(NativeTemplate.read(data).apply(circuit()))
    assert doc.sheet is not None and doc.sheet.template_file_name == TEMPLATE_REFERENCE
