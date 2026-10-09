# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Each row of the downgrade resolver proved on 9.0.9 and 10.0.6 (change c0162, ``H-K-DOWN-ROWS``;
capability kicad-version-gating, "Downgrade resolver", scenario "Each row proved on 9.0.9").

Run once per pinned image (``FENOLITE_KICAD_CLI=docker:kicad/kicad:9.0.9`` and ``:10.0.6``). The benches
and what each major checks: ``_downbench``.
"""

from __future__ import annotations

import _downbench
import _probes
import pytest

pytestmark = pytest.mark.needs_kicad


def test_protection_defaults() -> None:
    """Task 1.2: the absent default of covering, plugging, capping and filling is ``no``."""
    outcome = _downbench.protection_defaults(_probes.runner())
    print(f"protection defaults on {_probes.version()}: {outcome}")
    assert outcome == "equal"


def test_buried_form() -> None:
    """Task 1.2: 9.0.9 reads a buried via in the form of a blind via of the same span."""
    outcome = _downbench.buried_form(_probes.runner())
    print(f"buried via form on {_probes.version()}: {outcome}")
    assert outcome == "equal"
