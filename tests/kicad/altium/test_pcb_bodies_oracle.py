# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Written component bodies against ``kicad-cli pcb import`` (capability altium-pcb-writer; change c0121;
hypothesis ``H-A-PCBX-BODY-KICAD``).

The sample ``body2`` is built with and without ``--altium-bodies extruded`` and each PCB document is imported
with ``kicad-cli pcb import --format altium``. The probe ``altium-pcbx-bodies`` (``tests/_bodycases.py``) is
pinned in ``docs/evidence/kicad/probes/<version>.json``. ``pcb import`` exists from 10.0 only (S-0166), so
the importer of 9.0 is not run.

KiCad's importer shows nothing for an extruded body. A pass therefore says two things and no more: the
document with bodies is still read, and nothing else moved. It says nothing about the body, and it settles
no Altium row.
"""

from __future__ import annotations

import _bodycases
import _probes
import pytest
from _resources import kicad_cli_major

pytestmark = pytest.mark.needs_kicad


def _needs_import() -> None:
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")


def test_the_probe_is_registered_for_10_only() -> None:
    assert _probes.PROBES[_bodycases.PROBE].majors == (10,)


def test_kicad_reads_the_document_with_bodies_as_the_one_without() -> None:
    """``H-A-PCBX-BODY-KICAD``: the probe says ``equal``."""
    _needs_import()
    assert _probes.run(_bodycases.PROBE) == "equal"


def test_the_two_imports_are_one_board() -> None:
    """Both imports exit 0 with the same warnings; the two boards hold the same lines but for KiCad's random
    ids, and are equivalent at levels 1 to 4 (the sample holds no copper, so level 5 has nothing to judge)."""
    _needs_import()
    with_bodies, without = _bodycases.imported("extruded"), _bodycases.imported("off")
    assert with_bodies.code == without.code == 0
    assert _bodycases.messages(with_bodies) == _bodycases.messages(without)
    assert not [line for line in _bodycases.messages(with_bodies) if line.startswith("Error")]
    assert _bodycases.masked(with_bodies.text) == _bodycases.masked(without.text)
    report = _bodycases.judge()
    assert report.equivalent and [level.level for level in report.levels] == [1, 2, 3, 4]
    assert report.levels[-1].compared == 3  # the three footprints


def test_kicad_shows_no_model_for_an_extruded_body() -> None:
    """Three extruded bodies are in the document, and no footprint of KiCad's board holds a model: KiCad
    cannot be the oracle of a written body."""
    _needs_import()
    assert _bodycases.models() == (0, 0)
    board = _bodycases.imported("extruded").board.board
    assert board is not None and len(board.footprints) == 3
