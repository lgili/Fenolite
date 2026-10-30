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
