# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Builds of sixteen and thirty-two copper layers (capability design-dsl, "Builds of up to thirty-two copper
layers"; change c0277, task 1.3): planes, zones and script copper on deep inner layers, the copper guard
and the viewer's colours. Each test builds a blink variant in ``tmp_path``, in-process."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board

STAMP = "2026-10-30T00:00:00Z"
BOARD = "design.board(mm(50), mm(30))"
NETS = 'vin, gnd, led_drv, led_a = Net("VIN"), Net("GND"), Net("LED_DRV"), Net("LED_A")'
DEEP = """
design.track(
    "led_a",
    r1.pad(2), (mm(36), mm(9)),
    via_step(mm(36), mm(14), to="In13.Cu", diameter=mm(0.6), drill=mm(0.3)),
    (mm(41.5), mm(14)),
    via_step(mm(41.5), mm(17), to="F.Cu", diameter=mm(0.6), drill=mm(0.3)),
    (mm(41.5), mm(20)), d1.pad(2),
    width=mm(0.3),
)
"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def variant(folder: Path, copper: int, planes: str, append: str = "") -> Path:
    """The blink with its nets before a board of ``copper`` layers and the planes ``planes``."""
    script = blink_variant(folder, append=append)
    text = script.read_text(encoding="utf-8")
    text = text.replace(f"{NETS}\n", "").replace(
        BOARD, f"{NETS}\ndesign.board(mm(50), mm(30), copper={copper}, planes={planes})"
    )
    text = text.replace(
        "import Design, Net, Part, Power, connect, mm",
        "import Design, Net, Part, Power, connect, mm, via_step",
    )
    script.write_text(text, encoding="utf-8")
    return script


def build(script: Path, out: Path, target: int):  # noqa: ANN201
    return run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip


def rows(layers) -> list[tuple[str, str | None, str | None]]:  # noqa: ANN001
    found = []
    for layer in layers:
        if layer.kind == "copper":
            bag = dict(layer.ext["kicad"].payload)
            found.append((layer.name, bag.get("number"), bag.get("type")))
    return found


@pytest.mark.parametrize("target", [9, 10])
def test_sixteen_layers_with_planes(tmp_path: Path, target: int) -> None:
    """Scenario "Sixteen layers with planes"."""
    zones = '\ndesign.zone(gnd, layers=("In1.Cu",))\ndesign.zone(vin, layers=("In14.Cu",))\n'
    script = variant(tmp_path / "src", 16, '{"In1.Cu": gnd, "In14.Cu": vin}', DEEP + zones)
    out = tmp_path / "out"
    reply = build(script, out, target)
    assert reply.exit_code == 0, reply.error
    back = read_board(out / "blink.kicad_pcb")
    assert back.board is not None
    expected = [(name, number, kind) for name, number, kind in rows(created_layers(16))]
    planes = {"In1.Cu", "In14.Cu"}
    assert rows(back.board.layers) == [
        (name, number, "power" if name in planes else kind) for name, number, kind in expected
    ]
    assert len(expected) == 16
    deep = [track for track in back.board.tracks if track.layer == "In13.Cu"]
    assert len(deep) == 2  # (36, 14) to (41.5, 14) to (41.5, 17), between the two vias
    stepped = [via for via in back.board.vias if (via.position.x - 100_000_000) in (36_000_000, 41_500_000)]
    assert len(stepped) == 2
    assert sorted(z.layers for z in back.board.zones) == [("In1.Cu",), ("In14.Cu",)]
    codes = {i["code"] for i in reply.envelope["issues"]}  # type: ignore[index]
    assert not {c for c in codes if c.startswith(("kicad.copper", "build.plane"))}, codes


def test_thirty_two_layers(tmp_path: Path) -> None:
    """A board of thirty-two layers with a plane on ``In30.Cu``: every row of ``created_layers(32)``, the
    plane typed ``power``, a zone on the deepest layer, and the same bytes on a second build."""
    zone = '\ndesign.zone(gnd, layers=("In30.Cu",))\n'
    script = variant(tmp_path / "src", 32, '{"In30.Cu": gnd}', zone)
    out = tmp_path / "out"
    reply = build(script, out, 10)
    assert reply.exit_code == 0, reply.error
    first = (out / "blink.kicad_pcb").read_bytes()
    back = read_board(out / "blink.kicad_pcb")
    assert back.board is not None
    found = rows(back.board.layers)
    assert [row[0] for row in found] == ["F.Cu", *(f"In{k}.Cu" for k in range(1, 31)), "B.Cu"]
    assert found[-2] == ("In30.Cu", "62", "power")
    assert [z.layers for z in back.board.zones] == [("In30.Cu",)]
    assert build(script, out, 10).exit_code == 0
    assert (out / "blink.kicad_pcb").read_bytes() == first


def test_viewer_colours_every_inner_layer() -> None:
    """The viewer gives each inner layer of thirty-two a colour, cycling its inner palette."""
    from fenolite.view.scene import INNER

    assert len(INNER) >= 2
    colours = [INNER[k % len(INNER)] for k in range(30)]
    assert all(colours) and len(set(colours)) == len(INNER)


def test_exports_and_specctra_on_sixteen_layers(tmp_path: Path) -> None:
    """One Gerber per copper layer of sixteen, and a Specctra design file with sixteen layers whose two
    planes are written ``(type power)``."""
    from fenolite.backends.kicad.frame import board_pads
    from fenolite.backends.kicad.layers import plane_layers
    from fenolite.backends.kicad.outline import board_outline
    from fenolite.backends.specctra.dsn import DsnDefaults, write_dsn
    from fenolite.backends.specctra.lexer import parse as parse_dsn
    from fenolite.exports.plan import gerber_layers

    zones = '\ndesign.zone(gnd, layers=("In1.Cu",))\ndesign.zone(vin, layers=("In14.Cu",))\n'
    script = variant(tmp_path / "src", 16, '{"In1.Cu": gnd, "In14.Cu": vin}', zones)
    out = tmp_path / "out"
    assert build(script, out, 10).exit_code == 0
    back = read_board(out / "blink.kicad_pcb")
    names = [row[0] for row in rows(created_layers(16))]
    assert list(gerber_layers(back)[:16]) == names and gerber_layers(back)[16] != "In14.Cu"
    assert plane_layers(back) == ("In1.Cu", "In14.Cu")
    defaults = DsnDefaults(width=250_000, clearance=200_000, via_diameter=600_000, via_drill=300_000)
    result = write_dsn(
        back,
        pads=board_pads(back),
        outline=tuple(tuple(ring) for ring in board_outline(back).rings),
        selected=("LED_A", "LED_DRV"),
        defaults=defaults,
        plane_layers=plane_layers(back),
    )
    structure = parse_dsn(result.text).first("structure")
    assert structure is not None
    layers = [node for node in structure.lists if node.head == "layer"]
    assert [str(node.items[0]) for node in layers] == names
    power = [
        str(node.items[0]) for node in layers if "power" in " ".join(str(i) for i in node.lists[0].items)
    ]
    assert power == ["In1.Cu", "In14.Cu"]
