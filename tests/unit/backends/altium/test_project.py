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
from _altium import component_index, hier_model, model_of, records, sample, sample_model

from fenolite.backends import registry
from fenolite.backends.altium import hierarchy, project
from fenolite.backends.altium.hierarchy import plan_sheets
from fenolite.backends.altium.project import (
    EVIDENCE,
    WRITE_KINDS,
    power_styles,
    split_link,
    unique_id,
    write_project,
)
from fenolite.backends.altium.schdoc import schdoc_records
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level
from fenolite.dsl import Design, Net, Part, Power, connect

PACKAGE = Path(project.__file__).parent
STDLIB_ALLOWED = {
    "__future__", "collections", "dataclasses", "decimal", "fractions", "hashlib", "re", "struct", "types",
    "typing",
}  # fmt: skip
"""``decimal``, ``fractions`` and ``types`` serve the PCB writers (change c0035)."""
PINNED_ID = "WIEFALXV"
"""``unique_id("cmp_00000000-0000-0000-0000-000000000000")``, computed once by the rule of the spec."""


def test_files_of_the_sample() -> None:
    model = sample_model()
    assert sorted(write_project(model, name="altium_sample")) == [
        "FenoliteSample.SchLib",
        "altium_sample.PrjPcb",
        "altium_sample.SchDoc",
    ]
    assert sorted(write_project(model, name="altium_sample", project=False)) == [
        "FenoliteSample.SchLib",
        "altium_sample.SchDoc",
    ]


def test_the_writers_are_not_part_of_the_registered_backend() -> None:
    """Since change c0043 the package holds the registered backend ``altium``, which reads: it offers no
    write kind, so the writers stay experimental features of ``build``."""
    assert "fenolite.backends.altium.project" in sys.modules
    (altium,) = [b for b in registry.all_backends() if b.name == "altium"]
    assert altium.capabilities().write_kinds == () and not hasattr(altium, "write")


def test_imports_only_core_and_model() -> None:
    """The package imports ``fenolite.core``, ``fenolite.model``, itself and a few pure stdlib modules: no
    file, process or environment access."""
    for path in sorted(PACKAGE.glob("*.py")):
        if path.name == "backend.py":
            continue  # the reading backend of change c0043 does the file work; its rules are its own tests
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
                        (
                            "fenolite.core.",
                            "fenolite.model.",
                            "fenolite.geometry.",
                            "fenolite.backends.altium.",
                        )
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
        "H-A-ECO-NETCLASS",
        "H-A-ECO-PRJ-KEYS",
        "H-A-ECO-ROOMS",
        "H-A-ECO-SUPPLY",
    }
    assert {h for h in EVIDENCE.hypotheses if h.startswith("H-A-ECO-")} == {
        "H-A-ECO-NETCLASS",
        "H-A-ECO-PRJ-KEYS",
        "H-A-ECO-ROOMS",
        "H-A-ECO-SUPPLY",
    }
    assert WRITE_KINDS == (
        "altium_harness",
        "altium_prjpcb",
        "altium_schdoc_ascii",
        "altium_schdoc_binary",
        "altium_schlib",
    )
    assert project.HARNESS_KIND == "altium_harness" and project.HARNESS_KIND in WRITE_KINDS


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


# --- unique ids of sheet symbols and ports (change c0037) --------------------------------------------


