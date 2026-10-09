# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad plots an equal-sized oval pad as the copper of a circle pad (hypothesis ``H-K-EQ-OVAL``; capability
design-equivalence, "Tolerances and normalisation", "Pad shape"; change c0158).

Two boards that differ only in the shape of their surface-mount pads, ``oval`` and ``circle`` of one
``1.6 x 1.6`` mm size, are plotted to ``F.Cu`` Gerbers; the plots differ only in the aperture of those
pads, an obround of two equal sizes against a circle of that diameter, which are one disc.
"""

from __future__ import annotations

import _gerber
import _ovalcases
import _probes
import pytest

pytestmark = pytest.mark.needs_kicad


def test_the_plots_differ_only_in_the_aperture() -> None:
    found = _ovalcases.plots()
    pairs = _ovalcases.changed_apertures(found["oval"], found["circle"])
    print(f"kicad-cli {_probes.version()}: changed lines {pairs}")
    assert pairs and all(_ovalcases.disc_pair(a, b) for a, b in pairs)
    flashes = _gerber.flashes(found["oval"])
    assert flashes and flashes == _gerber.flashes(found["circle"])


def test_disc_pair() -> None:
    assert _ovalcases.disc_pair("%ADD10O,1.600000X1.600000*%", "%ADD10C,1.600000*%")
    assert not _ovalcases.disc_pair("%ADD10O,1.600000X1.700000*%", "%ADD10C,1.600000*%")
    assert not _ovalcases.disc_pair("%ADD10O,1.600000X1.600000*%", "%ADD11C,1.600000*%")
    assert not _ovalcases.disc_pair("%ADD10R,1.600000X1.600000*%", "%ADD10C,1.600000*%")


def test_probe() -> None:
    outcome = _probes.run("equiv-oval-disc")
    print(f"equiv-oval-disc: {outcome} on kicad-cli {_probes.version()}")
    assert outcome == "equal"
