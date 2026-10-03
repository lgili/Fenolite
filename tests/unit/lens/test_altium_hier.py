# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Module sheets in an Altium build (capability altium-build, "Module sheets in an Altium build" and the
hierarchy scenarios of "Altium build outputs"; capability altium-schematic-writer, "Project file of a
multi-sheet project" and "Harness definition files"; change c0037)."""

from __future__ import annotations

import hashlib
import json

import pytest
from _altium import HIER_PARTIAL, hier, records
from _cfb_read import read_compound

from fenolite.backends.altium import hierarchy
from fenolite.backends.altium.project import WRITE_KINDS, write_project
from fenolite.core.evidence import Level
from fenolite.dsl import Design, to_model
from fenolite.lens.altium import ALTIUM_BUILD_EVIDENCE, build_altium, generic_pins
from fenolite.lens.build import BuildOutput
from fenolite.model import canonical

PROJECT_FILES = [
    "FenoliteHier.SchLib",
    "altium_hier.Harness",
    "altium_hier.PrjPcb",
    "altium_hier.SchDoc",
    "altium_hier_flash.Harness",
    "altium_hier_flash.SchDoc",
    "altium_hier_mcu.Harness",
    "altium_hier_mcu.SchDoc",
]
LAYERS = [
    ".fenolite/board.json",
    ".fenolite/circuit.json",
    ".fenolite/findings.json",
    ".fenolite/manufacturing.json",
    ".fenolite/meta.json",
    ".fenolite/rules.json",
]


def build(design: Design | None = None, **kwargs: object) -> BuildOutput:
    design = design or hier()
    return build_altium(to_model(design), name=design.name, **kwargs)  # type: ignore[arg-type]


def test_files_of_the_hierarchy_sample() -> None:
    """Scenario "Files of the hierarchy sample"."""
    output = build(sheets="modules")
    assert sorted(output.files) == sorted([*PROJECT_FILES, *LAYERS, ".fenolite/build.json"])
    record = json.loads(output.files[".fenolite/build.json"])
    assert record["design"] == "altium_hier" and record["target"] == "altium"
    assert record["files"] == {name: hashlib.sha256(output.files[name]).hexdigest() for name in PROJECT_FILES}
    assert not [i for i in output.issues if i.severity in ("warning", "error")]


def test_flat_build_of_the_hierarchy_sample() -> None:
    """Scenario "Flat build of the hierarchy sample": the default mode."""
    output = build()
    schematic = [name for name in output.files if name.endswith((".SchDoc", ".Harness"))]
    assert schematic == ["altium_hier.SchDoc"]
    assert output.summary["sheet_mode"] == "flat" and output.summary["sheets"] == ["altium_hier.SchDoc"]
    assert (output.summary["ports"], output.summary["sheet_entries"], output.summary["harnesses"]) == (
        0,
        0,
        0,
    )
    assert output.files == build(sheets="flat").files


def test_summary_of_the_hierarchy_sample() -> None:
    summary = build(sheets="modules").summary
    assert summary["sheet_mode"] == "modules"
    assert summary["sheets"] == ["altium_hier.SchDoc", "altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"]
    assert (summary["ports"], summary["sheet_entries"], summary["harnesses"]) == (5, 5, 1)
    assert (summary["components"], summary["nets"], summary["sheet"]) == (6, 9, "A4")
    assert (summary["labels"], summary["power_ports"]) == (36, 11), "12 labels per sheet; 2 + 5 + 4 ports"
    assert summary["libraries"] == ["FenoliteHier.SchLib"] and summary["pcb_document"] is None


def test_libraries_and_layers_do_not_depend_on_the_mode() -> None:
    """Scenario "Libraries do not depend on the mode"."""
    flat, split = build().files, build(sheets="modules").files
    assert flat["FenoliteHier.SchLib"] == split["FenoliteHier.SchLib"]
    assert all(flat[name] == split[name] for name in LAYERS)
    assert flat[".fenolite/build.json"] != split[".fenolite/build.json"], "the record lists the planned files"


def test_harness_not_lowered_in_the_flat_mode() -> None:
    """Scenario "Harness not lowered in the flat mode"."""
    output = build()
    (found,) = [i for i in output.issues if i.code == "altium.not-lowered"]
    assert found.severity == "info" and "SPI" in found.message
    assert not [name for name in output.files if name.endswith(".Harness")]


