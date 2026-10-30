# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Finding identities, aligned with their issues (c0256)."""

import pytest

from fenolite.checks.stages import StageResult
from fenolite.checks.subjects import SUBJECT_KINDS, Subject
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence


def test_misaligned_subjects_refused_and_empty_accepted():
    issues = (Issue("length.out-of-range", "error", "long"),) * 2
    subject = Subject("net", "net_test", "SIGNAL")
    with pytest.raises(ValueError, match="aligned"):
        StageResult("length.rules", "errors", Evidence(), issues, subjects=((subject,),))
    assert StageResult("length.rules", "errors", Evidence(), issues).subjects == ()
    assert StageResult("length.rules", "errors", Evidence(), issues, subjects=((subject,), ())).subjects


def test_misaligned_closed_kinds_and_identity_required():
    assert SUBJECT_KINDS == (
        "component",
        "pin",
        "pad",
        "net",
        "netclass",
        "interface",
        "track",
        "arc",
        "via",
        "zone",
        "rule_area",
        "rule",
    )
    with pytest.raises(ValueError, match="kind"):
        Subject("footprint", "fp_test", "R1")
    with pytest.raises(ValueError, match="id"):
        Subject("net", "", "SIGNAL")
    assert Subject("net", "net_test", "SIGNAL").to_json() == {
        "kind": "net",
        "id": "net_test",
        "name": "SIGNAL",
    }


def test_subjects_length_and_envelope_indices():
    from dataclasses import replace

    from fenolite.checks.stages import CheckReport
    from fenolite.checks.subjects import for_issues
    from fenolite.cli.cmd_check import subject_rows
    from fenolite.model.circuit import Net
    from fenolite.model.design import Design

    design = Design.new("subjects", seed=0)
    design = replace(
        design,
        circuit=replace(design.circuit, nets=(Net(id="net_p", name="SK_P"), Net(id="net_n", name="SK_N"))),
    )
    item = Issue("length.skew-out-of-range", "error", "net SK_N against SK_P at 12 mm", where="SK_N")
    subjects = for_issues(design, (item,))
    assert {s.name for s in subjects[0]} == {"SK_P", "SK_N"}
    stage = StageResult("length.rules", "errors", Evidence(), (item,), subjects=subjects)
    first = Issue("check.cache-unreadable", "warning", "cache")
    report = CheckReport((stage,), (first, item), Evidence())
    assert subject_rows(report) == [{"issue": 1, "items": [s.to_json() for s in subjects[0]]}]


CAPACITOR = """schema = "fenolite.device.v0"
id = "Test:CAP_12V"
summary = "authored for the tests"
symbol = "Fenolite:Capacitor"
footprint = "Fenolite:Chip_0805"
evidence = "UNVERIFIED"
class = "capacitor"
ends = ["P1", "P2"]

[pins]
P1 = "1"
P2 = "2"

[ratings]
voltage = { abs_max = "12V" }
"""
RATED = """from fenolite.dsl import Design, connect, mm, supply, volt
design = Design("rating")
design.board(mm(20), mm(10))
gnd = design.ground("GND")
v12 = design.rail("V12", ground=gnd)
c1 = design.part("C1", device="Test:CAP_12V", value="10u")
connect(v12, c1.P1)
connect(gnd, c1.P2)
c1.place(mm(10), mm(5))
"""


def test_rating_finding_names_its_part_and_net(tmp_path, monkeypatch):
    """Scenario "A rating finding names its part and net": a capacitor rated 12 V on a 12 V ±10 % rail."""
    from _contracts import cli

    from fenolite.cli._script import run_design_script
    from fenolite.dsl import to_model
    from fenolite.model import canonical

    (tmp_path / "devices").mkdir()
    (tmp_path / "devices" / "cap.toml").write_text(CAPACITOR, encoding="utf-8")
    script = tmp_path / "design.py"
    script.write_text(RATED, encoding="utf-8")
    out = tmp_path / "build"
    code, env = cli(monkeypatch, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, env["issues"]
    # the rated-below design stops a build (c0252's build rule): its model is written over the build
    script.write_text(
        RATED + 'design.rig(supply(v12, gnd, voltage=volt("12").pct(10), name="bench"))\n', encoding="utf-8"
    )
    canonical.dump_dir(to_model(run_design_script(script).design), out / ".fenolite")
    code, env = cli(monkeypatch, "check", str(out), "--stages", "circuit.rules")
    assert code == 5
    index = next(k for k, found in enumerate(env["issues"]) if found["code"] == "circuit.rating-voltage")
    rows = [row for row in env["result"]["subjects"] if row["issue"] == index]
    assert [(s["kind"], s["name"]) for s in rows[0]["items"]] == [("component", "C1"), ("net", "V12")]
    model = canonical.load_dir(out / ".fenolite")
    assert [s["id"] for s in rows[0]["items"]] == [
        next(c.id for c in model.circuit.components if c.ref == "C1"),
        next(n.id for n in model.circuit.nets if n.name == "V12"),
    ]
