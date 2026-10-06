# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A pad that differs from its library pad only by ``(zone_connect N)`` raises no library mismatch
(``H-K-PAD-ZONE-LIB``; capability design-dsl, "Pad zone connections in a build", scenario "KiCad reports no
library mismatch"; change c0068)."""

from __future__ import annotations

import _padzonecases as pz
import pytest
from _probes import libdrc, major, run

from fenolite.backends.kicad import drc as drcmod

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("connection", pz.CONNECTIONS)
def test_no_library_mismatch(connection: str) -> None:
    output = pz.built(connection, major())
    text = output.files[pz.BOARD].decode("utf-8")
    assert (
        text.count(f"(zone_connect {pz.CONNECTIONS[connection]})") == 1 and text.count("(zone_connect") == 1
    )
    found = pz.report(connection)
    assert found is not None, "pcb drc wrote no report"
    assert pz.mismatches(found) == 0
    assert pz.naming_the_pad(found, pz.pad_uuid(output)) == []
    assert not found.of_type(drcmod.LIB_FOOTPRINT_ISSUES), "the vendored library was not found"


def test_the_library_check_runs() -> None:
    """A library check that reports nothing proves nothing: the missing-table control must speak."""
    assert libdrc("missing-table") == "present"


def test_probe_pad_zone_lib() -> None:
    assert run("pad-zone-lib") == "absent"
