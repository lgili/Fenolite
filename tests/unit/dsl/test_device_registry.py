# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where the devices of a script come from (change c0248; capability fenolite-component-catalog, "Device
sources and precedence" and "Project devices override shipped ones")."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.catalog.devices import parse_device, shipped_device
from fenolite.dsl import Design, DslError, Part
from fenolite.dsl.devices import ProjectDevices, installed, known_ids, project_devices, resolve

DATA = Path(__file__).resolve().parents[2] / "data" / "devices"
BUCK = parse_device((DATA / "example_buck.toml").read_text(encoding="utf-8"), file="example_buck.toml")


def test_shipped_device_resolves_as_builtin() -> None:
    found = resolve("Fenolite:R_0603")
    assert (
        found.origin == "builtin"
        and not found.overrides
        and found.device == shipped_device("Fenolite:R_0603")
    )


def test_unknown_device_names_the_closest() -> None:
    with pytest.raises(DslError, match="closest: Fenolite:R_0603"):
        Part("R1", device="Fenolite:R_0630")
    with pytest.raises(DslError):
        Part("R1", device="")


def test_project_devices_are_installed_for_a_run() -> None:
    assert project_devices() == ProjectDevices()
    with pytest.raises(DslError):
        resolve(BUCK.id)
    with installed(ProjectDevices((BUCK,), {BUCK.id: "devices/example_buck.toml"})):
        found = resolve(BUCK.id)
        assert found.origin == "authored" and found.device is BUCK and BUCK.id in known_ids()
    with pytest.raises(DslError):
        resolve(BUCK.id)


def test_override_of_a_shipped_device() -> None:
    own = replace(shipped_device("Fenolite:R_0603"), summary="project resistor")
    with installed(ProjectDevices((own,))):
        found = resolve("Fenolite:R_0603")
    assert found.origin == "authored" and found.overrides and found.device.summary == "project resistor"


def test_design_records_win() -> None:
    design = Design("d")
    mine = replace(BUCK, summary="design record")
    design.devices(mine)
    with installed(ProjectDevices((BUCK,))):
        part = design.part("U1", device=BUCK.id)
    assert part.device is mine and part.device_origin == "authored"
    design.devices(mine)  # the same record twice is one registration
    with pytest.raises(DslError, match="registered twice"):
        design.devices(replace(BUCK, summary="other"))
    with pytest.raises(DslError, match="DeviceDef"):
        design.devices("Example:BUCK_6V_2A")  # type: ignore[arg-type]


def test_design_records_need_the_design_part_call() -> None:
    design = Design("d")
    design.devices(BUCK)
    with pytest.raises(DslError, match="unknown device"):
        Part("U1", device=BUCK.id)