def test_harness_not_lowered_in_the_ascii_form() -> None:
    """Scenario "Harness not lowered in the ASCII form"."""
    output = build(sheets="modules", form="ascii")
    (found,) = [i for i in output.issues if i.code == "altium.not-lowered"]
    assert "SPI" in found.message
    assert output.summary["harnesses"] == 0 and output.summary["ports"] == 11
    assert output.summary["sheet_entries"] == 11
    assert not [name for name in output.files if name.endswith(".Harness")]
    for name in ("altium_hier.SchDoc", "altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"):
        found_records = records(output.files[name])
        assert not any(r.get("HARNESSTYPE") for r in found_records)
    paths = [
        line for line in output.files["altium_hier.PrjPcb"].decode("ascii").split("\r\n") if "Path=" in line
    ]
    assert paths == [
        "DocumentPath=altium_hier.SchDoc",
        "DocumentPath=FenoliteHier.SchLib",
        "DocumentPath=altium_hier_flash.SchDoc",
        "DocumentPath=altium_hier_mcu.SchDoc",
    ]


def test_kept_project_file() -> None:
    """Scenario "Kept project file"."""
    output = build(sheets="modules", project_exists=True)
    assert not [name for name in output.files if name.endswith(".PrjPcb")]
    (found,) = [i for i in output.issues if i.code == "altium.sheets-not-in-project"]
    assert found.message.count(".SchDoc") == 2 and found.message.count(".Harness") == 3
    assert output.summary["kept"] == ["altium_hier.PrjPcb"]
    assert "altium.sheets-not-in-project" not in {i.code for i in build(project_exists=True).issues}


def test_project_of_the_hierarchy_sample() -> None:
    """Scenario "Project of the hierarchy sample"."""
    text = build(sheets="modules").files["altium_hier.PrjPcb"].decode("ascii")
    paths = [line.partition("=")[2] for line in text.split("\r\n") if line.startswith("DocumentPath=")]
    assert paths == [
        "altium_hier.SchDoc",
        "FenoliteHier.SchLib",
        "altium_hier_flash.SchDoc",
        "altium_hier_mcu.SchDoc",
        "altium_hier.Harness",
        "altium_hier_mcu.Harness",
        "altium_hier_flash.Harness",
    ]
    assert "HierarchyMode" not in text and text.startswith("[Design]\r\nVersion=1.0\r\n")


def test_three_harness_files_of_the_sample() -> None:
    """Scenario "Three files of the sample"."""
    files = build(sheets="modules").files
    found = {name: data for name, data in files.items() if name.endswith(".Harness")}
    assert sorted(found) == ["altium_hier.Harness", "altium_hier_flash.Harness", "altium_hier_mcu.Harness"]
    assert set(found.values()) == {b"SPI=CS,MISO,MOSI,SCK\r\n"}


def test_every_sheet_is_a_compound_file_with_its_streams() -> None:
    files = build(sheets="modules").files
    for name in ("altium_hier.SchDoc", "altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"):
        assert sorted(read_compound(files[name])) == ["Additional", "FileHeader", "Storage"]
    assert sorted(read_compound(build().files["altium_hier.SchDoc"])) == ["FileHeader", "Storage"]


def test_component_records_do_not_depend_on_the_mode() -> None:
    """A component's unique id, designator and library links are the same in both modes."""

    def components(files: dict[str, bytes]) -> dict[str, tuple[str, str, str]]:
        found: dict[str, tuple[str, str, str]] = {}
        for name, data in files.items():
            if not name.endswith(".SchDoc"):
                continue
            rows = records(data)
            for index, row in enumerate(rows):
                if row["RECORD"] == "34":
                    owner = rows[int(row["OWNERINDEX"])]
                    found[row["TEXT"]] = (
                        owner["UNIQUEID"],
                        owner["LIBREFERENCE"],
                        owner["SOURCELIBRARYNAME"],
                    )
                    assert index > int(row["OWNERINDEX"])
        return found

    flat = components(build(form="ascii").files)
    split = components(build(sheets="modules", form="ascii").files)
    assert flat == split and sorted(flat) == ["C1", "C2", "J1", "R1", "U1", "U2"]


