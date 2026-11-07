# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0324 strict technical tables from runtime variants of Fenolite-authored CC0 inputs only."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _fidelity import ALL_LEVELS, roundtrip, snapshot
from _importcode import BOARD, build, imported

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse

ROOT = Path(__file__).resolve().parents[3]


def shorter(source: Path, *, extra: str = "") -> None:
    tree = parse(source.read_text(encoding="utf-8"))
    layers = tree.find("layers")
    assert layers is not None
    kept = [
        c
        for c in layers.children
        if not isinstance(c, Node) or c.atoms()[0].value not in {"Eco1.User", "Eco2.User"}
    ]
    assert len(layers.children) - len(kept) == 2
    if extra:
        kept.append(parse(extra))
    short = layers.with_children(kept)
    source.write_text(
        dumps(tree.with_children(short if c == layers else c for c in tree.children)), encoding="utf-8"
    )


def authored(tmp: Path, *, extra: str = "") -> Path:
    source = tmp / "source/short.kicad_pcb"
    source.parent.mkdir(parents=True)
    shutil.copyfile(BOARD, source)
    shorter(source, extra=extra)
    return source


@pytest.mark.parametrize("target", [9, 10])
def test_strict_import_copy_and_explicit_build_preserve_exact_table(tmp_path: Path, target: int) -> None:
    source = authored(tmp_path)
    before = source.read_bytes()
    first = imported(tmp_path, source, "--confirm", out="first")
    assert first.exit_code == 0, first.error
    assert first.result["unexpressed"] == []
    code = (tmp_path / "first/design.py").read_text(encoding="utf-8")
    assert "technical_layers=" in code and '"Eco1.User"' not in code and '"Eco2.User"' not in code
    second = imported(tmp_path, source, "--confirm", out="second")
    assert second.exit_code == 0, second.error
    assert snapshot(tmp_path / "first") == snapshot(tmp_path / "second")
    built = build(tmp_path / "first", "--kicad-version", str(target))
    assert built.exit_code == 0, built.error
    original = read_board(source).board
    native = read_board(tmp_path / "first/built/short.kicad_pcb").board
    assert original is not None and native is not None
    assert [(row.name, row.kind) for row in native.layers] == [
        (row.name, row.kind) for row in original.layers
    ]
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "extra,example",
    [
        ('(127 "Unknown.User" user)', "the DSL board lacks Unknown.User"),
        ('(41 "User.2" user)', "the source lacks User.1"),
    ],
)
def test_unknown_and_missing_user_rows_still_refuse(tmp_path: Path, extra: str, example: str) -> None:
    source = authored(tmp_path, extra=extra)
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 7 and reply.error is not None
    assert reply.error["code"] == "FEN-7001"
    findings = [row for row in (reply.envelope or {})["issues"] if row["code"] == "import.item-unexpressed"]
    assert len(findings) == 1
    assert findings[0]["where"] == "layer-table" and findings[0]["severity"] == "warning"
    assert findings[0]["message"].startswith("1 item(s) of kind layer-table")
    assert f"(for example {example})" in findings[0]["message"]
    assert not (tmp_path / "out").exists()


def test_authored_short_table_project_is_equal_at_all_nine_levels(tmp_path: Path) -> None:
    source = tmp_path / "original"
    shutil.copytree(ROOT / "tests/data/fidelity/sensor", source)
    shorter(next(source.glob("*.kicad_pcb")))
    reply = roundtrip(source, tmp_path / "roundtrip")
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["differences"] == [] and reply.result["accepted"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"])


def test_missing_required_edge_row_still_refuses(tmp_path: Path) -> None:
    source = authored(tmp_path)
    tree = parse(source.read_text(encoding="utf-8"))
    layers = tree.find("layers")
    assert layers is not None
    missing = layers.with_children(
        c for c in layers.children if not isinstance(c, Node) or c.atoms()[0].value != "Edge.Cuts"
    )
    source.write_text(
        dumps(tree.with_children(missing if c == layers else c for c in tree.children)), encoding="utf-8"
    )
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 7 and reply.error is not None
    assert reply.error["code"] == "FEN-7001"
    assert any(
        finding["code"] == "import.item-unexpressed"
        and finding["where"] == "layer-table"
        and "Edge.Cuts" in finding["message"]
        for finding in (reply.envelope or {})["issues"]
    )
    assert not (tmp_path / "out").exists()
