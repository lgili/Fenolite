# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Synthetic readback never promotes composition to native GUI acceptance."""

from pathlib import Path

from _altium import sample_model

from fenolite.core.evidence import Level
from fenolite.lens.altium import build_altium
from fenolite.schematic.intent import CompositionIntent


def test_evidence_and_native_status_remain_honest():
    output = build_altium(sample_model(), name="sample", composition=CompositionIntent())
    assert output.files and output.evidence.level is Level.INFERRED
    root = Path(__file__).resolve().parents[4]
    evidence = (root / "docs" / "evidence" / "schematic-composition.md").read_text(encoding="utf-8")
    assert "Unmeasured: native Altium GUI acceptance" in evidence
    assert "No author report is claimed" in evidence
