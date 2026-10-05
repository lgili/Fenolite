# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The content-selected MS-CFB stream view of ``fenolite inspect``."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from _cfb_build import build, set_field
from _cfb_read import read_compound as independent_read
from _checkcli import run

DATA = Path(__file__).resolve().parents[2] / "data"
SAMPLE = DATA / "altium" / "sample" / "binary" / "altium_sample.SchDoc"
PCB_LIBRARY = DATA / "altium" / "blink" / "blink.PcbLib"
BOARD = DATA / "kicad" / "board" / "two_layer.kicad_pcb"


def test_binary_sample_stream_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(SAMPLE), "--streams")
    result = env["result"]
    independent = independent_read(SAMPLE.read_bytes())
    assert code == 0
    assert result["kind"] == "compound_file" and result["major"] == 3
    assert result["counts"]["streams"] == 2 and result["counts"]["storages"] == 0
    assert [entry["path"] for entry in result["entries"]] == ["Storage", "FileHeader"]
    assert [entry["sha256"] for entry in result["entries"]] == [
        hashlib.sha256(independent[path]).hexdigest() for path in ("Storage", "FileHeader")
    ]
    assert env["issues"] == []
    assert env["input"]["sha256"] == hashlib.sha256(SAMPLE.read_bytes()).hexdigest()


def test_library_storage_precedes_children(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(PCB_LIBRARY), "--streams")
    entries = env["result"]["entries"]
    paths = [entry["path"] for entry in entries]
    parent = next(entry for entry in entries if entry["path"] == "Library")
    child_positions = [i for i, path in enumerate(paths) if path.startswith("Library/")]
    assert code == 0 and entries.index(parent) < min(child_positions)
    assert parent["type"] == "storage" and parent["children"] == sum(
        path.count("/") == 1 and path.startswith("Library/") for path in paths
    )


def test_compound_hint_and_two_view_usage_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(PCB_LIBRARY))
    assert code == 2 and err["code"] == "FEN-2001" and "--streams" in err["hint"]
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(PCB_LIBRARY), "--summary", "--streams")
    assert code == 2 and err["code"] == "FEN-2001"


def test_broken_compound_is_located_and_limit_is_enforced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    built = build([{"path": "FileHeader", "data": b"x" * 5000}])
    broken = bytearray(built.data)
    start = int.from_bytes(
        broken[built.offsets["entry:FileHeader"] + 116 : built.offsets["entry:FileHeader"] + 120],
        "little",
    )
    set_field(broken, built.offsets["fat"] + start * 4, start)
    path = tmp_path / "broken.PcbDoc"
    path.write_bytes(broken)
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(path), "--streams")
    assert code == 3 and err["code"] == "FEN-3004"
    assert err["message"].startswith("cfb.chain")
    assert "stream:FileHeader" in err["where"] and "@" in err["where"]

    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(SAMPLE), "--streams", "--limit-bytes", "1000")
    assert code == 3 and err["code"] == "FEN-3004"
    assert err["message"].startswith("cfb.limit") and "max_file_bytes" in err["message"]


def test_content_not_extension_selects_stream_view_and_fields_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    copied = tmp_path / "renamed.bin"
    shutil.copyfile(SAMPLE, copied)
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(copied), "--streams", "--fields", "counts")
    assert code == 0 and set(env["result"]) == {"counts"}
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(BOARD), "--streams")
    assert code == 3 and err["code"] == "FEN-3004" and err["message"].startswith("cfb.signature")


def test_limit_option_needs_stream_view(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(BOARD), "--limit-bytes", "1")
    assert code == 2 and err["code"] == "FEN-2001"


@pytest.mark.parametrize("value", ["0", "-1", "nope"])
def test_limit_must_be_positive_integer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(SAMPLE), "--streams", "--limit-bytes", value)
    assert code == 2