@pytest.mark.parametrize("form", ["ascii", "binary"])
def test_unique_ids_of_the_hierarchy_sample(form: str) -> None:
    """Scenario "Ids of the hierarchy sample": sheet symbols and ports carry ids keyed by names, components
    keep the ids of the flat build, and no other record holds ``UNIQUEID``."""
    model = hier_model()
    flat = {}
    for record in schdoc_records(project.plan_sheet(model, name="altium_hier")):
        fields = dict(record)
        if fields["RECORD"] == "1":
            flat[fields["LIBREFERENCE"], fields["UNIQUEID"]] = fields["UNIQUEID"]
    sheets = plan_sheets(model, name="altium_hier", sheets="modules", form=form)  # type: ignore[arg-type]
    components: set[str] = set()
    for sheet in sheets.sheets:
        found = [dict(record) for record in schdoc_records(sheet.plan)]
        symbols = [r for r in found if r["RECORD"] == "15"]
        files = [r["TEXT"] for r in found if r["RECORD"] == "33"]
        if sheet.module is None:
            assert files == ["altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"]
            assert [r["UNIQUEID"] for r in symbols] == [unique_id("sheet:flash"), unique_id("sheet:mcu")]
        else:
            assert not symbols and sheet.symbol_id == unique_id(f"sheet:{sheet.module}")
        for port in (r for r in found if r["RECORD"] == "18"):
            assert sheet.module is not None
            assert port["UNIQUEID"] == unique_id(f"port:{sheet.module}:{port['NAME']}")
        components |= {r["UNIQUEID"] for r in found if r["RECORD"] == "1"}
        assert all(r["RECORD"] in ("1", "15", "18") for r in found if "UNIQUEID" in r)
    assert components == set(flat.values()) and len(components) == 6
    assert components == {unique_id(c.id) for c in model.circuit.components}


def test_unique_ids_of_sheets_and_ports_depend_only_on_names() -> None:
    assert hierarchy.symbol_id("mcu") == unique_id("sheet:mcu") != unique_id("sheet:flash")
    assert hierarchy.port_id("mcu", "RESET_N") == unique_id("port:mcu:RESET_N")
    assert hierarchy.port_id("mcu", "FLASH_WP") != hierarchy.port_id("flash", "FLASH_WP")
    assert all(re.fullmatch(r"[A-Y]{8}", i) for i in (hierarchy.symbol_id("a"), hierarchy.port_id("a", "b")))


# --- net class directives (change c0048) -------------------------------------------------------------


def test_net_class_names_of_the_blink_sample() -> None:
    from _altium import blink

    assert project.net_class_names(model_of(blink())) == {"GND": "PWR", "VIN": "PWR"}
    assert project.net_class_names(sample_model()) == {}


def test_class_marks_of_the_single_sheet() -> None:
    """One mark per net of a class, in net-name order, inside the first stub of the net."""
    from _altium import blink

    plan = project.plan_sheet(model_of(blink()), name="blink")
    assert [(m.net, m.name) for m in plan.class_marks] == [("GND", "PWR"), ("VIN", "PWR")]
    for mark in plan.class_marks:
        stub = next(s for s in plan.stubs if s.net.net == mark.net)
        assert mark.vertical == stub.vertical
        assert mark.at not in (stub.start, stub.end, stub.mark)
        (x0, y0), (x1, y1), (x, y) = stub.start, stub.end, mark.at
        assert min(x0, x1) <= x <= max(x0, x1) and min(y0, y1) <= y <= max(y0, y1)
        distance = abs(x - x0) + abs(y - y0)
        assert distance == (200 if stub.length >= 300 else 100)
        assert mark.unique_id == project.unique_id(f"netclass:blink.SchDoc:{mark.net}")
        assert mark.parameter_id == project.unique_id(f"netclass:blink.SchDoc:{mark.net}:name")
    ids = [i for m in plan.class_marks for i in (m.unique_id, m.parameter_id)]
    assert len(set(ids)) == len(ids)


def test_class_marks_of_a_sheet_without_a_class() -> None:
    plan = project.plan_sheet(sample_model(), name="altium_sample")
    assert plan.class_marks == ()
    assert project.with_class_marks(plan, {}, "altium_sample.SchDoc") is plan
    assert project.with_class_marks(plan, {"NO_SUCH_NET": "X"}, "altium_sample.SchDoc") is plan


def test_class_mark_name_that_a_parameter_cannot_hold() -> None:
    """Scenario "Class name that a parameter cannot hold"."""
    from _altium import blink

    plan = project.plan_sheet(model_of(blink()), name="blink")
    with pytest.raises(ValueError, match="net class name '=PWR'"):
        project.class_marks(plan, {"GND": "=PWR"}, "blink.SchDoc")
