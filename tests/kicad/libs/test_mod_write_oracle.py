# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint libraries written by Fenolite against kicad-cli (capability kicad-library-read, "Footprint
files written by Fenolite read back equal"; hypotheses H-K-LIB-READ and H-K-SEXPR-ESCAPES; change c0018).

``Mini.pretty`` written for target 10 runs on 10.0.6 only; ``Mini_v9.pretty`` written for target 9, the
lossy target-9 copy of ``Mini.pretty`` and the escapes footprint run on both majors. Outcomes are the
``fp-write-*`` probes, pinned per version in ``docs/evidence/kicad/probes/``.
"""

from __future__ import annotations

import _fpwrite
import pytest
from _probes import major, run, runner

pytestmark = pytest.mark.needs_kicad


@pytest.mark.kicad_min_major(10)
def test_mini_written_for_10() -> None:
    result = _fpwrite.mini(runner(), "Mini.pretty", 10)
    assert result.svgs == 4 and run("fp-write-mini-10") == "load"
    assert run("fp-write-mini-10-reread") == "equal"


def test_mini_v9_written_for_9() -> None:
    result = _fpwrite.mini(runner(), "Mini_v9.pretty", 9)
    assert result.svgs == len(_fpwrite.definitions("Mini_v9.pretty"))
    assert run("fp-write-mini-v9-9") == "load" and run("fp-write-mini-v9-9-reread") == "equal"


def test_mini_lossy_for_9() -> None:
    result = _fpwrite.mini(runner(), "Mini.pretty", 9, True)
    assert result.issues and {i.code for i in result.issues} == {"kicad.footprint.dropped-too-new"}
    assert run("fp-write-mini-lossy-9") == "load"


def test_escapes_9() -> None:
    """The 9.0 half of H-K-SEXPR-ESCAPES (also run on 10.0.6 as supporting data)."""
    defn = _fpwrite.escapes()
    again = _fpwrite.escapes_run(runner()).upgraded[defn.name]
    assert again.properties == defn.properties, major()
    assert again.description == defn.description
    assert run("fp-write-escapes-9") == "equal"
