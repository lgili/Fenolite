# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The island and neck thresholds of a polygon pour from and to the zone settings (capability
altium-pcb-writer, "Polygon pour records"; capability altium-import, "Zones from polygons"; change c0446).

The source is the authored board ``tests/data/kicad/convert/roundrect_roundtrip.kicad_pcb`` with three
zones added: one with KiCad's default settings, one that removes islands below 0.1 mm² with a minimum width
of 0.1 mm, and one that never removes islands."""

from __future__ import annotations

from pathlib import Path

from fenolite.api.conversion import convert
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.model.board import Zone

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "convert" / "roundrect_roundtrip.kicad_pcb"
KEYS = ("REMOVEDEAD", "REMOVEISLANDSBYAREA", "AREATHRESHOLD", "REMOVENECKS", "NECKWIDTHTHRESHOLD")


def _zone(name: str, y0: int, settings: str) -> str:
    return f"""	(zone
		(net 0)
		(net_name "")
		(layer "B.Cu")
		(uuid "5a0c4440-7d21-4c3e-8f44-0c4446{y0:06d}")
		(name "{name}")
		(hatch edge 0.5)
		(connect_pads
			(clearance 0.5)
		)
{settings}		(polygon
			(pts
				(xy 11 {y0}) (xy 29 {y0}) (xy 29 {y0 + 2}) (xy 11 {y0 + 2})
			)
		)
	)
"""


ZONES = (
    _zone(
        "DEFAULT",
        6,
        "\t\t(min_thickness 0.25)\n\t\t(fill\n\t\t\t(thermal_gap 0.5)\n"
        "\t\t\t(thermal_bridge_width 0.5)\n\t\t)\n",
    )
    + _zone(
        "SMALL",
        11,
        "\t\t(min_thickness 0.1)\n\t\t(fill\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n"
        "\t\t\t(island_removal_mode 2)\n\t\t\t(island_area_min 0.1)\n\t\t)\n",
    )
    + _zone(
        "KEEP",
        22,
        "\t\t(min_thickness 0.25)\n\t\t(fill\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n"
        "\t\t\t(island_removal_mode 1)\n\t\t)\n",
    )
)  # fmt: skip


def _written(tmp_path: Path) -> Path:
    text = FIXTURE.read_text(encoding="utf-8")
    head, tail = text.rsplit("\t(gr_rect", 1)
    source = tmp_path / "zones.kicad_pcb"
    source.write_text(head + ZONES + "\t(gr_rect" + tail, encoding="utf-8")
    result = convert(source, to="altium", pour="outline", verify=False)
    (name,) = [key for key in result.conversion.files if key.endswith(".PcbDoc")]
    path = tmp_path / name
    path.write_bytes(result.conversion.files[name])
    return path


def test_written_thresholds_follow_the_zone(tmp_path: Path) -> None:
    """Scenario "Thresholds from the zone settings": a zone with the default settings keeps the values the kit
    verified; otherwise area removal only for the zone that removes islands below an area, and the neck width
    from the zone's minimum width; the board outline keeps its keys."""
    doc = read_pcbdoc(_written(tmp_path).read_bytes())
    found = {polygon.name: tuple(polygon.record.get(key) for key in KEYS) for polygon in doc.polygons}
    assert found == {
        "DEFAULT": ("TRUE", "TRUE", "250000000000.000000", "TRUE", "5mil"),
        "SMALL": ("TRUE", "TRUE", "15500031000.062000", "TRUE", "3.937mil"),
        "KEEP": ("FALSE", "FALSE", "250000000000.000000", "TRUE", "9.8425mil"),
    }
    board = doc.board.record.get
    assert (board("REMOVEISLANDSBYAREA"), board("AREATHRESHOLD"), board("NECKWIDTHTHRESHOLD")) == (
        "TRUE",
        "250000000000.000000",
        "5mil",
    )


def test_read_thresholds_give_the_zone_settings(tmp_path: Path) -> None:
    """Scenario "Island and neck settings of a saved polygon": the reading of the written document gives
    each zone the settings it was written from; Altium's default thresholds are the default settings."""
    board = AltiumBackend().read(_written(tmp_path)).design.board
    assert board is not None
    zones: dict[str, Zone] = {zone.name: zone for zone in board.zones}
    found = {
        name: (z.settings.island_removal, z.settings.min_island_area, z.settings.min_thickness)
        for name, z in zones.items()
    }
    default_area = 10_000_000_000_000
    assert found == {
        "DEFAULT": ("always", default_area, 250_000),
        "SMALL": ("below_area", 100_000_000_000, 100_000),
        "KEEP": ("never", default_area, 250_000),
    }
