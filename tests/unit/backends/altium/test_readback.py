# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The written records read back into the model's nets (capability altium-schematic-writer, "Written
records read back"; design Decision 19 of change c0032)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from _altium import SAMPLE_NETS, model_of, sample_model
from _altium_read import ReadError, net_differences, nets_from_sheet, read_records

from fenolite.backends.altium.project import write_project
from fenolite.dsl import Design, Net, Part, Power, connect
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
