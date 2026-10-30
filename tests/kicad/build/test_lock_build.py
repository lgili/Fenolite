# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's ERC on the design-lock example (change c0249; ``H-G-LOCK-REFS``): a project whose refs were
assigned by the lock holds no duplicate and no unannotated reference."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest
from _checkrun import check, stage
from _probes import major

import fenolite.cli.main as cli_main

pytestmark = pytest.mark.needs_kicad
EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "lock"
REF_TYPES = ("duplicate_reference", "unannotated")


def test_lock_example_has_annotated_unique_refs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    folder = tmp_path / "ex"
    folder.mkdir()
    shutil.copy(EXAMPLE / "design.py", folder / "design.py")
    out = tmp_path / "out"
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        args = ["--kicad-version", str(major()), "build", str(folder / "design.py"), "--out", str(out)]
        code = cli_main.main([*args, "--confirm", "--json"])
    assert code == 0, stderr.getvalue()
    assert json.loads(stdout.getvalue())["result"]["lock"]["written"] is True
    assert (folder / "design.lock").read_bytes() == (EXAMPLE / "design.lock").read_bytes()
    code, env, _, err = check(out, "--stages", "erc.kicad")
    erc = stage(env, "erc.kicad")
    print(f"exit {code}, erc {erc['status']}, by type {erc['summary'].get('by_type')}")
    assert erc["summary"]["sheets"] == 3, err
    by_type = erc["summary"].get("by_type", {})
    assert not [kind for kind in REF_TYPES if kind in by_type], by_type
