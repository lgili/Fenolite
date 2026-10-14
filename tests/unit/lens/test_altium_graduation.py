# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The build notice names only written experimental kinds; its evidence follows the cells (c0092)."""

from __future__ import annotations

from dataclasses import replace

from _altium import hier_model, sample_model

from fenolite.backends import base
from fenolite.backends.altium import claims
from fenolite.core.evidence import Evidence, Level
from fenolite.lens.altium import build_altium


def test_all_written_kinds_graduated_has_no_notice(monkeypatch) -> None:
    rows = tuple(
        replace(row, experimental=(), write=Evidence(Level.CORPUS_VERIFIED)) for row in claims.MATRIX
    )
    monkeypatch.setattr(claims, "MATRIX", rows)
    monkeypatch.setattr(base, "graduation_rows", lambda rows: tuple(rows))
    output = build_altium(sample_model(), name="graduation")
    assert output.files
    assert not [issue for issue in output.issues if issue.code == "altium.experimental"]
    assert output.summary["experimental"] is False
    assert output.evidence.level is Level.CORPUS_VERIFIED


def test_only_written_experimental_kind_is_named(monkeypatch) -> None:
    rows = tuple(
        replace(row, experimental=("write",) if row.kind == "altium_harness" else ()) for row in claims.MATRIX
    )
    monkeypatch.setattr(claims, "MATRIX", rows)
    monkeypatch.setattr(base, "graduation_rows", lambda rows: tuple(rows))
    output = build_altium(hier_model(), name="graduation", sheets="modules")
    assert any(name.endswith(".Harness") for name in output.files)
    notices = [issue for issue in output.issues if issue.code == "altium.experimental"]
    assert len(notices) == 1
    assert notices[0].message == "Experimental write kinds: altium_harness"
