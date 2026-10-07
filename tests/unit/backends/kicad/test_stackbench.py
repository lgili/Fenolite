# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The hermetic half of the stack-up benches (capability kicad-oracle, "Stack-up job file parity"; change
c0101): every bench parses, every case is listed once, and the readers of the job file judge authored
job files as the oracle tests expect them to."""

from __future__ import annotations

from fractions import Fraction

import _stackbench as sb
import pytest

from fenolite.backends.kicad import stackup
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.model.board import Stackup

TARGETS = (9, 10)


def node_of(text: str) -> Node:
    setup = parse(text).find("setup")
    assert setup is not None
    found = setup.find("stackup")
    assert found is not None
    return found


def test_counts_and_cases_are_listed_once() -> None:
    assert sb.COUNTS == (2, 4, 6, 8)  # every count of c0100
    assert len(set(sb.INCOMPLETE)) == 7 and len(set(sb.USED)) == 2
    assert not set(sb.INCOMPLETE) & set(sb.USED)
    ids = list(sb.stackup_probes(lambda: None))  # type: ignore[arg-type, return-value]
    assert len(ids) == len(set(ids))
    wanted = {f"pcb-stackup-{kind}-{n}" for kind in ("job", "default") for n in sb.COUNTS}
    wanted |= {f"pcb-stackup-incomplete-{case}" for case in sb.INCOMPLETE}
    wanted |= {f"pcb-stackup-{case}" for case in sb.USED}
    wanted |= {"pcb-stackup-resave", "pcb-stackup-resave-defaults", "pcb-stackup-ipc-thickness"}
    wanted |= {"build-stackup-job"}
    assert set(ids) == wanted
    majors = {pid: m for pid, (_, m) in sb.stackup_probes(lambda: None).items()}  # type: ignore[arg-type, return-value]
    assert {pid for pid, m in majors.items() if m == (10,)} == {
        "pcb-stackup-resave",
        "pcb-stackup-resave-defaults",
        "pcb-stackup-ipc-thickness",
    }


def test_benches_hold_what_the_requirement_names() -> None:
    """Together: a dielectric of two sheets, a colour, a mask of thickness 0, an empty and a named finish."""
    done = [stackup.complete(sb.bench_stackup(n), created_layers(n)) for n in sb.COUNTS]  # type: ignore[arg-type]
    entries = [e for found in done for e in found.layers]
    names = [[e.name for e in found.layers if e.kind == "dielectric"] for found in done]
    assert any(len(found) != len(set(found)) for found in names)
    assert any(e.color for e in entries)
    assert any(e.kind == "soldermask" and e.thickness == 0 for e in entries)
    assert {bool(found.finish) for found in done} == {True, False}
    assert any(found.impedance_controlled for found in done)


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("count", sb.COUNTS)
def test_job_and_default_benches_parse(count: int, target: int) -> None:
    assert sb.reader_verdict(sb.job_text(count, target)) == (True, [])
    assert sb.reader_verdict(sb.default_text(count, target)) == (False, [])
    assert parse(sb.default_text(count, target)).find("setup").find("stackup") is None  # type: ignore[union-attr]


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("case", sb.INCOMPLETE)
def test_incomplete_cases_parse_and_are_refused_by_the_reader(case: str, target: int) -> None:
    assert sb.reader_verdict(sb.case_text(case, target)) == (False, ["kicad.board.stackup-unused"])


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("case", sb.USED)
def test_used_cases_parse_and_are_read(case: str, target: int) -> None:
    assert sb.reader_verdict(sb.case_text(case, target)) == (True, [])
    assert node_of(sb.case_text(case, target)) != node_of(sb.job_text(4, target))


@pytest.mark.parametrize("target", TARGETS)
def test_other_benches_parse(target: int) -> None:
    rows = node_of(sb.resave_defaults_text(target)).nodes("layer")
    assert len(rows) == 9 and len(node_of(sb.resave_defaults_text(target)).nodes()) == 9  # no tail
    present, codes = sb.reader_verdict(sb.thin_general_text(target))
    assert present and codes == ["kicad.board.stackup-thickness"]


def job_of(found: Stackup, **general: object) -> dict[str, object]:
    """The job file KiCad 10.0.6 writes for a completed stack-up, authored from the measured form."""
    entries: list[dict[str, object]] = []
    for entry in found.layers:
        row: dict[str, object] = {"Type": sb.JOB_TYPES[entry.kind]}
        if entry.color:
            row["Color"] = entry.color
        if entry.kind in ("copper", "dielectric", "soldermask"):
            row["Thickness"] = float(Fraction(entry.thickness, 1_000_000))
        if entry.kind == "dielectric" and entry.material:
            row["Material"] = entry.material
        if entry.kind == "dielectric" and found.impedance_controlled:
            row["DielectricConstant"] = entry.epsilon_r
            row["LossTangent"] = entry.loss_tangent
        entries.append(row)
    specs: dict[str, object] = {
        "BoardThickness": float(Fraction(found.thickness(), 1_000_000)),
        "Finish": found.finish or "None",
    }
    if found.impedance_controlled:
        specs["ImpedanceControlled"] = True
    specs.update(general)
    return {"GeneralSpecs": specs, "MaterialStackup": entries}


@pytest.mark.parametrize("count", sb.COUNTS)
def test_job_differences(count: int) -> None:
    layers = created_layers(count)  # type: ignore[arg-type]
    declared = sb.bench_stackup(count)
    job = job_of(stackup.complete(declared, layers))
    assert sb.job_differences(job, declared, layers) == []
    assert sb.job_differences(job_of(stackup.complete(declared, layers), Finish="x"), declared, layers)
    assert sb.job_differences(
        job_of(stackup.complete(declared, layers), BoardThickness=1.6), declared, layers
    )
    fewer = {**job, "MaterialStackup": job["MaterialStackup"][1:]}  # type: ignore[index]
    assert sb.job_differences(fewer, declared, layers)
    assert sb.thickness_verdict(job) == "present"


def test_thickness_verdicts() -> None:
    assert sb.thickness_verdict(None) == "inconclusive"
    assert sb.thickness_verdict({"MaterialStackup": [{"Type": "Copper"}, {"Type": "Legend"}]}) == "absent"
    mixed = {"MaterialStackup": [{"Type": "Copper", "Thickness": 0.035}, {"Type": "Dielectric"}]}
    assert sb.thickness_verdict(mixed) == "different"


def test_default_differences() -> None:
    def default(count: int, each: float) -> dict[str, object]:
        rows: list[dict[str, object]] = [{"Type": "SolderMask", "Thickness": 0.01}]
        for k in range(count):
            rows.append({"Type": "Copper", "Thickness": 0.035})
            if k < count - 1:
                rows.append({"Type": "Dielectric", "Thickness": each, "Material": "FR4"})
        rows.append({"Type": "SolderMask", "Thickness": 0.01})
        return {"GeneralSpecs": {"Finish": "None"}, "MaterialStackup": rows}

    for count, each in ((2, 1.51), (4, 0.48), (6, 0.274), (8, 0.1857)):
        assert sb.default_differences(default(count, each), count) == []
    assert sb.default_differences(default(4, 0.5), 4)


def test_kicad_defaults_fill_only_dielectrics() -> None:
    filled = sb.with_kicad_defaults(sb.bench_stackup(2))
    core = next(e for e in filled.layers if e.kind == "dielectric")
    assert (core.material, core.epsilon_r, core.loss_tangent) == ("FR4", "4.5", "0.02")
    assert all(not e.epsilon_r for e in filled.layers if e.kind != "dielectric")


def test_six_layer_blink_holds_a_gap_of_two_sheets() -> None:
    design = sb.stackup_blink_six()
    assert design.copper == 6 and design.stack is not None
    names = [name for name, _ in design.stack.entries]
    assert names.count("dielectric 3") == 2 and names[1] == "F.Cu" and names[-2] == "B.Cu"


def test_stackup_blink_is_the_scenario_design() -> None:
    design = sb.stackup_blink()
    assert design.stack is not None and design.stack.finish == "ENIG" and len(design.stack.entries) == 5
