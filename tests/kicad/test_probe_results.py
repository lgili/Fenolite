# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probe outcomes are pinned per ``kicad-cli`` version (capability kicad-oracle, "Probe results per
kicad-cli version"; change c0017).

Every probe of the running major runs (cache hits when the oracle tests ran first) and its outcome is
compared with ``docs/evidence/kicad/probes/<version>.json``; ``FENOLITE_PROBES_WRITE=1`` writes the file.
"""

from __future__ import annotations

import _probes
import pytest

pytestmark = pytest.mark.needs_kicad


def test_probe_results() -> None:
    _probes.verify(_probes.version(), _probes.outcomes(_probes.major()))
