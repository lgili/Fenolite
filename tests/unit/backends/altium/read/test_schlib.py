# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic library container (capability altium-schematic-reader, "Schematic library container")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium_sch_build import LIBRARY_HEADER, component_text, frame_bytes, pin_payload, schlib, stream

from fenolite.backends.altium.cfb import Storage, write_compound
from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.schlib import encode_stream, read_schlib
from fenolite.core.errors import FormatError, Issue

ROOT = Path(__file__).resolve().parents[5]
SAMPLE = ROOT / "tests" / "data" / "altium" / "sample" / "FenoliteSample.SchLib"


def test_fenolites_own_library() -> None:
    data = SAMPLE.read_bytes()
    issues: list[Issue] = []
    library = read_schlib(data, issues=issues)
    assert issues == []
    header = library.header.props
    assert header is not None
    listed = [header.text(f"LIBREF{i}") for i in range(header.int("COMPCOUNT"))]
    assert len(library.components) == 6
    assert [component.name for component in library.components] == listed
    assert all(isinstance(component.component, sch.Component) for component in library.components)
    for path, content in library.streams.items():
        assert encode_stream(library, path) == content, path
    assert sch.check_identity(library) == ()
    assert library.fonts == (sch.Font(1, "Times New Roman", 10),)
    assert library.header_tail == b"" and library.listed_names == ()


def test_section_key() -> None:
    lib_ref = "CONNECTOR-HEADER-2X20-RIGHT-ANGLE-SHROUD"
    key = lib_ref[:31]
    assert (len(lib_ref), len(key)) == (40, 31)
    header_fields = f"|WEIGHT=2|COMPCOUNT=1|LIBREF0={lib_ref}|PARTCOUNT0=2"
    data = schlib(
        [(key, [component_text(lib_ref)])], header_fields=header_fields, section_keys={lib_ref: key}
    )
    issues: list[Issue] = []
    library = read_schlib(data, issues=issues)
    (component,) = library.components
    assert component.name == lib_ref and component.storage_name == key
    assert library.section_keys == {lib_ref: key}
    assert issues == []
    assert library.get(lib_ref.lower()) is component
    assert sch.check_identity(library) == ()


def test_section_key_with_a_slash() -> None:
    lib_ref = "A/B"
    header_fields = f"|WEIGHT=2|COMPCOUNT=1|LIBREF0={lib_ref}"
    data = schlib(
        [("A_B", [component_text(lib_ref)])], header_fields=header_fields, section_keys={lib_ref: "A/B"}
    )
    issues: list[Issue] = []
    library = read_schlib(data, issues=issues)
    assert [component.name for component in library.components] == ["A/B"]
    assert issues == []


def test_storage_the_header_does_not_list() -> None:
    header_fields = "|WEIGHT=3|COMPCOUNT=1|LIBREF0=ZETA"
    data = schlib(
        [("ALPHA", [component_text("ALPHA")]), ("ZETA", [component_text("ZETA")])],
        header_fields=header_fields,
    )
    issues: list[Issue] = []
    library = read_schlib(data, issues=issues)
    assert [component.storage_name for component in library.components] == ["ZETA", "ALPHA"]
    assert sorted((issue.code, issue.severity) for issue in issues) == [
        ("altium.sch.weight-mismatch", "warning"),
        ("altium.schlib.unlisted-component", "info"),
    ]


def test_owner_inside_data() -> None:
    records = [component_text("A"), "|RECORD=44", "|RECORD=45|OWNERINDEX=1", "|RECORD=45|OWNERINDEX=7"]
    issues: list[Issue] = []
    library = read_schlib(schlib([("A", records)]), issues=issues)
    component = library.components[0]
    data = component.records
    assert data[2].owner == sch.RecordRef("data", 1)
    assert data[3].owner == sch.RecordRef("data", 0)
    assert data[1].owner == sch.RecordRef("data", 0)
    assert data[0].owner is None
    assert issues == []
    assert component.children() == (data[1], data[3])


def test_missing_and_no_component_and_empty_data() -> None:
    header_fields = "|WEIGHT=4|COMPCOUNT=3|LIBREF0=A|LIBREF1=GONE|LIBREF2=B|LIBREF3=C"
    components = [("A", ["|RECORD=14"]), ("B", []), ("C", [component_text("C"), (1, pin_payload())])]
    issues: list[Issue] = []
    library = read_schlib(schlib(components, header_fields=header_fields), issues=issues)
    assert [component.storage_name for component in library.components] == ["A", "B", "C"]
    assert library.components[0].component is None
    assert library.components[1].records == ()
    codes = [issue.code for issue in issues]
    assert codes == [
        "altium.schlib.missing-component",
        "altium.schlib.no-component",
        "altium.sch.empty-stream",
    ]
    assert library.components[1].name == "B"


def test_storage_without_data_and_unknown_root_stream() -> None:
    entries = [
        ("FileHeader", stream([f"|HEADER={LIBRARY_HEADER}|WEIGHT=2|COMPCOUNT=1|LIBREF0=A"])),
        ("Storage", stream(["|HEADER=Icon storage"])),
        ("Odd", b"xyz"),
        Storage("A", (("Data", stream([component_text("A")])),)),
        Storage("NoData", (("Other", b"1"),)),
    ]
    issues: list[Issue] = []
    library = read_schlib(write_compound(entries), issues=issues)
    assert len(library.components) == 1
    assert library.extra_streams == {"Odd": b"xyz", "NoData/Other": b"1"}
    assert [issue.code for issue in issues] == ["altium.sch.unknown-stream"] * 2
    assert sch.check_identity(library) == ()


def test_header_errors() -> None:
    with pytest.raises(FormatError) as caught:
        read_schlib(write_compound([("Storage", b"")]), file="l.SchLib")
    assert (caught.value.locator, caught.value.file) == ("FileHeader", "l.SchLib")
    with pytest.raises(FormatError) as caught:
        read_schlib(write_compound([("FileHeader", stream(["|HEADER=Other"]))]))
    assert caught.value.locator == "FileHeader/record 0"
    with pytest.raises(FormatError):
        read_schlib(b"not a compound file")
    with pytest.raises(FormatError):
        read_schlib(write_compound([("FileHeader", b"\x01")]))


def test_name_list_after_the_header() -> None:
    names = [b"A", b"BB"]
    tail = len(names).to_bytes(4, "little") + b"".join(frame_bytes(0, bytes([len(n)]) + n) for n in names)
    library = read_schlib(schlib([("A", [component_text("A")]), ("BB", [component_text("BB")])], tail=tail))
    assert library.listed_names == ("A", "BB")
    assert library.header_tail == tail
    assert sch.check_identity(library) == ()
    odd = read_schlib(schlib([("A", [component_text("A")])], tail=b"\x07"))
    assert odd.listed_names == () and odd.header_tail == b"\x07"
    assert sch.check_identity(odd) == ()


def test_get_and_parts() -> None:
    library = read_schlib(SAMPLE.read_bytes())
    with pytest.raises(KeyError):
        library.get("nothing")
    component = library.components[0]
    assert component.parts == range(1, 2) and component.modes == range(1)
    assert component.pins == component.of_type(sch.Pin)


def test_encode_stream_names() -> None:
    library = read_schlib(SAMPLE.read_bytes())
    with pytest.raises(KeyError):
        encode_stream(library, "Nothing/Data")
    with pytest.raises(KeyError):
        encode_stream(library, "Other")
