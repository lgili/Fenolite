# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""User layers ``User.1`` … ``User.<n>`` on the running ``kicad-cli`` (hypothesis H-K-BOARD-USERLAYERS;
change c0161, task 1.2; ``docs/formats/kicad/board.md``, "User layers").

``test_rows_follow_the_record`` is hermetic: the rows ``layers.user_rows`` writes are the numbers that
KiCad's own 10.0.6 files hold (``User.1`` is 39, ``User.45`` is 127). The oracle test runs the probe
``pcb-user-layers`` of ``_userlayers``.
"""

from __future__ import annotations

import _userlayers as ul
import pytest

from fenolite.backends.kicad.layers import USER_LAYERS, user_rows
from fenolite.backends.kicad.pcb import read_board


def test_rows_follow_the_record() -> None:
    rows = user_rows(45, target=10, names=["Mechanical 1"])
    assert rows[0] == (39, "User.1", "user", "Mechanical 1")
    assert rows[1] == (41, "User.2", "user", None)
    assert rows[-1] == (127, "User.45", "user", None)
    assert USER_LAYERS == {9: 45, 10: 45}
    with pytest.raises(ValueError, match="0 to 45 user layers"):
        user_rows(46, target=9)


@pytest.mark.parametrize("target", [9, 10])
def test_probe_board_reads_back(target: int) -> None:
    back = read_board(ul.board(USER_LAYERS[target], target))
    assert back.board is not None
    names = [layer.name for layer in back.board.layers if layer.name.startswith("User.")]
    assert names == [f"User.{n}" for n in range(1, USER_LAYERS[target] + 1)]
    assert {g.layer for g in back.board.graphics} == set(names)


@pytest.mark.needs_kicad
def test_user_layers_hold_items() -> None:
    from _probes import major, run

    assert run("pcb-user-layers") == "equal", f"KiCad {major()}"


@pytest.mark.needs_kicad
def test_copper_rows_up_to_32() -> None:
    from _probes import major, run

    assert run("pcb-copper-32") == "equal", f"KiCad {major()}"
