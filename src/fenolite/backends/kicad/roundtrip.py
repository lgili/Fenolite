# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT1, the same-version rebuild of a board (c0009 Decision 3; capability kicad-file-backend, "Round-trip
verdict").

RT1 holds when (a) the rebuilt tree equals the parsed tree, (b) a re-read of the rebuilt text gives the
same canonical model as the first read, every ``provenance`` left out, and (c) the opaque counts and
digests agree. ``difference`` locates the first failing condition: the ``kicad-sexpr`` locator of the
first differing node (``sexpr.first_difference``), else ``model`` or ``opaque``.
"""

# evidence: see pcb

from __future__ import annotations

import dataclasses
from typing import Any

from fenolite.backends.base import RoundTrip
from fenolite.backends.kicad.pcb import opaque_count, opaque_digests, read_board, rebuild_board
from fenolite.backends.kicad.sexpr import dumps, first_difference, parse, tree_equal
from fenolite.model.canonical import to_data
from fenolite.model.design import Design


def _without_provenance(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_provenance(v) for k, v in value.items() if k != "provenance"}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, list):
        return [_without_provenance(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def _canonical(design: Design) -> Any:
    return _without_provenance([to_data(design.header), to_data(design.circuit), to_data(design.board)])


def rt1(text: str, *, file: str = "") -> RoundTrip:
    """The RT1 verdict of one board text; the reader's errors are raised unchanged."""
    design = read_board(text, file=file)
    rebuilt = rebuild_board(design)
    original = parse(text, file=file)
    tree_ok = tree_equal(rebuilt, original)
    again = read_board(dumps(rebuilt), file=file)
    # The header name comes from the file name, never from the content.
    again = dataclasses.replace(again, header=dataclasses.replace(again.header, name=design.header.name))
    model_ok = _canonical(again) == _canonical(design)
    opaque_ok = opaque_count(again) == opaque_count(design) and opaque_digests(again) == opaque_digests(
        design
    )
    if not tree_ok:
        difference = first_difference(rebuilt, original) or f"/{original.name}"
    elif not model_ok:
        difference = "model"
    elif not opaque_ok:
        difference = "opaque"
    else:
        difference = ""
    return RoundTrip(
        level="RT1",
        passed=tree_ok and model_ok and opaque_ok,
        tree_equal=tree_ok,
        model_equal=model_ok,
        opaque_equal=opaque_ok,
        opaque_count=opaque_count(design),
        difference=difference,
    )


__all__ = ["rt1"]
