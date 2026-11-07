# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Changed references keep the layout (capability layout-lens, "Changed references keep the layout";
change c0249): a ref changed through the design lock moves no footprint, because footprints are matched by
uuid and by the ``fenolite.path`` property, never by reference."""

from __future__ import annotations

import io
import json
import re
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "lock"


def build(monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, *flags: str) -> dict[str, object]:
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main(["build", str(script), "--out", str(out), "--kicad-version", "10", "--json", *flags])
    assert code == 0
    return json.loads(stdout.getvalue())


def footprint_at(text: str, path: str) -> tuple[str, str]:
    """The ``(at …)`` of the footprint carrying ``fenolite.path`` = ``path``, and its reference."""
    for block in re.split(r"\n\t\(footprint ", text)[1:]:
        if f'(property "fenolite.path" "{path}"' in block:
            at = re.search(r"\n\t\t\(at ([^)]*)\)", block)
            ref = re.search(r'\(property "Reference" "([^"]*)"', block)
            assert at is not None and ref is not None
            return at.group(1), ref.group(1)
    raise AssertionError(f"no footprint of {path}")


def test_lock_edit_renumbers_without_moving(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    folder = tmp_path / "ex"
    folder.mkdir()
    shutil.copy(EXAMPLE / "design.py", folder / "design.py")
    shutil.copy(EXAMPLE / "design.lock", folder / "design.lock")
    out = tmp_path / "B"
    build(monkeypatch, folder / "design.py", out, "--confirm")
    board = out / "lock_demo.kicad_pcb"
    text = board.read_text(encoding="utf-8")
    at, ref = footprint_at(text, "reg/U")
    assert ref == "U1"
    x, y, *rest = at.split()
    moved = " ".join([f"{float(x) + 3:g}", y, *rest])
    board.write_text(text.replace(f"\n\t\t(at {at})", f"\n\t\t(at {moved})", 1), encoding="utf-8")
    assert footprint_at(board.read_text(encoding="utf-8"), "reg/U")[0] == moved
    lock = folder / "design.lock"
    lock.write_text(lock.read_text(encoding="utf-8").replace('"reg/U" = "U1"', '"reg/U" = "U9"'), "utf-8")
    env = build(monkeypatch, folder / "design.py", out, "--confirm")
    assert "reg/U" in env["result"]["preserved"]["kept"]  # type: ignore[index]
    assert not [i for i in env["issues"] if i["code"] == "layout.unplaced" and i["where"] in ("U1", "U9")]  # type: ignore[union-attr]
    after, ref = footprint_at(board.read_text(encoding="utf-8"), "reg/U")
    assert after == moved and ref == "U9"
