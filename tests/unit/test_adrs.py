# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Architecture Decision Records follow the MADR-lite structure."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ADR_DIR = Path(__file__).resolve().parents[2] / "docs" / "adr"
SECTIONS = ["## Status", "## Context", "## Decision", "## Alternatives", "## Consequences", "## Evidence"]
STATUS = re.compile(r"^(Proposed|Accepted|Deprecated|Superseded by ADR-\d{4})\b")
REQUIRED = ["0001-neutral-model.md", "0003-clean-room-and-provenance.md", "0004-licence-apache-2.0.md"]


def _adrs() -> list[Path]:
    return sorted(p for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))


@pytest.mark.parametrize("name", REQUIRED)
def test_required_adr_exists(name: str) -> None:
    assert (ADR_DIR / name).is_file()


@pytest.mark.parametrize("path", _adrs(), ids=lambda p: p.name)
def test_adr_structure(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    number = path.name[:4]
    assert text.startswith(f"# ADR-{number}: "), "title must be '# ADR-NNNN: <title>'"
    positions = [text.find(s + "\n") for s in SECTIONS]
    assert all(p >= 0 for p in positions), (
        f"missing sections: {[s for s, p in zip(SECTIONS, positions, strict=True) if p < 0]}"
    )
    assert positions == sorted(positions), "sections out of order"
    status_line = text.split("## Status\n", 1)[1].strip().splitlines()[0]
    assert STATUS.match(status_line), f"invalid status line: {status_line!r}"


def test_adr_0004_states_process_boundary_rule() -> None:
    text = (ADR_DIR / "0004-licence-apache-2.0.md").read_text(encoding="utf-8")
    assert "only behind a process boundary or a published plugin API, never" in text
    assert "imported or vendored" in text
