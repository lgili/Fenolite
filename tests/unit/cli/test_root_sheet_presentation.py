# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 scene controls: root role, collision refusal and retained losses (c0330)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.cli._presentation import presentation_level
from fenolite.cli.cmd_verify_source import Original, _paired_sheet_scenes
from fenolite.core.errors import FormatError


def project(folder: Path, name: str, *, root_text: str = "Authored probe", child: str = "aaa") -> Original:
    folder.mkdir()
    board = folder / f"{name}.kicad_pcb"
    board.touch()  # only the existing project path resolver reads this placeholder
    for filename, value in ((name, root_text), (child, "Authored child")):
        (folder / f"{filename}.kicad_sch").write_text(
            '(kicad_sch (version 20250114) (generator "fenolite_owned_probe") (paper "A4") '
            f'(text "{value}" (at 40 40 0) (effects (font (size 1.27 1.27)))))',
            encoding="utf-8",
        )
    return Original(board, folder, "kicad", tuple(sorted(folder.iterdir())))


def compare(first, second):
    return presentation_level(first, second, pixel_ppm=1000, pitch_nm=50_000)


def test_explicit_root_pairs_without_changing_any_scene_or_child(tmp_path: Path) -> None:
    first = project(tmp_path / "a", "root with space")
    second = project(tmp_path / "b", "root_with_space")
    a, b = _paired_sheet_scenes(first, second)
    assert set(a) == set(b) == {"sheet:root with space.kicad_sch", "sheet:aaa.kicad_sch"}
    assert not compare(a, b).differences


def test_renamed_root_retains_a_visible_loss(tmp_path: Path) -> None:
    a = project(tmp_path / "a", "root with space")
    b = project(tmp_path / "b", "root_with_space", root_text="A visibly longer changed authored probe")
    result = compare(*_paired_sheet_scenes(a, b))
    assert result.differences and {row.kind for row in result.differences} == {"render-pixels"}
    assert all(row.where.startswith("sheet:root with space.kicad_sch") for row in result.differences)


def test_child_filenames_are_not_normalized(tmp_path: Path) -> None:
    a = project(tmp_path / "a", "root with space", child="child with space")
    b = project(tmp_path / "b", "root_with_space", child="child_with_space")
    result = compare(*_paired_sheet_scenes(a, b))
    assert {row.kind for row in result.differences} == {"render-missing"}
    assert {row.where for row in result.differences} == {
        "sheet:child with space.kicad_sch",
        "sheet:child_with_space.kicad_sch",
    }


@pytest.mark.parametrize("side", ("original", "rebuilt"))
def test_a_child_cannot_be_overwritten_by_root_pairing(side: str, tmp_path: Path) -> None:
    a = project(tmp_path / "a", "root with space", child="root_with_space" if side == "original" else "aaa")
    b = project(tmp_path / "b", "root_with_space", child="root with space" if side == "rebuilt" else "aaa")
    with pytest.raises(FormatError, match="collides"):
        _paired_sheet_scenes(a, b)


def test_missing_root_is_not_invented(tmp_path: Path) -> None:
    a = project(tmp_path / "a", "root with space")
    b = project(tmp_path / "b", "root_with_space")
    root = b.root / "root_with_space.kicad_sch"
    root.unlink()
    b = Original(b.path, b.root, b.backend, tuple(path for path in b.files if path != root))
    scenes_a, scenes_b = _paired_sheet_scenes(a, b)
    assert "sheet:root with space.kicad_sch" not in scenes_b
    assert {row.kind for row in compare(scenes_a, scenes_b).differences} == {"render-missing"}
