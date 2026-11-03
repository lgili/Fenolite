# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit unused-pin markers cannot change any native pin or connected bus drawing."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _altium_clean_drawn import source

from fenolite.api import run
from fenolite.backends.altium.read import sch


@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_only_explicit_unused_inputs_receive_native_markers(tmp_path: Path, monkeypatch, form: str):
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    variants = []
    for marked in (False, True):
        folder = tmp_path / str(marked)
        script = source(folder / "source", marked=marked)
        reply = run(
            "build", str(script), "--out", str(folder / "out"), "--target", "altium",
            "--altium-format", form, "--confirm", cwd=tmp_path,
            seed=1, timestamp="2026-11-03T00:00:00Z",
        )  # fmt: skip
        assert reply.exit_code == 0, (reply.error, reply.envelope)
        documents = [sch.read_schematic(p.read_bytes()) for p in (folder / "out").glob("*.SchDoc")]
        markers = [m for d in documents for m in d.no_ercs()]
        assert len(markers) == (2 if marked else 0)
        assert all(m.active and m.suppress_all for m in markers)
        pins = [p for d in documents for p in d.of_type(sch.Pin)]
        assert len(pins) == 40
        if marked:
            assert Counter(m.location for m in markers) == Counter(
                p.hot_end for p in pins if p.designator in {"11", "12"}
            )
        variants.append(Counter((p.designator, p.location) for p in pins))
    assert variants[0] == variants[1]
