# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``lens.altium.build_altium`` (capability altium-build, "Altium build outputs" and "Altium build
evidence"; change c0032; the schematic form of change c0033, "Altium schematic format option")."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from _altium import SAMPLE_NETS, records, sample
from _cfb_read import deframe, read_compound

from fenolite.backends.altium import binary, project
from fenolite.backends.altium.cfb import SIGNATURE
from fenolite.core.evidence import Level
from fenolite.dsl import Design, Net, Part, connect, to_model
from fenolite.lens.altium import ALTIUM_BUILD_EVIDENCE, EXPERIMENTAL, TARGET, build_altium, generic_pins
from fenolite.lens.build import RECORD_FILE, RECORD_SCHEMA, BuildOutput
from fenolite.model import canonical
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[3]
LAYERS = ("board", "circuit", "findings", "manufacturing", "meta", "rules")


def build(design: Design, **kwargs: object) -> BuildOutput:
    return build_altium(to_model(design), name=design.name, **kwargs)  # type: ignore[arg-type]


def test_files_of_the_sample() -> None:
    output = build(sample())
    assert sorted(output.files) == sorted(
        [
            "altium_sample.PrjPcb",
            "altium_sample.SchDoc",
            RECORD_FILE,
            *(f".fenolite/{n}.json" for n in LAYERS),
        ]
    )
    assert not [i for i in output.issues if i.severity in ("warning", "error")]
    assert [i.code for i in output.issues] == ["altium.generic-symbols"]


def test_files_are_the_writer_bytes() -> None:
    output = build(sample())
    written = project.write_project(output.design, name="altium_sample")
    assert {k: output.files[k] for k in written} == written


def test_build_record() -> None:
    output = build(sample())
    data = output.files[RECORD_FILE]
    assert data.endswith(b"}\n")
    record = json.loads(data)
    assert list(record) == sorted(record) and set(record) == {"design", "files", "schema", "target"}
    assert record["schema"] == RECORD_SCHEMA == "fenolite.build-record.v0" and record["target"] == "altium"
    assert record["design"] == "altium_sample"
    assert record["files"] == {
        name: hashlib.sha256(output.files[name]).hexdigest()
        for name in ("altium_sample.PrjPcb", "altium_sample.SchDoc")
    }
    assert b"2026" not in data and b'"date' not in data


def test_generic_pins_in_the_layer_files(tmp_path: Path) -> None:
    output = build(sample())
    for name, data in output.files.items():
        if name.startswith(".fenolite/") and name != RECORD_FILE:
            target = tmp_path / name.removeprefix(".fenolite/")
            target.write_bytes(data)
    loaded = canonical.load_dir(tmp_path)
    u1 = next(c for c in loaded.circuit.components if c.properties["fenolite.path"] == "power/U1")
    assert sorted((p.number, p.name, p.etype) for p in u1.pins) == [
        ("1", "1", "passive"),
        ("2", "2", "passive"),
        ("3", "3", "passive"),
    ]
    assert json.loads(output.files[".fenolite/findings.json"]) == {}
    assert canonical.dump_texts(loaded) == canonical.dump_texts(output.design)


def test_errors_produce_no_files() -> None:
    design = sample()
    design.parts["J1"].lib_id = "HDR2"
    output = build(design)
    assert output.files == {}
    found = [i for i in output.issues if i.code == "altium.lib-id-form"]
    assert len(found) == 1 and "J1" in found[0].message and found[0].severity == "error"


def test_project_exists_keeps_the_project_file() -> None:
    output = build(sample(), project_exists=True)
    assert "altium_sample.PrjPcb" not in output.files and "altium_sample.SchDoc" in output.files
    assert output.summary["kept"] == ["altium_sample.PrjPcb"]
    assert "altium.project-kept" in [i.code for i in output.issues]
    record = json.loads(output.files[RECORD_FILE])
    assert list(record["files"]) == ["altium_sample.SchDoc"]


