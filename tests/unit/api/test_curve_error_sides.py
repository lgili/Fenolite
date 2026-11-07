# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project geometry is an explicit hashed input of each comparison side (c0340)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import _drawn_fonts
import pytest

from fenolite.api import equivalent
from fenolite.api.sides import SideUsageError, _project_context, read_side, source_hashes
from fenolite.backends.kicad import pro
from fenolite.backends.kicad.lowering import millimetres
from fenolite.core.errors import FormatError


def project(folder: Path, error: int) -> Path:
    original = _drawn_fonts.original(folder, target=9)
    path = original / "font_probe.kicad_pro"
    data = pro.read_project_text(path.read_text())
    data["board"]["design_settings"]["rules"]["max_error"] = millimetres(error)
    path.write_text(pro.write_project_text(data))
    return path


def test_project_and_adjacent_board_sides_read_hashed_setting(tmp_path: Path) -> None:
    path = project(tmp_path / "original", 10_000)
    for given in (path, path.parent, path.with_suffix(".kicad_pcb")):
        side = read_side(given)
        assert side.design.board is not None and side.design.board.max_curve_error == 10_000
        hashes = {file.name: digest for file, digest in side.source_files}
        assert hashes[path.name] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert (
            hashes[path.with_suffix(".kicad_pcb").name]
            == hashlib.sha256(path.with_suffix(".kicad_pcb").read_bytes()).hexdigest()
        )


def test_equivalent_reports_project_input_hashes_and_exact_setting_delta(tmp_path: Path) -> None:
    first = project(tmp_path / "first", 10_000)
    other = tmp_path / "second"
    shutil.copytree(first.parent, other)
    second = other / first.name
    data = pro.read_project_text(second.read_text())
    data["board"]["design_settings"]["rules"]["max_error"] = millimetres(20_000)
    second.write_text(pro.write_project_text(data))
    result = equivalent(first, second, level=6).to_json()
    assert result["equivalent"] is False
    assert [(row["field"], row["a"], row["b"]) for row in result["differences"]] == [
        ("max_curve_error", "10000", "20000")
    ]
    assert result["sides"]["a"]["files"][first.name] != result["sides"]["b"]["files"][second.name]
    assert all("/" not in name for side in result["sides"].values() for name in side["files"])


def test_malformed_adjacent_project_never_falls_back_to_default(tmp_path: Path) -> None:
    path = project(tmp_path / "original", 10_000)
    data = pro.read_project_text(path.read_text())
    data["board"]["design_settings"]["rules"]["max_error"] = None
    path.write_text(pro.write_project_text(data))
    with pytest.raises(FormatError) as caught:
        read_side(path.with_suffix(".kicad_pcb"))
    assert caught.value.file == path.name and caught.value.locator.endswith("/max_error")


def test_explicit_project_precedes_adjacent_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board, explicit = tmp_path / "authored.kicad_pcb", tmp_path / "selected.kicad_pro"

    def forbidden(_path):
        raise AssertionError("an explicit project must not be replaced by directory guessing")

    monkeypatch.setattr(Path, "iterdir", forbidden)
    assert _project_context(board, explicit) == explicit


def test_ambiguous_adjacent_projects_are_not_chosen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    board = tmp_path / "authored.kicad_pcb"
    candidates = (tmp_path / "authored.kicad_pro", tmp_path / "AUTHORED.kicad_pro")
    monkeypatch.setattr(Path, "iterdir", lambda _path: iter(candidates))
    with pytest.raises(SideUsageError, match="ambiguous"):
        _project_context(board, None)


@pytest.mark.parametrize("same_path", (True, False))
def test_input_trace_never_clobbers_ambiguous_names_or_hashes(tmp_path: Path, same_path: bool) -> None:
    first = tmp_path / "one/authored.kicad_pro"
    other = first if same_path else tmp_path / "two/authored.kicad_pro"
    with pytest.raises(SideUsageError, match="ambiguous"):
        source_hashes(((first, "a" * 64), (other, "b" * 64)))
