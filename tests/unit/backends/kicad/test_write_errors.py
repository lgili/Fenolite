# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The writer's exceptions: codes, attributes and hints (capabilities kicad-file-backend, cli-contract)."""

from __future__ import annotations

from fenolite.backends.kicad.versions import (
    FileKind,
    LegacyEditRefusedError,
    LossyWriteError,
)
from fenolite.cli.errors import REGISTRY
from fenolite.core.errors import FenoliteError, Issue

TOO_NEW = Issue("kicad.token.too-new", "error", "'duplicate_pad_numbers_are_jumpers' needs KiCad 10.0")
NET_REF = Issue("kicad.board.opaque-net-ref", "error", "net 7 is not in the source table", where="/x")


def test_droppable_loss_names_the_flag() -> None:
    error = LossyWriteError([TOO_NEW], droppable=True)
    assert error.cli_code == "FEN-7001" and isinstance(error, FenoliteError)
    assert error.issues == (TOO_NEW,) and error.droppable is True
    assert "--allow-lossy" in error.hint
    assert "duplicate_pad_numbers_are_jumpers" in str(error)


def test_kept_loss_does_not_name_the_flag() -> None:
    error = LossyWriteError([NET_REF, TOO_NEW], droppable=False)
    assert error.droppable is False and "--allow-lossy" not in error.hint
    assert error.issues == (NET_REF, TOO_NEW) and "1 more" in str(error)


def test_legacy_edit() -> None:
    error = LegacyEditRefusedError(FileKind.BOARD, 20240108)
    assert error.cli_code == "FEN-7003" and error.kind is FileKind.BOARD and error.version == 20240108
    assert "kicad-cli pcb upgrade" in error.hint and "KiCad 9.0" in error.hint
    assert "20240108" in str(error)


def test_codes_are_registered_with_exit_7() -> None:
    for code in ("FEN-7001", "FEN-7002", "FEN-7003"):
        assert REGISTRY[code].exit_code == 7
    assert "kicad-cli pcb upgrade" in REGISTRY["FEN-7003"].hint
