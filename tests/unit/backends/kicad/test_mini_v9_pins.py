# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Nine-format ``Mini_R`` and ``Mini_LED`` (capability design-dsl, "Blink examples", scenario "Equal pins in
both formats"; change c0011 Decision 18)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad.sexpr import load
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.backends.kicad.versions import FileKind, check_emittable

LIBS = Path(__file__).resolve().parents[4] / "tests" / "data" / "libs"


def pins(path: Path, name: str) -> list[tuple[str, str, str]]:
    (symbol,) = [s for s in read_symbol_library(path, library="Mini") if s.name == name]
    return [(p.number, p.name, p.etype) for p in symbol.pins]


@pytest.mark.parametrize("name", ["Mini_R", "Mini_LED"])
def test_equal_pins_in_both_formats(name: str) -> None:
    assert pins(LIBS / "Mini_v9.kicad_sym", name) == pins(LIBS / "Mini.kicad_sym", name)


def test_nine_format_is_clean_for_target_9() -> None:
    node = load(LIBS / "Mini_v9.kicad_sym")
    assert node.find("version").atoms()[0].text == "20241209"  # type: ignore[union-attr]
    assert [i for i in check_emittable(node, FileKind.SYMBOL_LIB, 9) if i.severity == "error"] == []
    assert {"Mini_R", "Mini_LED"} <= {s.atoms()[0].value for s in node.nodes("symbol")}
    text = (LIBS / "Mini_v9.kicad_sym").read_text(encoding="utf-8")
    for head in ("in_pos_files", "duplicate_pin_numbers_are_jumpers", "show_name", "do_not_autoplace"):
        assert f"({head}" not in text, head


def test_led_pins() -> None:
    assert [(n, name) for n, name, _ in pins(LIBS / "Mini_v9.kicad_sym", "Mini_LED")] == [
        ("1", "K"),
        ("2", "A"),
    ]