def test_envelope_evidence() -> None:
    """Scenario "Envelope evidence" (the lens part)."""
    output = build(sheets="modules")
    assert output.evidence.level is Level.INFERRED and ALTIUM_BUILD_EVIDENCE.level is Level.INFERRED
    assert set(hierarchy.EVIDENCE.hypotheses) <= set(ALTIUM_BUILD_EVIDENCE.hypotheses)
    assert {"H-A-SCH-HIER-OPEN", "H-A-SCH-HIER-ECO", "H-A-SCH-HARN-OPEN"} <= set(output.evidence.hypotheses)
    assert len(hierarchy.EVIDENCE.hypotheses) == 9


def test_write_project_modes() -> None:
    model = generic_pins(to_model(hier()))
    flat = write_project(model, name="altium_hier")
    assert flat == write_project(model, name="altium_hier", sheets="flat")
    assert sorted(flat) == ["FenoliteHier.SchLib", "altium_hier.PrjPcb", "altium_hier.SchDoc"]
    split = write_project(model, name="altium_hier", sheets="modules")
    assert sorted(split) == PROJECT_FILES
    assert sorted(write_project(model, name="altium_hier", sheets="modules", project=False)) == [
        name for name in PROJECT_FILES if not name.endswith(".PrjPcb")
    ]
    assert "altium_harness" in WRITE_KINDS
    with pytest.raises(ValueError, match="sheet mode"):
        write_project(model, name="altium_hier", sheets="pages")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="sheet mode"):
        build(sheets="pages")


def test_partial_sample_builds_without_warnings() -> None:
    design = hier(script=HIER_PARTIAL)
    output = build(design, sheets="modules")
    assert design.name == "altium_hier_partial" and output.summary["harnesses"] == 1
    assert not [i for i in output.issues if i.severity in ("warning", "error")]
    harness = {data for name, data in output.files.items() if name.endswith(".Harness")}
    assert harness == {b"SPI=CS,HOLD,MISO,MOSI,SCK\r\n"}


def test_layer_files_keep_the_harness_interface() -> None:
    output = build(sheets="modules")
    texts = {
        name.split("/", 1)[1]: data.decode("utf-8") for name, data in output.files.items() if name in LAYERS
    }
    assert texts == canonical.dump_texts(output.design)
    kinds = {i.kind for i in output.design.circuit.interfaces}
    assert kinds == {"power", "harness"} and '"harness"' in texts["circuit.json"]


def test_no_connect_directives_stay_on_the_sheet_of_their_pin() -> None:
    """Changes c0036 and c0037 together: a marked pin of a module part gets its No ERC directive on the
    module's sheet, in both modes, and the nets still read back."""
    from _altium_read import nets_from_project, read_no_connects, read_sheet

    mark = "\nfrom fenolite.dsl import no_connect\nno_connect(u2[9], j1[4])\n"
    design = hier(append=mark)
    flat = build_altium(to_model(design), name=design.name, form="ascii")
    split = build_altium(to_model(hier(append=mark)), name=design.name, sheets="modules", form="ascii")
    assert flat.summary["no_connects"] == split.summary["no_connects"] == 2
    assert not [i for i in split.issues if i.severity in ("warning", "error")]
    marks = {
        name: read_no_connects(records(data))
        for name, data in split.files.items()
        if name.endswith(".SchDoc")
    }
    assert marks == {
        "altium_hier.SchDoc": {("J1", "4")},
        "altium_hier_flash.SchDoc": {("U2", "9")},
        "altium_hier_mcu.SchDoc": set(),
    }
    binary = build_altium(to_model(hier(append=mark)), name=design.name, sheets="modules")
    sheets = {name: read_sheet(data) for name, data in binary.files.items() if name.endswith(".SchDoc")}
    nets = nets_from_project(sheets, "altium_hier.SchDoc")
    named = {name: pins for name, pins in nets.items() if not name.startswith("<unnamed ")}
    assert sorted(named) == sorted(n.name for n in binary.design.circuit.nets) and len(named) == 9
    for sheet in sheets.values():
        kinds = [r["RECORD"] for r in sheet[0]]
        assert "22" not in kinds or kinds.index("22") > max(
            i for i, k in enumerate(kinds) if k in ("27", "25", "17")
        )
