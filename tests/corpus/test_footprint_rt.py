# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint codec round trip over two corpus origins (capability kicad-library-read, "Footprint files
written by Fenolite read back equal"; footprint half of H-K-LIB-READ; change c0018).

Every footprint of a board is read as a definition with ``board_footprints``, written with
``write_footprint`` and read again with ``read_footprint``. ``-k demo`` covers the non-heavy demo boards
that the board reader reads with 0 errors, at the board's own major (9 for an 8.0 board). ``-k upgraded``
covers the ``pcb upgrade --force`` copies of the third-party rows, made in memory on KiCad 10 and never
written to the repository. Items are named by their manifest id only.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from _boardcorpus import BOARD_ITEMS, READABLE_ITEMS, read
from _corpus import CorpusItem, require
from _resources import kicad_cli

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import versions
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.mod import board_footprints, read_footprint, write_footprint
from fenolite.backends.kicad.sexpr import load, parse
from fenolite.model.base import Opaque
from fenolite.model.board import Pad
from fenolite.model.library import FootprintDef

pytestmark = pytest.mark.needs_corpus
DEMOS = [i for i in READABLE_ITEMS if not i.heavy]
THIRD_PARTY = [i for i in BOARD_ITEMS if i.origin == "third-party" and not i.heavy]
HEADER = ("(version ", "(generator ", "(generator_version ")
COUNTS: Counter[str] = Counter()


def bare(defn: FootprintDef) -> FootprintDef:
    def clean(pad: Pad) -> Pad:
        stack = pad.padstack
        if stack is not None:
            stack = dataclasses.replace(stack, provenance=None, ext={})
        return dataclasses.replace(pad, provenance=None, ext={}, padstack=stack)

    return dataclasses.replace(
        defn,
        provenance=None,
        ext={},
        pads=tuple(clean(p) for p in defn.pads),
        graphics=tuple(dataclasses.replace(g, provenance=None, ext={}) for g in defn.graphics),
    )


def fragments(defn: FootprintDef) -> list[str]:
    found = [s.fragment for s in slotlib.from_ext(defn.ext["kicad"]) if isinstance(s, Opaque)]
    return [f for f in found if not f.startswith(HEADER)]


def first_field(a: FootprintDef, b: FootprintDef) -> str:
    for field in dataclasses.fields(FootprintDef):
        if getattr(a, field.name) != getattr(b, field.name):
            return field.name
    return "opaque fragments"


def round_trip(label: str, text: str, target: int) -> int:
    defs = board_footprints(text)
    for index, defn in enumerate(defs):
        again = read_footprint(write_footprint(defn, target=target), library=defn.library)
        if bare(again) != bare(defn) or fragments(again) != fragments(defn):
            pytest.fail(
                f"{label}: footprint {index}: first differing field {first_field(bare(again), bare(defn))}"
            )
    return len(defs)


@pytest.mark.parametrize("item", DEMOS, ids=lambda i: i.id)
def test_demo(item: CorpusItem) -> None:
    path = require(item)
    _, issues = read(path)
    if any(i.severity == "error" for i in issues):
        pytest.skip(f"{item.id}: the board reader reports errors")
    major = versions.major_for(versions.FileKind.BOARD, versions.detect_version(load(path))) or 10
    COUNTS[item.origin] += round_trip(item.id, path.read_text(encoding="utf-8"), max(9, major))


@cache
def runner() -> KicadCli:
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    return KicadCli(Path(path), timeout=600)


@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("item", THIRD_PARTY, ids=lambda i: i.id)
def test_upgraded(item: CorpusItem) -> None:
    text = runner().upgrade_board(require(item)).decode("utf-8")
    parse(text)
    COUNTS[item.origin] += round_trip(f"{item.id} (upgraded)", text, 10)


def test_counts_printed() -> None:
    print("footprints round-tripped per origin:", dict(COUNTS))
