# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board headers with other ``generator_version`` values (capability kicad-oracle; hypothesis
H-K-GENVER; change c0017).

The triad texts with ``generator_version`` absent, ``"9.0"``, ``"10.0"`` and ``"fenolite-x"``: the
target-9 text on both majors, the target-10 text on 10.0.6. Outcomes are recorded per probe; the
emitted value must load.
"""

from __future__ import annotations

import pytest
from _probes import GENERATOR_VERSIONS, major, run

pytestmark = pytest.mark.needs_kicad


def test_generator_version_variants() -> None:
    targets = [9, 10] if major() >= 10 else [9]
    for target in targets:
        outcomes = {label: run(f"pcb-genver-{target}-{label}") for label in GENERATOR_VERSIONS}
        assert set(outcomes.values()) <= {"load", "reject"}, outcomes
        assert outcomes[f"{target}.0"] == "load", outcomes
