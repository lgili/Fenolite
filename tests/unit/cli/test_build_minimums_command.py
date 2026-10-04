# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script rule minimums through ``fenolite build`` (capability design-dsl, "Rule minimums in the DSL";
altium-build, "Rule minimums in an Altium build"; change c0054). Each test builds a copy of the blink whose
script declares minimums into ``tmp_path``, in-process."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
MINIMUMS = (
    "design.rules.minimum(clearance=mm(0.15), track_width=mm(0.25))\n"
    'design.rules.minimum(clearance=mm(0.2), track_width=mm(0.5), netclass="PWR")\n'
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def script(tmp_path: Path, append: str = MINIMUMS) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
    shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
    path = root / "examples" / "blink_2layer" / "design.py"
    path.write_text(path.read_text(encoding="utf-8") + append, encoding="utf-8")
    return path


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def test_build_writes_and_rebuild_replaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, out = script(tmp_path), tmp_path / "B"
    code, _, err = run(monkeypatch, "build", str(path), "--out", str(out), "--confirm")
    assert code == 0, err
    rules = out / "blink.kicad_dru"
    text = rules.read_text(encoding="utf-8")
    assert text.count("(rule ") == 4 and "fenolite_1_min_track_width_pwr" in text
    setup = json.loads((out / "blink.kicad_pro").read_text(encoding="utf-8"))
    assert setup["board"]["design_settings"]["rules"]["min_track_width"] == 0.25
    model = json.loads((out / ".fenolite" / "rules.json").read_text(encoding="utf-8"))
    assert len(model["rules"]) == 4

    rules.write_text(text + "(rule mine\n\t(constraint track_width (max 5mm))\n)\n", encoding="utf-8")
    path.write_text(path.read_text(encoding="utf-8").replace("mm(0.25)", "mm(0.3)"), encoding="utf-8")
    code, _, err = run(monkeypatch, "build", str(path), "--out", str(out), "--confirm")
    assert code == 0, err
    text = rules.read_text(encoding="utf-8")
    assert text.count("fenolite_0_min_track_width") == 1 and "0.25mm" not in text
    assert text.index("fenolite_1_min_track_width_pwr") < text.index("mine")
    setup = json.loads((out / "blink.kicad_pro").read_text(encoding="utf-8"))
    assert setup["board"]["design_settings"]["rules"]["min_track_width"] == 0.3


def test_a_refused_minimum_is_a_script_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = script(tmp_path, "design.rules.minimum(clearance=0.2)\n")
    code, _, err = run(monkeypatch, "build", str(path), "--out", str(tmp_path / "B"), "--dry-run")
    assert code == 3 and "minimum(): clearance" in err


def test_altium_target_reports_the_minimums(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, out = script(tmp_path), tmp_path / "A"
    code, env, err = run(
        monkeypatch,
        "build",
        str(path),
        "--out",
        str(out),
        "--target",
        "altium",
        "--confirm",
    )
    assert code == 0, err
    found = [i for i in env["issues"] if i.get("where") == "design-rules"]  # type: ignore[union-attr]
    assert [i["code"] for i in found] == ["altium.not-lowered"]
    assert "min_clearance" in found[0]["message"] and "min_track_width_PWR" in found[0]["message"]
