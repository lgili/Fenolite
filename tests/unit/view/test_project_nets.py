# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project nets on the sheets of an Altium project (capability project-connectivity-view, change c0185)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.cli.cmd_view import scene_of
from fenolite.model.design import Design
from fenolite.view.project_nets import annotate, pin_nets, project_index

HIER = Path(__file__).resolve().parents[3] / "tests" / "data" / "altium" / "hier"
SHEETS = ("altium_hier.SchDoc", "altium_hier_mcu.SchDoc", "altium_hier_flash.SchDoc")


def _project() -> tuple[Design, dict[str, dict[str, Any]]]:
    path = HIER / "altium_hier.PrjPcb"
    backend: Any = registry.for_path(path)
    design = backend.read(path).content
    assert isinstance(design, Design)
    return design, {name: scene_of(HIER / name) for name in SHEETS}


def test_net_through_a_port() -> None:
    """Scenario "A net through a port": SPI_CS joins the MCU and the flash sheets."""
    design, sheets = _project()
    index = project_index(design, sheets)
    assert index["SPI_CS"]["sheets"] == ["altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"]
    assert index["SPI_CS"]["pins"] == ["U1-3", "U2-1"]
    for name in ("altium_hier_mcu.SchDoc", "altium_hier_flash.SchDoc"):
        nets = {n["project"]: n for n in annotate(sheets[name], design, index)["nets"] if "project" in n}
        assert nets["SPI_CS"]["project_pins"] == ["U1-3", "U2-1"]


def test_local_name_differs() -> None:
    """A local net is named by the project net its pins belong to, whatever its own label."""
    design, sheets = _project()
    index = project_index(design, sheets)
    scene = {
        "meta": {"counts": {}},
        "nets": [{"name": "N1", "pins": ["U1-1"]}, {"name": "ALONE", "pins": []}],
    }
    nets = annotate(scene, design, index)["nets"]
    assert nets[0]["project"] == "RESET_N" and "project" not in nets[1]
    assert pin_nets(design)["J1-3"] == "RESET_N"