def test_summary_of_the_sample() -> None:
    summary = build(sample()).summary
    assert dict(summary) == {
        "components": 8,
        "nets": 6,
        "labels": 6,
        "power_ports": 13,
        "sheet": "A4",
        "kept": [],
        "schematic_format": "binary",
        "experimental": True,
    }
    assert build(sample(), form="ascii").summary["schematic_format"] == "ascii"


def test_written_nets_equal_the_model() -> None:
    """The (ref, pin) pairs of each net in the written model equal the hand-written table of the sample."""
    output = build(sample())
    refs = {c.id: c.ref for c in output.design.circuit.components}
    nets = {n.name: {(refs[m.component_id], m.pin) for m in n.members} for n in output.design.circuit.nets}
    assert nets == SAMPLE_NETS


def test_generic_pins() -> None:
    design = Design("order")
    u1 = Part("U1", "L.SchLib:IC", "L.PcbLib:SO8", "x")
    design.add(u1)
    for designator in ("10", "2", "A1", "1"):
        connect(Net(f"N{designator}"), u1[designator])
    model = generic_pins(to_model(design))
    (component,) = model.circuit.components
    assert [p.number for p in component.pins] == ["1", "2", "10", "A1"]
    assert all(p.name == p.number and p.etype == "passive" for p in component.pins)
    assert generic_pins(model) == model, "components that hold pins keep them"
    again = generic_pins(to_model(design))
    assert [p.id for p in again.circuit.components[0].pins] == [p.id for p in component.pins]


def test_board_items_are_kept_in_the_model() -> None:
    design = sample()
    from fenolite.dsl import mm

    design.board(mm(50), mm(30))
    output = build(design, placed=("J1",))
    assert output.files and output.design.board is not None and output.design.board.outline is not None
    codes = [i.code for i in output.issues if i.code == "altium.not-lowered"]
    assert len(codes) == 2


def test_evidence() -> None:
    output = build(sample())
    assert output.evidence.level is Level.INFERRED
    assert {"H-A-SCH-OPEN", "H-A-SCH-NETS", "H-A-PRJ-OPEN"} <= set(output.evidence.hypotheses)
    assert ALTIUM_BUILD_EVIDENCE.level is Level.INFERRED
    assert "H-A-SCHBIN-VIEWER" in output.evidence.hypotheses
    registered = {r.id for r in load_register(ROOT / "docs" / "hypotheses.md")}
    rows = {i for i in registered if i.startswith(("H-A-SCH-", "H-A-SCHBIN-", "H-A-PRJ-"))}
    assert set(ALTIUM_BUILD_EVIDENCE.hypotheses) == rows
    assert set(project.EVIDENCE.hypotheses) <= rows
    assert set(binary.EVIDENCE.hypotheses) == {i for i in rows if i.startswith("H-A-SCHBIN-")}


def test_experimental_entry() -> None:
    assert TARGET == "altium"
    assert dict(EXPERIMENTAL) == {
        "name": "altium-schematic-writer",
        "command": "build",
        "option": "--target altium",
        "write_kinds": ["altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary"],
    }


def test_sample_schematic_holds_every_component() -> None:
    found = records(build(sample(), form="ascii").files["altium_sample.SchDoc"])
    assert sorted(r["TEXT"] for r in found if r["RECORD"] == "34") == sorted(
        ["J1", "R2", "U2", "R1", "D1", "U1", "C1", "C2"]
    )


def test_binary_by_default() -> None:
    """The default form is binary; both forms hold the same records and the same project file."""
    default, ascii_form = build(sample()), build(sample(), form="ascii")
    schdoc = default.files["altium_sample.SchDoc"]
    assert project.DEFAULT_FORM == "binary" and schdoc.startswith(SIGNATURE)
    assert ascii_form.files["altium_sample.SchDoc"].startswith(b"|HEADER=")
    assert default.files["altium_sample.PrjPcb"] == ascii_form.files["altium_sample.PrjPcb"]
    found = [dict(r) for r in deframe(read_compound(schdoc)["FileHeader"])[1:]]
    assert found == records(ascii_form.files["altium_sample.SchDoc"])
