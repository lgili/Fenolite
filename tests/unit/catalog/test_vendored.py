# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0266 vendored records: identity pairing, local files, conflicts and authored precedence."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from fenolite.catalog.records import load_tree
from fenolite.catalog.vendored import load_vendored, overlay
from fenolite.core.errors import FormatError

FIXTURE = Path(__file__).resolve().parents[2] / "data/library/project"


def test_vendored_reads_only_data(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    (tmp_path / "fenolite_library/devices/evil.py").write_text("raise RuntimeError('executed')")
    found = load_vendored(tmp_path)
    assert len(found.tree.records) == 3 and not found.issues
    assert found.items[("device", "Demo266:Demo900")].catalog == "library:device/Demo266:Demo900@1.0.0"
    assert not any(path.name.endswith(".py") for path in found.files)
    assert found.tree.devices()[0].symbol == "Demo266:TwoPin"


@pytest.mark.parametrize(
    "key,value", [("id", "Other:Wrong"), ("version", "2.0.0"), ("spdx", "MIT"), ("id", "Fenolite:X")]
)
def test_vendored_item_matches_record(tmp_path: Path, key: str, value: str) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    marker = next((tmp_path / "fenolite_library/devices").rglob("item.json"))
    data = json.loads(marker.read_text())
    data[key] = value
    marker.write_text(json.dumps(data))
    with pytest.raises(FormatError):
        load_vendored(tmp_path)


def test_vendored_conflict_names_both_folders(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    folder = tmp_path / "fenolite_library/devices/Demo266/Demo900"
    shutil.copytree(folder, folder.with_name("Copy"))
    found = load_vendored(tmp_path)
    assert [i.code for i in found.issues] == ["library.item-conflict"]
    assert "Demo900" in found.issues[0].message and "Copy" in found.issues[0].message


def test_vendored_authored_overlay(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    authored = tmp_path / "devices"
    authored.mkdir()
    shutil.copy(tmp_path / "fenolite_library/devices/Demo266/Demo900/record.toml", authored / "own.toml")
    tree, issues = overlay(load_tree(authored, label="devices/"), load_vendored(tmp_path))
    assert tree.files[("device", "Demo266:Demo900")] == "devices/own.toml"
    assert [i.code for i in issues] == ["library.overrides-item"]


def test_vendored_symlink_escape_refused(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    marker = next((tmp_path / "fenolite_library/devices").rglob("record.toml"))
    marker.unlink()
    marker.symlink_to(FIXTURE / "fenolite_library/devices/Demo266/Demo900/record.toml")
    with pytest.raises(FormatError, match="symlink"):
        load_vendored(tmp_path)


def test_vendored_family_is_one_device_item(tmp_path: Path) -> None:
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
    found = load_vendored(tmp_path)
    assert not found.tree.records and len(found.families) == 1
    assert found.families[0][1].catalog == "library:device/Example:EX_CHIP_R@1.0.0"
