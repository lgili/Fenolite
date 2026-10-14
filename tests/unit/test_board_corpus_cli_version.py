# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""New cached downgrade inputs cannot be sent directly to an older native oracle."""

from pathlib import Path

import pytest
from _boardcorpus import require_cli_board_version

from fenolite.backends.kicad.versions import FORMAT_VERSIONS, READ_FLOOR, FileKind
from fenolite.core.errors import FormatError


def board(tmp_path: Path, version: int) -> Path:
    path = tmp_path / f"board-{version}.kicad_pcb"
    path.write_text(f"(kicad_pcb (version {version}))", encoding="utf-8")
    return path


@pytest.mark.parametrize("source,running", [(9, 9), (9, 10), (10, 10)])
def test_matching_or_newer_cli_is_not_skipped(tmp_path: Path, source: int, running: int) -> None:
    require_cli_board_version(board(tmp_path, FORMAT_VERSIONS[FileKind.BOARD][source]), running)


def test_new_board_is_skipped_only_for_older_cli(tmp_path: Path) -> None:
    path = board(tmp_path, FORMAT_VERSIONS[FileKind.BOARD][10])
    with pytest.raises(pytest.skip.Exception, match="requires KiCad 10; direct oracle is KiCad 9"):
        require_cli_board_version(path, 9)
    require_cli_board_version(path, 10)


def test_read_floor_board_still_runs_on_nine(tmp_path: Path) -> None:
    require_cli_board_version(board(tmp_path, READ_FLOOR[FileKind.BOARD]), 9)


def test_unknown_format_fails_instead_of_skipping(tmp_path: Path) -> None:
    with pytest.raises(pytest.fail.Exception, match="unsupported board format"):
        require_cli_board_version(board(tmp_path, 20990101), 9)


def test_missing_format_header_is_not_silently_skipped(tmp_path: Path) -> None:
    path = tmp_path / "malformed.kicad_pcb"
    path.write_text("(kicad_pcb)", encoding="utf-8")
    with pytest.raises(FormatError, match="format version is missing"):
        require_cli_board_version(path, 9)
