# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored library-block releases and projects shared by c0273 tests; no network."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _buildhelp import blink_variant
from _checkcli import run
from _libdemo import write_release

ROOT = Path(__file__).resolve().parents[3]
REPOSITORY = ROOT / "tests/data/library_repo/block_items"
ITEM_PATH = Path("blocks/cc0/Demo/led")
VENDORED = Path("fenolite_library/blocks/Demo/led")
SCRIPT = """from fenolite.dsl import Design, Net, connect, mm
from fenolite_library.blocks.Demo.led import led

design = Design("library_blocks")
design.board(mm(40), mm(20))
positive, negative = Net("POS"), Net("NEG")
instance = design.use(led, "led1")
connect(positive, instance.POS)
connect(negative, instance.NEG)
instance.part("R").place(mm(10), mm(10))
"""


def project(folder: Path) -> Path:
    blink_variant(folder)  # the authored Mini library tables
    (folder / "design.py").write_text(SCRIPT, encoding="utf-8")
    return folder


def release(folder: Path, *, version: str = "1.0.0", resistance: str = "1k") -> Path:
    root = folder / "repository"
    shutil.copytree(REPOSITORY, root)
    item = root / ITEM_PATH
    source = item / "__init__.py"
    source.write_text(
        source.read_text()
        .replace('version="1.0.0"', f'version="{version}"')
        .replace('param("1k"', f'param("{resistance}"')
    )
    for name in ("item.json", "PROVENANCE.json"):
        data = json.loads((item / name).read_text())
        data["version"] = version
        (item / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    from fenolite.cli._blocks_index import exported_block, item_module
    from fenolite.dsl.blockitem import from_record
    from fenolite.dsl.record import describe

    with item_module(item) as module:
        record = from_record(describe(exported_block(module)))
    (item / "block.json").write_text(record.text())
    destination = folder / "release"
    write_release(root, destination, version)
    return destination


def get(monkeypatch: pytest.MonkeyPatch, work: Path, source: Path) -> dict:
    code, result, error, _ = run(
        monkeypatch, work, "get", "block", "Demo:led", "--from", str(source), "--confirm"
    )
    assert code == 0, (result, error)
    return result
