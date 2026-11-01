# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored block-item records and explicit reviewed indexing (c0273)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.core.errors import FormatError
from fenolite.dsl.blockitem import from_record, read_item
from fenolite.dsl.record import describe, page, record_data

ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT / "tests/data/library_repo/block_items"
ITEM = REPO / "blocks/cc0/Demo/led"


@pytest.fixture
def item(tmp_path: Path) -> Path:
    destination = tmp_path / "led"
    shutil.copytree(ITEM, destination)
    return destination


def test_record_file_of_a_test_item(monkeypatch: pytest.MonkeyPatch, item: Path) -> None:
    (item / "block.json").unlink()
    code, result, error, _ = run(
        monkeypatch, item.parent, "blocks", "index", "led", "--out", "out/block.json", "--dry-run"
    )
    assert code == 0, error
    assert result["result"]["record"]["schema"] == "fenolite.block-item.v0"
    assert result["result"]["record"]["namespace"] == "Demo"
    assert result["result"]["plan"][0]["kind"] == "block-index"
    assert not (item.parent / "out/block.json").exists()
    plan = result["result"]["plan_id"]
    code, result, error, _ = run(
        monkeypatch,
        item.parent,
        "blocks",
        "index",
        "led",
        "--out",
        "out/block.json",
        "--confirm",
        "--plan",
        plan,
    )
    assert code == 0, error
    assert [p["path"] for p in result["receipt"]["written"]] == ["out/block.json"]
    stored = read_item((item.parent / "out/block.json").read_text())
    assert (stored.id, stored.version) == ("Demo:led", "1.0.0")
    code, result, error, _ = run(
        monkeypatch, item.parent, "blocks", "index", "led", "--out", "out/block.json", "--dry-run"
    )
    assert code == 0, error
    assert result["result"]["current"] is True and result["receipt"] is None
    assert not list(item.rglob("__pycache__"))


def test_index_check_stale_and_same_process_code_edit(monkeypatch: pytest.MonkeyPatch, item: Path) -> None:
    code, _, error, _ = run(monkeypatch, item.parent, "blocks", "index", "led", "--check")
    assert code == 0, error
    source = item / "__init__.py"
    source.write_text(source.read_text().replace('param("1k"', 'param("2k"'))
    before = (item / "block.json").read_bytes()
    code, result, error, _ = run(monkeypatch, item.parent, "blocks", "index", "led", "--check")
    assert code == 5, error
    assert [i["code"] for i in result["issues"]] == ["blocks.index-stale"]
    assert (item / "block.json").read_bytes() == before


def test_plan_binds_package_sources(monkeypatch: pytest.MonkeyPatch, item: Path) -> None:
    (item / "block.json").unlink()
    code, result, error, _ = run(monkeypatch, item.parent, "blocks", "index", "led", "--dry-run")
    assert code == 0, error
    source = item / "__init__.py"
    source.write_text(source.read_text() + "\n# changed after review\n")
    code, _, error, _ = run(
        monkeypatch, item.parent, "blocks", "index", "led", "--confirm", "--plan", result["result"]["plan_id"]
    )
    assert code == 4 and error["code"] == "FEN-4002"
    assert not (item / "block.json").exists()


@pytest.mark.parametrize("exports", ["[]", "['led', 'another']"])
def test_exactly_one_export(monkeypatch: pytest.MonkeyPatch, item: Path, exports: str) -> None:
    source = item / "__init__.py"
    source.write_text(source.read_text() + f"\nanother = led\n__all__ = {exports}\n")
    code, _, error, _ = run(monkeypatch, item.parent, "blocks", "index", "led", "--dry-run")
    assert code == 3 and error["code"] == "FEN-3004"
    assert "exactly one" in error["message"]


@pytest.mark.parametrize("field,value", [("id", "Demo:other"), ("version", "1.1.0"), ("executes", False)])
def test_manifest_identity_and_execution(
    monkeypatch: pytest.MonkeyPatch, item: Path, field: str, value: object
) -> None:
    manifest = json.loads((item / "item.json").read_text())
    manifest[field] = value
    (item / "item.json").write_text(json.dumps(manifest))
    code, _, error, _ = run(monkeypatch, item.parent, "blocks", "index", "led", "--dry-run")
    assert code == 3 and error["code"] == "FEN-3004"


def test_static_record_preserves_quantity_range_and_length_text() -> None:
    from fenolite.cli.blocksrc import import_file

    definition = import_file(ROOT / "tests/data/blocks/divider.py").divider
    original = describe(definition)
    stored = read_item(from_record(original).text())
    assert record_data(stored.record) == record_data(original)
    assert page(stored.record) == page(original)
    assert from_record(stored.record).text() == from_record(original).text()


@pytest.mark.parametrize("field", ["id", "namespace", "version"])
def test_outer_record_identity_is_checked(field: str) -> None:
    table = json.loads((ITEM / "block.json").read_text())
    table[field] = "Other" if field == "namespace" else "Other:led" if field == "id" else "1.2.0"
    with pytest.raises(FormatError, match="must equal its record"):
        read_item(json.dumps(table))


def test_digest_is_checked_without_import() -> None:
    table = json.loads((ITEM / "block.json").read_text())
    table["record"]["summary"] = "edited metadata"
    with pytest.raises(FormatError, match="digests"):
        read_item(json.dumps(table))
