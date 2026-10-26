# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Each row of the downgrade resolver proved on 9.0.9 and 10.0.6 (change c0162, ``H-K-DOWN-ROWS``;
capability kicad-version-gating, "Downgrade resolver", scenario "Each row proved on 9.0.9").

Run once per pinned image (``FENOLITE_KICAD_CLI=docker:kicad/kicad:9.0.9`` and ``:10.0.6``). The benches
and what each major checks: ``_downbench``.
"""

from __future__ import annotations

import os

import _downbench
import _probes
import pytest

from fenolite.backends.kicad import resolver

pytestmark = pytest.mark.needs_kicad


def test_protection_defaults() -> None:
    """Task 1.2: the absent default of covering, plugging, capping and filling is ``no``."""
    outcome = _downbench.protection_defaults(_probes.runner())
    print(f"protection defaults on {_probes.version()}: {outcome}")
    assert outcome == "equal"


@pytest.mark.skipif(os.environ.get(_downbench.WRITE_VARIABLE) != "1", reason="writes the benches")
def test_write_benches() -> None:
    """``FENOLITE_GOLDEN_WRITE=1`` on 10.0.6: the benches as 10.0.6 saves them, and its violation types."""
    if _probes.major() != 10:
        pytest.skip("the benches are saved by 10.0.6")
    _downbench.write_benches(_probes.runner())


def test_every_row_has_a_bench() -> None:
    """Each resolver row of a board, footprint, schematic or symbol kind has a bench and a recorded
    source; the rules and project rows have none (no ``kicad-cli`` check reads them alone)."""
    table = resolver.load()
    benched = {item.row for item in _downbench.benches()}
    rows = {r for r in table.rows if not r.startswith(("project:", "rules-"))}
    assert benched == rows
    recorded = _downbench.recorded()
    for item in _downbench.benches():
        assert item.path.is_file() and item.id in recorded, item.id


@pytest.mark.parametrize("bench", [item.id for item in _downbench.benches()])
def test_row(bench: str) -> None:
    """Scenario "Each row proved on 9.0.9": ``equal``, or ``different`` for a row whose action is
    ``design`` (its loss is reported and needs consent)."""
    item = _downbench.bench(bench)
    outcome = _probes.run(f"down-row-{bench}")
    _, edits = _downbench.downgraded(item, _downbench.saved(item))
    action = _downbench.action_of(item, edits)
    print(f"down-row-{bench}: {outcome} on {_probes.version()} ({item.row}: {action})")
    assert outcome == "equal" or (outcome == "different" and action == "design")


def test_buried_form() -> None:
    """Task 1.2: 9.0.9 reads a buried via in the form of a blind via of the same span."""
    outcome = _downbench.buried_form(_probes.runner())
    print(f"buried via form on {_probes.version()}: {outcome}")
    assert outcome == "equal"
