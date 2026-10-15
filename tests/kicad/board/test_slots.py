# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots on the running ``kicad-cli`` (capability kicad-oracle, "Slots pass the oracle"; hypotheses
H-K-SLOT-RING, H-K-SLOT-OVERLAP, H-K-SLOT-UNION and H-K-HOLE-OVERLAP; change c0167).

The boards are those of ``_slotbench``."""

from __future__ import annotations

import _slotbench as sb
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def test_overlapping_cutouts_are_invalid() -> None:
    assert run("slot-overlap") == "present", "KiCad loads two overlapping cut-outs as a valid outline"


def test_union_of_the_ell_loads_clean() -> None:
    assert run("slot-union") == "absent", "KiCad reports a violation on the merged ring of the L"


def test_drilled_slots_overlap_without_a_hole_finding() -> None:
    assert run("slot-drilled-overlap") == "absent", "KiCad reports overlapping drilled slots"


def test_drilled_slot_near_a_plated_hole() -> None:
    wanted = "present" if major() >= 10 else "absent"
    assert run("slot-drilled-near") == wanted, sb.drilled_types(True)


def test_fixture_ring_loads_without_invalid_outline() -> None:
    assert run("slot-ring-drc") == "absent", sb.fixture_types()


def test_fixture_ring_reaches_no_drill_file() -> None:
    assert run("slot-ring-drill") == "absent", "a slot or a cut-out reached a drill file"


def test_fixture_ring_reads_back_as_written() -> None:
    text = dict(sb.fixture_files())[sb.FIXTURE_BOARD]
    assert sb.read_back(text.decode("utf-8") if isinstance(text, bytes) else text) == "equal"


@pytest.mark.kicad_min_major(10)
def test_fixture_ring_reads_back_after_a_resave() -> None:
    assert run("slot-ring-read") == "equal", "the re-saved board does not read back to the slots"
