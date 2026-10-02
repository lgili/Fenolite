# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT1 in ``src`` and the validation operation (capability kicad-file-backend, "Round-trip verdict";
backend-protocol, "Validation operation"; change c0013)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.base import Validator
from fenolite.backends.kicad import backend as backend_module
from fenolite.backends.kicad import roundtrip
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import opaque_count, read_board
from fenolite.backends.kicad.roundtrip import rt1
from fenolite.backends.kicad.sexpr import Atom, Node
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[4]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
FOOTPRINT = ROOT / "tests" / "data" / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"


def test_authored_board_passes() -> None:
    text = TWO_LAYER.read_text(encoding="utf-8")
    verdict = rt1(text, file=TWO_LAYER.name)
    assert verdict.passed and verdict.tree_equal and verdict.model_equal and verdict.opaque_equal
    assert verdict.difference == ""
    assert verdict.opaque_count == opaque_count(read_board(text))


def _grow_first_pad(node: Node, done: list[bool]) -> Node:
    children: list[Node | Atom] = []
    for child in node.children:
        if isinstance(child, Node) and not done:
            if child.name == "size" and node.name == "pad":
                child = child.with_children((Atom.from_nm(9_000_000), Atom.from_nm(9_000_000)))
                done.append(True)
            else:
                child = _grow_first_pad(child, done)
        children.append(child)
    return node.with_children(children)


def test_altered_pad_located(monkeypatch: pytest.MonkeyPatch) -> None:
    original = roundtrip.rebuild_board
    monkeypatch.setattr(roundtrip, "rebuild_board", lambda design: _grow_first_pad(original(design), []))
    verdict = rt1(TWO_LAYER.read_text(encoding="utf-8"))
    assert not verdict.passed and not verdict.tree_equal
    assert "/footprint[" in verdict.difference and "/pad[0]" in verdict.difference


def test_model_and_opaque_difference_named(monkeypatch: pytest.MonkeyPatch) -> None:
    text = TWO_LAYER.read_text(encoding="utf-8")
    counts = iter([1, 2, 1, 2])
    monkeypatch.setattr(roundtrip, "opaque_count", lambda design: next(counts))
    verdict = rt1(text)
    assert verdict.tree_equal and verdict.model_equal and not verdict.opaque_equal
    assert verdict.difference == "opaque" and not verdict.passed


def test_reader_errors_raised_unchanged() -> None:
    with pytest.raises(FormatError):
        rt1("(kicad_pcb (version 20241229)) trailing")


def test_board_validated_through_the_backend() -> None:
    backend = KicadBackend()
    validation = backend.validate(TWO_LAYER)
    assert validation.read == backend.read(TWO_LAYER)
    assert validation.roundtrip.passed


def test_footprint_file_refused() -> None:
    with pytest.raises(ValueError, match="kicad_mod"):
        KicadBackend().validate(FOOTPRINT)


def test_invalid_utf8_raises_format_error(tmp_path: Path) -> None:
    data = TWO_LAYER.read_bytes()
    index = data.index(b'"F.Cu"') + 2
    board = tmp_path / "bad.kicad_pcb"
    board.write_bytes(data[:index] + b"\xff" + data[index:])
    with pytest.raises(FormatError):
        KicadBackend().validate(board)


def test_kicad_backend_is_a_validator() -> None:
    assert isinstance(backend_module._VALIDATOR, Validator)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(KicadBackend(), Validator)
    assert "validate" in KicadBackend().capabilities().operations
