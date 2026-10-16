# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The defaults of the panel checks cite their sources (capability board-panels, "Panel limits cite their
sources"; ``H-G-PANEL-LIMITS``; change c0173)."""

from __future__ import annotations

import dataclasses
import re
from fractions import Fraction
from pathlib import Path

import pytest

from fenolite.dsl import DslError, Panel, mm, to_model
from fenolite.model.panel import PanelLimits
from fenolite.panel.limits import DEFAULTS, resolved

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "docs" / "formats" / "kicad" / "panel.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
WORDS = {"one": 1, "two": 2, "three": 3}


def _rows() -> list[tuple[str, str]]:
    """``(fact, sources)`` of every fact row of ``panel.md``."""
    rows: list[tuple[str, str]] = []
    for line in PAGE.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] not in ("fact", "---"):
            rows.append((cells[0], cells[1]))
    return rows


def _value(figure: str) -> int:
    """The first number of ``figure`` in nanometres when a ``mm`` follows, else as a count."""
    first = figure.split()[0]
    if first in WORDS:
        return WORDS[first]
    number = Fraction(first)
    return int(number * 1_000_000) if figure.endswith("mm") else int(number)


@pytest.mark.parametrize("name", sorted(DEFAULTS))
def test_every_default_cites_its_row(name: str) -> None:
    default = DEFAULTS[name]
    matches = [(fact, sources) for fact, sources in _rows() if default.row in fact]
    assert len(matches) == 1, f"{name}: {default.row!r} names {len(matches)} rows of panel.md"
    fact, sources = matches[0]
    registered = SOURCES.read_text(encoding="utf-8")
    for source in default.sources:
        assert source in sources, f"{name}: the row does not cite {source}"
        assert re.search(rf"^\| {source} \|", registered, re.M), f"{source} is not registered"
    assert default.figure in fact, f"{name}: the row holds no {default.figure!r}"
    assert _value(default.figure) == default.value, name


def test_every_limit_has_a_default() -> None:
    assert sorted(DEFAULTS) == sorted(f.name for f in dataclasses.fields(PanelLimits))


def test_limits_replace_the_defaults() -> None:
    panel = Panel("p", board="b.kicad_pcb", limits={"vscore_copper": mm(1), "fiducial_count": 4})
    found = resolved(to_model(panel).limits)
    assert (found.vscore_copper, found.fiducial_count, found.gap) == (1_000_000, 4, 1_200_000)


@pytest.mark.parametrize("value", [3, "x", -1, mm(-1)])
def test_a_limit_that_is_no_length(value: object) -> None:
    with pytest.raises(DslError, match="gap"):
        Panel("p", board="b.kicad_pcb", limits={"gap": value})
