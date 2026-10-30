# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tool-free findings preserve evidence and refuse oracle stages before running them."""

from pathlib import Path

import pytest

from fenolite.testing import TestingError, load


def test_findings_filters_and_unattached(script: Path):
    script.write_text(script.read_text() + '\nlost = Part("R3", "Fenolite:Resistor")\n')
    with load(script) as d:
        findings = d.findings("build.*", severity="warning")
        assert isinstance(findings, tuple)
        assert len(findings) == 1 and findings[0].code == "build.unattached"
        assert findings.evidence == d.findings("build.*").evidence
        assert not d.findings("build.*", severity="error")
        assert d.findings(stages=("model.validate",)).evidence.level.value == "INFERRED"


def test_oracle_refused_before_any_call(script: Path, monkeypatch):
    with load(script) as d:

        def refuse(*a, **kw):
            raise AssertionError("a command ran")

        monkeypatch.setattr("fenolite.api.run", refuse)
        with pytest.raises(TestingError, match="drc.kicad.*fenolite check"):
            d.findings(stages=("model.validate", "drc.kicad"))
        with pytest.raises(TestingError, match="unknown"):
            d.findings(stages=("no.such-stage",))


CAPACITOR = """schema = "fenolite.device.v0"
id = "Test:CAP_10V"
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
voltage = { abs_max = "10V" }
"""
RAIL = """from fenolite.dsl import Design, connect, mm, supply, volt
design = Design("rating")
design.board(mm(20), mm(10))
design.contracts(unknown="warning")
gnd = design.ground("GND")
v12 = design.rail("V12", ground=gnd)
c1 = design.part("C1", device="Test:CAP_10V", value="10u")
connect(v12, c1.P1)
connect(gnd, c1.P2)
c1.place(mm(10), mm(5))
"""


def test_circuit_findings_in_a_test(script: Path):
    """Scenario "Circuit findings in a test": a 10 µF capacitor rated 10 V on the rail V12."""
    (script.parent / "devices").mkdir()
    (script.parent / "devices" / "cap.toml").write_text(CAPACITOR, encoding="utf-8")
    # the rail's voltage unstated: under contracts(unknown='warning') the rating row is one warning
    script.write_text(RAIL, encoding="utf-8")
    with load(script) as d:
        (finding,) = d.findings("circuit.*", severity="warning")
        assert finding.code == "circuit.value-unknown" and "rating-voltage:C1" in finding.message
        assert [(s.kind, s.name) for s in finding.subjects] == [("component", "C1"), ("net", "V12")]
        assert finding.subjects[0].id == d.ref("C1").id and finding.subjects[1].id == d.net("V12").id
    # stated at 12 V the rating fails, and a rating error stops the build (c0252): load names it
    script.write_text(
        RAIL + 'design.rig(supply(v12, gnd, voltage=volt("12"), name="bench"))\n', encoding="utf-8"
    )
    with pytest.raises(TestingError, match=r"circuit\.rating-voltage at C1"):
        load(script)
