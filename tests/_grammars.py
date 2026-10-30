# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored grammar families of change c0263 (illustrative, ``Example Passive``) for the tests."""

from __future__ import annotations

from pathlib import Path

from fenolite.pick.grammar.schema import GrammarFamily, parse_family, read_family

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "families"
EXAMPLE_DEVICES = EXAMPLES / "devices"
FIXTURES = ROOT / "tests" / "fixtures" / "families"
MLCC = EXAMPLE_DEVICES / "example_mlcc.toml"
CHIP_R = EXAMPLE_DEVICES / "example_chip_r.toml"
FILM_R = EXAMPLE_DEVICES / "example_film_r.toml"
THIN_R = FIXTURES / "example_thin_r.toml"


def authored_files() -> list[Path]:
    """Every authored grammar file of the examples and the test fixtures, in path order."""
    return sorted([*EXAMPLE_DEVICES.glob("*.toml"), *FIXTURES.glob("*.toml")])


def authored() -> list[GrammarFamily]:
    return [read_family(path) for path in authored_files()]


def mlcc() -> GrammarFamily:
    return read_family(MLCC)


def edited(path: Path, old: str, new: str) -> GrammarFamily:
    """The family of ``path`` with ``old`` replaced by ``new`` (``old`` must occur)."""
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    return parse_family(text.replace(old, new, 1), file=path.name)
