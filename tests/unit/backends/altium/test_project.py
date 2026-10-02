# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The writer package (capability altium-schematic-writer, "Altium writer package", "Stable component
unique ids" and the issue of "Custom sheet"; change c0032)."""

from __future__ import annotations

import ast
import dataclasses
import re
import sys
from pathlib import Path

import pytest
from _altium import component_index, model_of, records, sample, sample_model

from fenolite.backends import registry
from fenolite.backends.altium import project
from fenolite.backends.altium.project import (
    EVIDENCE,
    WRITE_KINDS,
    power_styles,
    split_link,
    unique_id,
    write_project,
)
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level
from fenolite.dsl import Design, Net, Part, Power, connect

PACKAGE = Path(project.__file__).parent
STDLIB_ALLOWED = {"__future__", "collections", "dataclasses", "hashlib", "re", "struct", "typing"}
PINNED_ID = "WIEFALXV"
"""``unique_id("cmp_00000000-0000-0000-0000-000000000000")``, computed once by the rule of the spec."""


def test_files_of_the_sample() -> None:
    model = sample_model()
    assert sorted(write_project(model, name="altium_sample")) == [
        "altium_sample.PrjPcb",
        "altium_sample.SchDoc",
    ]
    assert list(write_project(model, name="altium_sample", project=False)) == ["altium_sample.SchDoc"]


def test_not_a_registered_backend() -> None:
    assert "fenolite.backends.altium.project" in sys.modules
    assert all(b.name != "altium" for b in registry.all_backends())


def test_imports_only_core_and_model() -> None:
    """The package imports ``fenolite.core``, ``fenolite.model``, itself and a few pure stdlib modules: no
    file, process or environment access."""
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id not in {"open", "exec", "eval", "__import__"}, path.name
                continue
            for name in names:
                if name.startswith("fenolite."):
                    assert name.startswith(
                        ("fenolite.core.", "fenolite.model.", "fenolite.backends.altium.")
                    ), f"{path.name} imports {name}"
                else:
                    assert name.split(".")[0] in STDLIB_ALLOWED, f"{path.name} imports {name}"


def test_evidence_and_kinds() -> None:
    assert EVIDENCE.level is Level.INFERRED
    assert set(EVIDENCE.hypotheses) <= {
        "H-A-SCH-OPEN",
        "H-A-SCH-LINEEND",
        "H-A-SCH-UID",
        "H-A-SCH-NETS",
        "H-A-SCH-LINK",
        "H-A-PRJ-OPEN",
    }
    assert WRITE_KINDS == ("altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("FenoliteSample.SchLib:HDR2", ("FenoliteSample.SchLib", "HDR2")),
        ("My Parts.IntLib:R:0603", ("My Parts.IntLib", "R:0603")),
        ("HDR2", None),
        (":HDR2", None),
        ("Lib.SchLib:", None),
        ("", None),
    ],
)
def test_split_link(text: str, expected: tuple[str, str] | None) -> None:
    assert split_link(text) == expected


# --- requirement "Stable component unique ids" -------------------------------------------------------


def test_unique_id_form() -> None:
    keys = [f"cmp_{n:08d}" for n in range(1000)]
    ids = [unique_id(k) for k in keys]
    assert all(re.fullmatch(r"[A-Y]{8}", i) for i in ids)
    assert ids == [unique_id(k) for k in keys]
    assert len(set(ids)) == len(ids)


def test_unique_id_pinned_value() -> None:
    assert unique_id("cmp_00000000-0000-0000-0000-000000000000") == PINNED_ID


def test_component_unique_ids_are_keyed_by_component_id() -> None:
    model = sample_model()
    found = records(write_project(model, name="altium_sample", form="ascii")["altium_sample.SchDoc"])
    for component in model.circuit.components:
        assert found[component_index(found, component.ref)]["UNIQUEID"] == unique_id(component.id)
    assert [r["RECORD"] for r in found if "UNIQUEID" in r] == ["1"] * 8


# --- power styles -------------------------------------------------------------------------------------


def test_power_styles_of_the_sample() -> None:
    model = sample_model()
    names = {n.id: n.name for n in model.circuit.nets}
    assert {names[k]: v for k, v in power_styles(model).items()} == {
        "GND": "ground",
        "VIN": "bar",
        "+5V": "bar",
    }


def _vmid() -> Design:
    design = Design("vmid")
    vcc, vmid, gnd = Net("VCC"), Net("VMID"), Net("GND")
    r1, r2 = (
        Part("R1", "L.SchLib:RES", "L.PcbLib:R0603", "1k"),
        Part("R2", "L.SchLib:RES", "L.PcbLib:R0603", "1k"),
    )
    design.add(r1, r2)
    connect(vcc, r1[1])
    connect(vmid, r1[2], r2[1])
    connect(gnd, r2[2])
    design.add(Power(vmid, gnd), Power(vcc, vmid))
    return design


def test_a_net_high_in_one_supply_and_low_in_another() -> None:
    found = records(write_project(model_of(_vmid()), name="vmid", form="ascii")["vmid.SchDoc"])
    styles = {(r["TEXT"], r["STYLE"]) for r in found if r["RECORD"] == "17"}
    assert styles == {("VCC", "2"), ("VMID", "2"), ("GND", "4")}


# --- errors the build checks first -----------------------------------------------------------------


def test_member_pin_the_component_does_not_hold() -> None:
    model = sample_model()
    u2 = model.by_ref["U2"]
    fewer = dataclasses.replace(u2, pins=u2.pins[:-1])
    with pytest.raises(ValueError, match="holds no pin"):
        write_project(model.replace_entity(fewer), name="altium_sample")


@pytest.mark.parametrize(
    ("ref", "change"),
    [
        ("R2", {"value": "=Value"}),
        ("R2", {"value": "10µF"}),
        ("R2", {"lib_symbol_ref": "RES"}),
        ("R2", {"lib_footprint_ref": "FenoliteSample.PcbLib:"}),
        ("R2", {"ref": "R 2 "}),
    ],
)
def test_unwritable_component(ref: str, change: dict[str, str]) -> None:
    model = sample_model()
    changed = dataclasses.replace(model.by_ref[ref], **change)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        write_project(model.replace_entity(changed), name="altium_sample")


def test_unwritable_net_name_and_design_name() -> None:
    model = sample_model()
    net = model.nets_by_name["EN"]
    with pytest.raises(ValueError, match="net name"):
        write_project(model.replace_entity(dataclasses.replace(net, name="E|N")), name="altium_sample")
    with pytest.raises(ValueError, match="design name"):
        write_project(model, name="a|b")


# --- the issue of scenario "Custom sheet" ----------------------------------------------------------


def test_custom_sheet_issue() -> None:
    design = Design("big")
    a, b = Net("A"), Net("B")
    for n in range(1, 701):
        part = Part(f"R{n}", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
        design.add(part)
        connect(a, part[1])
        connect(b, part[2])
    issues: list[Issue] = []
    files = write_project(model_of(design), name="big", issues=issues, form="ascii")
    assert [(i.code, i.severity) for i in issues] == [("altium.sheet-custom", "warning")]
    sheet = files["big.SchDoc"].split(b"\r\n")[1].decode("ascii")
    assert re.search(r"\|USECUSTOMSHEET=T\|CUSTOMX=\d+\|CUSTOMY=\d+$", sheet) and "SHEETSTYLE" not in sheet


def test_no_issue_on_a_standard_sheet() -> None:
    issues: list[Issue] = []
    write_project(model_of(sample()), name="altium_sample", issues=issues)
    assert issues == []
