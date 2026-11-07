# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build isolation, determinism, failure diagnostics and ownership."""

import gc
from pathlib import Path

import pytest

from fenolite.testing import TestingError, load


def test_temporary_and_same_inputs(script: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "outside-state"))
    cwd = Path.cwd()
    with load(script) as a, load(script) as b:
        assert a.model == b.model
        assert {c.ref for c in a.model.circuit.components} == {"R1", "R2"}
        assert a.path.parent != b.path.parent
    assert Path.cwd() == cwd and not (tmp_path / "outside-state").exists()


def test_lifecycle_and_workdir(script: Path, tmp_path: Path):
    with load(script) as d:
        own = d.path
    assert not own.exists()
    d.close()
    with load(script, workdir=tmp_path / "kept") as d:
        kept = d.path
    assert (kept / ".fenolite").is_dir()
    d = load(script)
    final = d.path
    del d
    gc.collect()
    assert not final.exists()


def test_failing_script(script: Path):
    script.write_text("\n" * 6 + "raise ValueError('failed')\n")
    with pytest.raises(TestingError, match="FEN-3004.*line:7"):
        load(script)
