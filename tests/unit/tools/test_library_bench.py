# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``tools/library_bench.py``, the optional scheduled ``library-bench`` job (change c0279, task 4.4)."""

from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from email.message import Message
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parents[3] / "tools" / "library_bench.py"


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("library_bench", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _board(root: Path, ident: str, files: int) -> Path:
    folder = root / "boards" / "cc0" / "demo" / ident.split(":")[1]
    folder.mkdir(parents=True)
    (folder / "item.json").write_text(json.dumps({"id": ident, "kind": "board"}), encoding="utf-8")
    for index in range(files):
        (folder / f"f{index}.txt").write_text("x", encoding="utf-8")
    return folder


def test_the_smallest_boards_are_chosen(tmp_path: Path) -> None:
    tool = _tool()
    _board(tmp_path, "demo:large", 9)
    small = _board(tmp_path, "demo:small", 1)
    middle = _board(tmp_path, "demo:middle", 4)
    found = tool.boards(tmp_path)
    assert [row[0] for row in found] == ["demo:large", "demo:middle", "demo:small"]
    assert tool.select(found, count=2) == [("demo:middle", middle), ("demo:small", small)]
    assert tool.select(found, count=2, only=["demo:large"]) == [("demo:large", found[0][1])]
    with pytest.raises(SystemExit, match="demo:absent"):
        tool.select(found, count=2, only=["demo:absent"])


def test_newest_release_and_none_yet() -> None:
    tool = _tool()

    def found(url: str) -> bytes:
        assert url.endswith("/releases/latest")
        return json.dumps({"tag_name": "v1.0.0"}).encode()

    assert tool.newest_release(found) == "v1.0.0"

    def missing(url: str) -> bytes:
        raise urllib.error.HTTPError(url, 404, "Not Found", Message(), io.BytesIO(b""))

    assert tool.newest_release(missing) is None


def test_no_release_records_that_nothing_ran(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool()

    def none(fetch: object = None) -> None:
        return None

    monkeypatch.setattr(tool, "newest_release", none)
    assert tool.main(["--out", str(tmp_path / "out")]) == 0
    reply = json.loads((tmp_path / "out" / "not-run.json").read_text(encoding="utf-8"))
    assert reply["status"] == "not-run" and "no release" in reply["reason"]
    assert not (tmp_path / "out" / "bench.json").exists()


def test_a_failed_command_fails_the_row() -> None:
    tool = _tool()
    fidelity: dict[str, object] = {"proof": {"levels": {}}}
    runs: list[dict[str, object]] = [
        {
            "id": "demo:a",
            "levels": [],
            "differences": [],
            "fidelity": fidelity,
            "seconds": 1,
            "failure": "boom",
        },
        {
            "id": "demo:b",
            "levels": [],
            "differences": [],
            "fidelity": fidelity,
            "seconds": 1,
            "replay_exit": 0,
            "proof_exit": 5,
        },
    ]
    rows = {row["id"]: row for row in tool.table(runs)}
    assert rows["demo:a"]["result"] == "fail" and rows["demo:a"]["failure"] == "boom"
    assert rows["demo:b"]["result"] == "fail" and rows["demo:b"]["proof_exit"] == 5
