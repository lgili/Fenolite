# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The written records read back into the model's nets (capability altium-schematic-writer, "Written
records read back"; design Decision 19 of change c0032)."""

from __future__ import annotations

import json
import re
import struct
from collections import Counter
from pathlib import Path

import pytest
from _altium import (
    EXAMPLE_NETS,
    HIER_NETS,
    HIER_PARTIAL,
    NO_CONNECT_MARKS,
    NO_CONNECT_NETS,
    SAMPLE_NETS,
    example_files,
    hier,
    hier_model,
    model_of,
    no_connect_example,
    no_connect_files,
    sample_model,
)
from _altium_read import (
    ReadError,
    SheetRecords,
    net_differences,
    nets_from_project,
    nets_from_sheet,
    pin_end,
    read_no_connects,
    read_records,
    read_schlib,
    read_sheet,
)
from _cfb_read import deframe, read_compound

from fenolite.backends.altium.project import write_project
from fenolite.dsl import Design, Net, Part, Power, connect, to_model
from fenolite.lens.altium import build_altium
from fenolite.model.design import Design as ModelDesign

ROOT = Path(__file__).resolve().parents[4]
GOLDEN = ROOT / "tests" / "data" / "altium" / "sample"
COMMITTED = (
    "altium_sample.SchDoc",
    "variants/altium_sample_lf.SchDoc",
    "variants/altium_sample_nouid.SchDoc",
)


def model_nets(model: ModelDesign) -> dict[str, set[tuple[str, str]]]:
    refs = {c.id: c.ref for c in model.circuit.components}
    return {n.name: {(refs[m.component_id], m.pin) for m in n.members} for n in model.circuit.nets}


def schdoc(model: ModelDesign, name: str = "x") -> bytes:
    return write_project(model, name=name, project=False, form="ascii")[f"{name}.SchDoc"]


def read(data: bytes) -> dict[str, set[tuple[str, str]]]:
    return nets_from_sheet(read_records(data))


def test_sample_reads_back() -> None:
    model = sample_model()
    nets = read(schdoc(model, "altium_sample"))
    assert nets == model_nets(model) == SAMPLE_NETS
    assert nets["LED_A"] == {("R1", "2"), ("D1", "2")}


@pytest.mark.parametrize("name", COMMITTED)
def test_committed_files_read_back(name: str) -> None:
    assert read((GOLDEN / name).read_bytes()) == SAMPLE_NETS


def _move_first_label(data: bytes, net: str, dx: int, dy: int) -> bytes:
    """``data`` with the first net label of ``net`` moved by (``dx``, ``dy``) units of 10 mil."""
    lines = data.split(b"\r\n")
    for index, line in enumerate(lines):
        if line.startswith(b"|RECORD=25|") and f"|TEXT={net}|".encode() in line:
            x = int(re.search(rb"\|LOCATION\.X=(\d+)", line).group(1))  # type: ignore[union-attr]
            y = int(re.search(rb"\|LOCATION\.Y=(\d+)", line).group(1))  # type: ignore[union-attr]
            line = line.replace(f"|LOCATION.X={x}|".encode(), f"|LOCATION.X={x + dx}|".encode())
            lines[index] = line.replace(f"|LOCATION.Y={y}|".encode(), f"|LOCATION.Y={y + dy}|".encode())
            return b"\r\n".join(lines)
    raise AssertionError(f"no label of {net}")


def test_a_label_off_its_stub_is_caught() -> None:
    model = sample_model()
    moved = _move_first_label(schdoc(model, "altium_sample"), "LED_A", 0, 1)  # 1 unit = 10 mil
    problems = net_differences(read(moved), model_nets(model))
    assert problems and any(p.startswith("LED_A: ") for p in problems), problems


def test_a_label_moved_along_its_stub_still_connects() -> None:
    model = sample_model()
    moved = _move_first_label(schdoc(model, "altium_sample"), "LED_A", 1, 0)
    assert net_differences(read(moved), model_nets(model)) == []


