# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The export probes on the running ``kicad-cli`` (``H-K-EXPORT-FILES``, ``H-K-EXPORT-REPEAT``,
``H-K-EXPORT-RENDER``; capability kicad-oracle, "Exports are probed on both majors"; change c0024)."""

from __future__ import annotations

import _exportcases
import pytest
from _probes import run

from fenolite.backends.kicad.plot import png_size
from fenolite.exports.plan import KINDS

pytestmark = pytest.mark.needs_kicad
BYTE_EQUAL = {"gerbers": False, "drill": False, "pos": True, "ipcd356": True}
"""Whether two exports are byte-equal, per kind, as recorded in ``docs/evidence/kicad-export.md``."""


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_files(kind: str) -> None:
    assert run(f"export-files-{kind}") == "equal"


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_repeat(kind: str) -> None:
    unknown = _exportcases.unknown_lines(kind)
    assert not unknown, f"{kind}: lines that differ between two runs and are no known date line: {unknown}"
    assert run(f"export-repeat-{kind}") == "equal"
    assert _exportcases.byte_equal(kind) is BYTE_EQUAL[kind]
    assert KINDS[kind].repeatable is BYTE_EQUAL[kind]


def test_render() -> None:
    assert run("export-render-svg") == "present"
    assert run("export-render-png") == "present"
    data, message = _exportcases.view("top.png")
    assert data is not None, message
    size = png_size(data)
    assert size is not None
    assert 0 < size[0] <= _exportcases.RENDER_SIZE[0] and 0 < size[1] <= _exportcases.RENDER_SIZE[1]
