# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library items: ids, ``item.json`` and the tree digest (capability fenolite-library, "Library item
manifest"; change c0279)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from fenolite.backends.kicad.libcache import tree_hash
from fenolite.library.items import (
    ItemError,
    canonical_json,
    folder_files,
    id_path,
    id_problem,
    item_folder,
    read_item,
    tree_digest,
)

DEMO = Path(__file__).resolve().parents[2] / "data" / "library_repo" / "demo"
DEVICE = DEMO / "devices" / "cc0" / "Demo" / "EXB"


def test_ids_of_each_kind() -> None:
    assert id_problem("device", "Demo:EXB") is None
    assert id_problem("board", "kicad-demos/cm5_minima") is None
    assert id_problem("board", "KiCad/Board") is not None
    assert id_problem("device", "Demo") is not None
    assert id_problem("device", "Demo:..") is not None
    assert id_problem("widget", "a:b") is not None
    assert id_path("Demo:EXB") == "Demo/EXB"
    assert item_folder("device", "Demo:EXB") == "fenolite_library/devices/Demo/EXB"


def test_demo_manifest_reads_and_round_trips() -> None:
    data = (DEVICE / "item.json").read_bytes()
    item = read_item(data)
    assert item.kind == "device" and item.version == "1.2.0" and not item.executes
    assert [d.key for d in item.depends] == ["symbol/Demo:EXB", "footprint/Demo:SOT"]
    assert canonical_json(item.as_json()) == data


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"version": "1.2"}, "version"),
        ({"files": ["b", "a"]}, "files"),
        ({"files": ["../x"]}, "files"),
        ({"files": ["LICENSE"]}, "files"),
        ({"executes": "no"}, "executes"),
        ({"extra": 1}, "extra"),
        ({"depends": [{"kind": "symbol", "id": "Demo:EXB"}]}, "depends[0]"),
    ],
)
def test_manifest_rules(change: dict[str, object], field: str) -> None:
    table = json.loads((DEVICE / "item.json").read_text(encoding="utf-8"))
    table.update(change)
    with pytest.raises(ItemError, match=re.escape(field)):
        read_item(json.dumps(table).encode())


def test_tree_digest_is_the_libcache_scheme(tmp_path: Path) -> None:
    files = folder_files(DEVICE)
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    digest, count = tree_hash(tmp_path)
    assert tree_digest(files) == f"fenolite-tree-1:{digest}" and count == len(files)
    rows = [(path, len(data), hashlib.sha256(data).hexdigest()) for path, data in files.items()]
    assert tree_digest(rows) == tree_digest(files)