def test_weight_must_count_the_records() -> None:
    data = schdoc(sample_model(), "altium_sample").replace(b"|WEIGHT=122\r\n", b"|WEIGHT=121\r\n", 1)
    with pytest.raises(ReadError, match="WEIGHT"):
        read_records(data)


def test_owner_must_precede_its_children() -> None:
    data = schdoc(sample_model(), "altium_sample").replace(b"|OWNERINDEX=1|", b"|OWNERINDEX=99|", 1)
    with pytest.raises(ReadError, match="owner"):
        read_records(data)


def test_no_line_ends_with_a_continuation() -> None:
    data = schdoc(sample_model(), "altium_sample")
    lines = data.split(b"\r\n")
    lines[1] += b"|>"
    with pytest.raises(ReadError, match=r"\|>"):
        read_records(b"\r\n".join(lines))


def _vmid() -> Design:
    design = Design("vmid")
    vcc, vmid, gnd = Net("VCC"), Net("VMID"), Net("GND")
    r1 = Part("R1", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
    r2 = Part("R2", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
    design.add(r1, r2)
    connect(vcc, r1[1])
    connect(vmid, r1[2], r2[1])
    connect(gnd, r2[2])
    design.add(Power(vmid, gnd), Power(vcc, vmid))
    return design


def _wide() -> Design:
    """Forty two-pin parts and a ten-pin part on shared signal and supply nets, over several rows."""
    design = Design("wide")
    gnd, vcc = Net("GND"), Net("VCC")
    bus = [Net(f"D{n}") for n in range(10)]
    u1 = Part("U1", "L.SchLib:IC10", "L.PcbLib:SO10", "IC")
    design.add(u1)
    for n, net in enumerate(bus, start=1):
        connect(net, u1[n])
    for n in range(1, 41):
        part = Part(f"R{n}", "L.SchLib:RES", "L.PcbLib:R0603", "10k")
        design.add(part)
        connect(bus[n % 10], part[1])
        connect(gnd if n % 2 else vcc, part[2])
    design.add(Power(vcc, gnd))
    return design


@pytest.mark.parametrize("make", [_vmid, _wide])
def test_other_designs_read_back(make: object) -> None:
    model = model_of(make())  # type: ignore[operator]
    assert net_differences(read(schdoc(model)), model_nets(model)) == []


def test_the_reader_is_test_code_only() -> None:
    sources = (ROOT / "src").rglob("*.py")
    assert not [p for p in sources if "_altium_read" in p.read_text(encoding="utf-8")]


# --- the KiCad example (change c0034) ----------------------------------------------------------------


def test_vertical_stubs_of_the_example() -> None:
    files = example_files("ascii")
    found = read_records(files["altium_kicad.SchDoc"])
    nets = nets_from_sheet(found)
    unconnected = {k: v for k, v in nets.items() if k.startswith("<unnamed ")}
    assert sorted(unconnected.values()) == [{("U2", "2")}, {("U2", "4")}, {("U2", "8")}]
    named = {k: v for k, v in nets.items() if k not in unconnected}
    assert net_differences(named, EXAMPLE_NETS) == []
    vertical = [r for r in found if r["RECORD"] == "27" and r["X1"] == r["X2"]]
    assert vertical, "the example has up and down pins"
    labels = [r for r in found if r["RECORD"] == "25" and r.get("ORIENTATION") == "1"]
    assert labels and all(any(r["X1"] == label["LOCATION.X"] for r in vertical) for label in labels), (
        "each rotated label lies on a vertical stub"
    )


def test_pins_at_the_library_positions() -> None:
    files = example_files("ascii")
    found = read_records(files["altium_kicad.SchDoc"])
    library = read_schlib(files["altium_kicad.SchLib"])
    body_ends = {
        (storage, str(r["DESIGNATOR"])): (r["LOCATION.X"], r["LOCATION.Y"])
        for storage, rows in library.items()
        for r in rows
        if r.get("BINARY")
    }
    checked = 0
    for index, record in enumerate(found):
        if record["RECORD"] != "1":
            continue
        ox, oy = int(record["LOCATION.X"]), int(record["LOCATION.Y"])
        for pin in (r for r in found if r.get("OWNERINDEX") == str(index) and r["RECORD"] == "2"):
            relative = (int(pin["LOCATION.X"]) - ox, int(pin["LOCATION.Y"]) - oy)
            assert relative == body_ends[(record["LIBREFERENCE"], pin["DESIGNATOR"])]
            checked += 1
    assert checked == 2 + 2 + 2 + 8 + 8 + 8  # J1, R1, R2, U1 parts A and B, U2


# --- no-connect directives (change c0036) -------------------------------------------------------------

NO_CONNECT_FILE = "altium_no_connect.SchDoc"
NO_ERC_FIELDS = [
    "RECORD=22",
    "OWNERPARTID=-1",
    "COLOR=255",
    "ISACTIVE=T",
    "SUPPRESSALL=T",
    "SYMBOL=Thin Cross",
]


def _named(nets: dict[str, set[tuple[str, str]]]) -> dict[str, set[tuple[str, str]]]:
    return {k: v for k, v in nets.items() if not k.startswith("<unnamed ")}


def _binary_records(data: bytes) -> list[dict[str, str]]:
    """The records of a binary schematic after its header record, as the ASCII reader gives them."""
    return [dict(r) for r in deframe(read_compound(data)["FileHeader"])[1:]]


def _payloads(stream: bytes) -> list[bytes]:
    """The payloads of a ``FileHeader`` stream, each without its closing NUL."""
    found: list[bytes] = []
    offset = 0
    while offset < len(stream):
        (word,) = struct.unpack_from("<I", stream, offset)
        length = word & 0xFFFFFF
        payload = stream[offset + 4 : offset + 4 + length]
        assert word >> 24 == 0 and payload.endswith(b"\0")
        found.append(payload[:-1])
        offset += 4 + length
    return found


@pytest.mark.parametrize("form", ["ascii", "binary"])
def test_no_connect_example_reads_back(form: str) -> None:
    data = no_connect_files(form)[NO_CONNECT_FILE]
    found = read_records(data) if form == "ascii" else _binary_records(data)
    marks = read_no_connects(found)
    assert marks == NO_CONNECT_MARKS
    nets = nets_from_sheet(found)
    assert net_differences(_named(nets), NO_CONNECT_NETS) == []
    in_a_net = set().union(*_named(nets).values())
    assert ("U1", "3") not in marks and ("U1", "3") not in in_a_net
    assert not marks & in_a_net, "no marked pin is in a net"


def test_no_connect_marks_equal_the_model() -> None:
    files = no_connect_files("ascii")
    stored = json.loads(files[".fenolite/circuit.json"])
    refs = {c["id"]: c["ref"] for c in stored["components"]}
    model_marks = {(refs[m["component_id"]], m["pin"]) for m in stored["no_connects"]}
    assert read_no_connects(read_records(files[NO_CONNECT_FILE])) == model_marks
    assert len(to_model(no_connect_example()).circuit.no_connects) == len(model_marks) == 3


def test_no_connect_directive_records_of_the_example() -> None:
    data = no_connect_files("ascii")[NO_CONNECT_FILE]
    lines = data.split(b"\r\n")
    assert lines[-1] == b"" and lines[0].endswith(f"|WEIGHT={len(lines) - 2}".encode())
    last = [line.decode("ascii") for line in lines[-4:-1]]
    for line in last:
        fields = line[1:].split("|")
        assert [f for f in fields if not f.startswith("LOCATION.")] == NO_ERC_FIELDS
        assert [f.split("=")[0] for f in fields[2:4]] == ["LOCATION.X", "LOCATION.Y"] and len(fields) == 8
    found = read_records(data)
    assert [r["RECORD"] for r in found].count("22") == 3
    u1 = next(int(r["OWNERINDEX"]) for r in found if r["RECORD"] == "34" and r["TEXT"] == "U1")
    ends = {r["DESIGNATOR"]: pin_end(r) for r in found if r["RECORD"] == "2" and r["OWNERINDEX"] == str(u1)}
    places = [(int(r["LOCATION.X"]), int(r["LOCATION.Y"])) for r in found[-3:]]
    assert places == [ends["2"], ends["4"], ends["8"]]


def test_no_connect_directives_are_the_same_in_the_binary_form() -> None:
    ascii_lines = no_connect_files("ascii")[NO_CONNECT_FILE].split(b"\r\n")[-4:-1]
    payloads = _payloads(read_compound(no_connect_files("binary")[NO_CONNECT_FILE])["FileHeader"])
    assert payloads[-3:] == ascii_lines
    assert all(line.startswith(b"|RECORD=22|") for line in ascii_lines)


def test_no_connect_unlisted_pin_has_no_stub() -> None:
    found = read_records(no_connect_files("ascii")[NO_CONNECT_FILE])
    u1 = next(int(r["OWNERINDEX"]) for r in found if r["RECORD"] == "34" and r["TEXT"] == "U1")
    ends = {r["DESIGNATOR"]: pin_end(r) for r in found if r["RECORD"] == "2" and r["OWNERINDEX"] == str(u1)}
    wires = [r for r in found if r["RECORD"] == "27"]
    starts = {(int(w["X1"]), int(w["Y1"])) for w in wires}
    assert not {ends[d] for d in ("2", "3", "4", "8")} & starts
    kinds = [r["RECORD"] for r in found]
    assert (len(wires), kinds.count("17"), kinds.count("25")) == (8, 6, 2)


def _move_directive(data: bytes, which: int, dx: int, dy: int) -> bytes:
    """``data`` with its ``which``-th No ERC directive moved by (``dx``, ``dy``) units of 10 mil."""
    lines = data.split(b"\r\n")
    index = [i for i, line in enumerate(lines) if line.startswith(b"|RECORD=22|")][which]
    line = lines[index]
    x = int(re.search(rb"\|LOCATION\.X=(\d+)", line).group(1))  # type: ignore[union-attr]
    y = int(re.search(rb"\|LOCATION\.Y=(\d+)", line).group(1))  # type: ignore[union-attr]
    line = line.replace(f"|LOCATION.X={x}|".encode(), f"|LOCATION.X={x + dx}|".encode())
    lines[index] = line.replace(f"|LOCATION.Y={y}|".encode(), f"|LOCATION.Y={y + dy}|".encode())
    return b"\r\n".join(lines)


def _directive_at(data: bytes, which: int, at: tuple[int, int]) -> bytes:
    found = read_records(data)
    record = [r for r in found if r["RECORD"] == "22"][which]
    x, y = int(record["LOCATION.X"]), int(record["LOCATION.Y"])
    return _move_directive(data, which, at[0] - x, at[1] - y)


def test_no_connect_directive_off_its_pin_is_caught() -> None:
    data = no_connect_files("ascii")[NO_CONNECT_FILE]
    first = next(r for r in read_records(data) if r["RECORD"] == "22")
    moved = (int(first["LOCATION.X"]) + 1, int(first["LOCATION.Y"]))  # 1 unit = 10 mil
    with pytest.raises(ReadError, match=re.escape(str(moved))):
        read_no_connects(read_records(_move_directive(data, 0, 1, 0)))


def test_no_connect_directive_on_a_wire_label_or_port_is_caught() -> None:
    data = no_connect_files("ascii")[NO_CONNECT_FILE]
    found = read_records(data)
    wire = next(r for r in found if r["RECORD"] == "27")
    with pytest.raises(ReadError, match="lies on a wire"):
        read_no_connects(read_records(_directive_at(data, 0, (int(wire["X1"]), int(wire["Y1"])))))
    on_wire = {
        (x, y)
        for r in found
        if r["RECORD"] == "27"
        for x in range(min(int(r["X1"]), int(r["X2"])), max(int(r["X1"]), int(r["X2"])) + 1)
        for y in range(min(int(r["Y1"]), int(r["Y2"])), max(int(r["Y1"]), int(r["Y2"])) + 1)
    }
    for kind, what in (("25", "net label"), ("17", "power port")):
        spots = [(int(r["LOCATION.X"]), int(r["LOCATION.Y"])) for r in found if r["RECORD"] == kind]
        # every label and port of the example lies on its stub, so the wire check comes first
        assert all(spot in on_wire for spot in spots), what
    port = next(r for r in found if r["RECORD"] == "17")
    spot = (int(port["LOCATION.X"]), int(port["LOCATION.Y"]))
    moved = read_records(_directive_at(data, 0, spot))
    with pytest.raises(ReadError, match="lies on a power port"):
        read_no_connects([r for r in moved if r["RECORD"] != "27"])
    label = next(r for r in found if r["RECORD"] == "25")
    spot = (int(label["LOCATION.X"]), int(label["LOCATION.Y"]))
    moved = read_records(_directive_at(data, 0, spot))
    with pytest.raises(ReadError, match="lies on a net label"):
        read_no_connects([r for r in moved if r["RECORD"] != "27"])


def test_no_connect_two_directives_at_one_place_are_caught() -> None:
    data = no_connect_files("ascii")[NO_CONNECT_FILE]
    second = [r for r in read_records(data) if r["RECORD"] == "22"][1]
    at = (int(second["LOCATION.X"]), int(second["LOCATION.Y"]))
    with pytest.raises(ReadError, match="two No ERC directives"):
        read_no_connects(read_records(_directive_at(data, 0, at)))


def test_no_connect_reader_does_not_use_the_writer() -> None:
    text = (ROOT / "tests" / "_altium_read.py").read_text(encoding="utf-8")
    assert "fenolite.backends.altium.schdoc" not in text and "import fenolite" not in text
    assert read_no_connects(read_records(schdoc(sample_model(), "altium_sample"))) == set()


# --- hierarchy read back (change c0037, "Hierarchy read back") ---------------------------------------

HIER_SHEETS = ("altium_hier.SchDoc", "altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc")


def hierarchy_sheets(form: str = "binary", **variant: object) -> dict[str, SheetRecords]:
    """File name → the records read from each written sheet of the hierarchy sample's ``modules`` build."""
    design = hier(**variant)  # type: ignore[arg-type]
    output = build_altium(to_model(design), name=design.name, sheets="modules", form=form)  # type: ignore[arg-type]
    assert output.files, [i.message for i in output.issues]
    return {name: read_sheet(data) for name, data in output.files.items() if name.endswith(".SchDoc")}


def _edited(
    sheets: dict[str, SheetRecords], file: str, stream: int, match: dict[str, str], **change: str | None
) -> None:
    """Change (or, with ``None``, remove) keys of the one record of ``file`` that holds ``match``."""
    (record,) = (r for r in sheets[file][stream] if all(r.get(k) == v for k, v in match.items()))
    for key, value in change.items():
        if value is None:
            del record[key]
        else:
            record[key] = value


@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_hierarchy_sample_reads_back_in_both_forms(form: str) -> None:
    """Scenario "Sample reads back in both forms": the nine nets of the model, each with one name."""
    sheets = hierarchy_sheets(form)
    assert sorted(sheets) == sorted(HIER_SHEETS)
    nets = nets_from_project(sheets, "altium_hier.SchDoc")
    assert nets == model_nets(hier_model()) == HIER_NETS and len(nets) == 9
    assert net_differences(nets, HIER_NETS) == []
    has_harness = [bool(extra) for _main, extra in sheets.values()]
    assert has_harness == ([True, True, True] if form == "binary" else [False, False, False])


def test_hierarchy_record_counts_of_the_written_sample() -> None:
    """Scenarios "Symbols of the hierarchy sample" and "Ports of the hierarchy sample", on the written
    bytes."""
    sheets = hierarchy_sheets("binary")

    def counts(file: str) -> Counter[str]:
        return Counter(r["RECORD"] for r in sheets[file][0])

    top = counts("altium_hier.SchDoc")
    assert (top["15"], top["16"], top["32"], top["33"], top["27"], top["25"], top["17"]) == (
        2,
        5,
        2,
        2,
        14,
        12,
        2,
    )
    entries = [r for r in sheets["altium_hier.SchDoc"][0] if r["RECORD"] == "16"]
    assert sum("HARNESSTYPE" not in r for r in entries) == 3
    assert [r["HARNESSTYPE"] for r in entries if "HARNESSTYPE" in r] == ["SPI", "SPI"]
    mcu, flash = counts("altium_hier_mcu.SchDoc"), counts("altium_hier_flash.SchDoc")
    assert (mcu["18"], mcu["27"], mcu["25"], mcu["17"]) == (3, 16, 12, 4)
    assert (flash["18"], flash["27"], flash["25"], flash["17"]) == (2, 17, 12, 5)
    additional = Counter(r["RECORD"] for r in sheets["altium_hier.SchDoc"][1])
    assert additional == {"215": 2, "216": 8, "217": 2, "218": 2}


@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_hierarchy_unwired_entry_joins_nothing(form: str) -> None:
    """Scenario "Unwired entry joins nothing" (``partial.py``)."""
    sheets = hierarchy_sheets(form, script=HIER_PARTIAL)
    nets = nets_from_project(sheets, "altium_hier_partial.SchDoc")
    assert nets["FLASH_HOLD_N"] == {("U2", "7"), ("R1", "2")}
    assert nets == model_nets(hier_model(script=HIER_PARTIAL)) == HIER_NETS
    if form == "binary":
        entries = [r["NAME"] for _main, extra in sheets.values() for r in extra if r["RECORD"] == "216"]
        assert entries.count("HOLD") == 4 and len(entries) == 20


def test_hierarchy_nested_module_and_second_harness_read_back() -> None:
    variant = {
        "text": "mcu.add(u1, c1)",
        "new": 'decoupling = Module("decoupling")\ndecoupling.add(c1)\nmcu.add(u1, decoupling)',
        "append": '\ndesign.add(Harness("DBG", {"RST": reset_n}))\n',
    }
    nets = nets_from_project(hierarchy_sheets("binary", **variant), "altium_hier.SchDoc")
    assert nets == HIER_NETS


def test_hierarchy_renamed_port_is_caught() -> None:
    """Scenario "A renamed port is caught"."""
    sheets = hierarchy_sheets("binary")
    _edited(sheets, "altium_hier_mcu.SchDoc", 0, {"RECORD": "18", "NAME": "RESET_N"}, NAME="RESET")
    with pytest.raises(ReadError, match=r"port RESET of altium_hier_mcu\.SchDoc .* sheet symbol mcu"):
        nets_from_project(sheets, "altium_hier.SchDoc")


def test_hierarchy_entry_without_a_port_is_caught() -> None:
    sheets = hierarchy_sheets("ascii")
    main, extra = sheets["altium_hier_flash.SchDoc"]
    index = next(i for i, r in enumerate(main) if r["RECORD"] == "18" and r["NAME"] == "FLASH_WP")
    sheets["altium_hier_flash.SchDoc"] = (main[:index] + main[index + 1 :], extra)
    with pytest.raises(ReadError, match="sheet entry FLASH_WP of the sheet symbol flash has no port"):
        nets_from_project(sheets, "altium_hier.SchDoc")


def test_hierarchy_missing_sheet_file_is_caught() -> None:
    sheets = hierarchy_sheets("binary")
    _edited(
        sheets,
        "altium_hier.SchDoc",
        0,
        {"RECORD": "33", "TEXT": "altium_hier_mcu.SchDoc"},
        TEXT="other.SchDoc",
    )
    with pytest.raises(ReadError, match=r"names the file other\.SchDoc, which is not a sheet"):
        nets_from_project(sheets, "altium_hier.SchDoc")
    with pytest.raises(ReadError, match="top sheet"):
        nets_from_project(hierarchy_sheets("binary"), "missing.SchDoc")


def test_hierarchy_loose_harness_line_is_caught() -> None:
    sheets = hierarchy_sheets("binary")
    (line,) = (r for r in sheets["altium_hier_flash.SchDoc"][1] if r["RECORD"] == "218")
    line["X2"] = str(int(line["X2"]) - 5)
    with pytest.raises(ReadError, match="signal harness line ends at"):
        nets_from_project(sheets, "altium_hier.SchDoc")


def test_hierarchy_blocks_of_one_type_must_agree() -> None:
    sheets = hierarchy_sheets("binary")
    _edited(sheets, "altium_hier_mcu.SchDoc", 1, {"RECORD": "216", "NAME": "MISO"}, NAME="SDO")
    with pytest.raises(ReadError, match="harness type SPI has the entries"):
        nets_from_project(sheets, "altium_hier.SchDoc")


def test_hierarchy_moved_connector_position_is_caught() -> None:
    """The connection point comes from the connector's own keys: a wrong position leaves the line loose."""
    sheets = hierarchy_sheets("binary")
    _edited(sheets, "altium_hier_mcu.SchDoc", 1, {"RECORD": "215"}, PRIMARYCONNECTIONPOSITION="30")
    with pytest.raises(ReadError, match="signal harness line ends at"):
        nets_from_project(sheets, "altium_hier.SchDoc")


def test_hierarchy_shifted_harness_entry_breaks_the_net() -> None:
    """An entry moved one step no longer meets its wire: the net splits into two with one name."""
    sheets = hierarchy_sheets("binary")
    extra = sheets["altium_hier_flash.SchDoc"][1]
    cs = next(r for r in extra if r["RECORD"] == "216" and r["NAME"] == "CS")
    sck = next(r for r in extra if r["RECORD"] == "216" and r["NAME"] == "SCK")
    cs["DISTANCEFROMTOP"], sck["DISTANCEFROMTOP"] = sck["DISTANCEFROMTOP"], cs["DISTANCEFROMTOP"]
    with pytest.raises(ReadError, match=r"net names \['SPI_CS', 'SPI_SCK'\] are joined"):
        nets_from_project(sheets, "altium_hier.SchDoc")


def test_hierarchy_port_off_its_wire_splits_the_net() -> None:
    sheets = hierarchy_sheets("ascii")
    port = next(
        r for r in sheets["altium_hier_mcu.SchDoc"][0] if r["RECORD"] == "18" and r["NAME"] == "RESET_N"
    )
    port["LOCATION.Y"] = str(int(port["LOCATION.Y"]) + 5)
    with pytest.raises(ReadError, match="RESET_N is on two separate nets"):
        nets_from_project(sheets, "altium_hier.SchDoc")


def test_hierarchy_power_ports_join_across_sheets_and_labels_do_not() -> None:
    """Without its ports and sheet entries a labelled net falls apart, while power nets stay whole."""
    sheets = hierarchy_sheets("ascii")
    stripped = {
        name: (
            [r if r["RECORD"] not in ("15", "16", "18", "32", "33") else {"RECORD": "0"} for r in main],
            extra,
        )
        for name, (main, extra) in sheets.items()
    }
    with pytest.raises(ReadError, match="is on two separate nets"):
        nets_from_project(stripped, "altium_hier.SchDoc")
    nets = nets_from_project(sheets, "altium_hier.SchDoc")
    assert nets["VDD"] == HIER_NETS["VDD"] and nets["GND"] == HIER_NETS["GND"]


def test_hierarchy_harness_records_belong_to_the_additional_stream() -> None:
    files = build_altium(to_model(hier()), name="altium_hier", sheets="modules").files
    main, extra = read_sheet(files["altium_hier_flash.SchDoc"])
    assert not {r["RECORD"] for r in main} & {"215", "216", "217", "218"}
    assert {r["RECORD"] for r in extra} == {"215", "216", "217", "218"}
    flat = build_altium(to_model(hier()), name="altium_hier").files["altium_hier.SchDoc"]
    assert read_sheet(flat)[1] == []
    assert nets_from_sheet(read_sheet(flat)[0]) == HIER_NETS


def test_hierarchy_reader_does_not_import_the_writer() -> None:
    """Scenario "Reader does not import the writer"."""
    source = (ROOT / "tests" / "_altium_read.py").read_text(encoding="utf-8")
    assert "fenolite.backends.altium" not in source and "import fenolite" not in source
    assert "from fenolite" not in source
