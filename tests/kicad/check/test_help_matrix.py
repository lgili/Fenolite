# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The command matrix read from ``kicad-cli`` help pages matches the documented command sets
(``H-K-CLI-HELP``; capability kicad-oracle, "Subcommand matrix from help text", scenario "Matrix matches
the documented command sets"). Every row is also a ``check-help-*`` probe pinned per version."""

from __future__ import annotations

import pytest
from _checkcases import matrix
from _probes import major, run

from fenolite.backends.kicad.helpmatrix import MATRIX, probe_id

pytestmark = pytest.mark.needs_kicad

TEN_ONLY = (("pcb", "import"), ("pcb", "upgrade"))
TEN_ONLY_OPTIONS = ("--refill-zones", "--save-board")
BOTH = (("pcb", "export", "ipcd356"), ("pcb", "export", "pos"), ("pcb", "export", "svg"))
BOTH_OPTIONS = ("--format", "--severity-all")


def test_matrix_matches_facts() -> None:
    found = matrix()
    assert found.unparsed == ()
    ten = major() >= 10
    for command in TEN_ONLY:
        assert run(probe_id(command)) == ("present" if ten else "absent"), command
    for option in TEN_ONLY_OPTIONS:
        assert run(probe_id(("pcb", "drc"), option)) == ("present" if ten else "absent"), option
    for command in BOTH:
        assert run(probe_id(command)) == "present", command
    for option in BOTH_OPTIONS:
        assert run(probe_id(("pcb", "drc"), option)) == "present", option


def test_every_row_recorded() -> None:
    for entry in MATRIX:
        assert run(probe_id(entry.command)) in {"present", "absent"}
        for option in entry.options:
            assert run(probe_id(entry.command, option)) in {"present", "absent"}
