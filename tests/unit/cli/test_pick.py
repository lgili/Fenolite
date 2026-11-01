# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0266 exact library item versions in picks, with explicit unverified-row consent."""

from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path

import pytest
from _checkcli import run

FIXTURE = Path(__file__).resolve().parents[3] / "tests/data/library/project"


def test_library_pick_pins_catalog_and_rechecks_item_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    (tmp_path / "design.py").write_text("""from fenolite.dsl import Design, mm, ohm, resistor
design = Design("picked_library")
design.board(mm(20), mm(12))
r = design.part("R1", device=resistor(ohm(900), row="Demo266:Demo900"))
r.place(mm(10), mm(6))
r.unused_no_connect()
""")
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--confirm")
    assert code == 0, (error, env.get("issues"))
    assert env["result"]["picks"][0]["catalog"] == "library:device/Demo266:Demo900@1.0.0"
    assert (
        tomllib.loads((tmp_path / "design.lock").read_text())["picks"]["R1"]["catalog"]
        == "library:device/Demo266:Demo900@1.0.0"
    )
    folder = tmp_path / "fenolite_library/devices/Demo266/Demo900"
    record = folder / "record.toml"
    record.write_text(record.read_text().replace('version = "1.0.0"', 'version = "1.0.1"'))
    marker = folder / "item.json"
    data = json.loads(marker.read_text())
    data["version"] = "1.0.1"
    marker.write_text(json.dumps(data))
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--dry-run")
    assert code == 0, (error, env.get("issues"))
    assert env["result"]["picks"][0]["state"] == "row-changed"
    assert env["result"]["picks"][0]["catalog"] == "library:device/Demo266:Demo900@1.0.1"


def test_library_family_is_one_pick_item(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    folder = tmp_path / "fenolite_library/devices/Example/EX_CHIP_R"
    folder.mkdir(parents=True)
    text = (root / "examples/families/devices/example_chip_r.toml").read_text()
    text = text.replace(
        'sources = ["EXR series datasheet rev A, ordering code table (illustrative)"]', 'sources = ["D-0001"]'
    )
    (folder / "family.toml").write_text(text)
    (folder / "item.json").write_text(
        json.dumps({"id": "Example:EX_CHIP_R", "kind": "device", "version": "1.0.0", "spdx": "CC0-1.0"})
    )
    (tmp_path / "design.py").write_text("""from fenolite.dsl import Design, mm, ohm, resistor
design = Design("family_library")
design.board(mm(20), mm(12))
r = design.part("R1", device=resistor(ohm(1000), row="Example:EX_CHIP_R", case="0603"))
r.place(mm(10), mm(6))
r.unused_no_connect()
""")
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--dry-run")
    assert code == 0, (error, env.get("issues"))
    assert env["result"]["picks"][0]["catalog"] == "library:device/Example:EX_CHIP_R@1.0.0"
    assert env["result"]["devices"][0]["item"]["id"] == "Example:EX_CHIP_R"
    assert "H-G-DEVICE-PACKS" in env["evidence"]["hypotheses"]
