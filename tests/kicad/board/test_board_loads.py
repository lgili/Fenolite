# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Boards load in kicad-cli through the package runner (capability kicad-oracle, change c0009)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _corpus import CorpusItem, require
from _kicad import supported_version
from _resources import kicad_cli

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import rebuild_board
from fenolite.backends.kicad.sexpr import dumps

pytestmark = pytest.mark.needs_kicad

FIXTURE = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def runner() -> KicadCli:
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    return KicadCli(Path(path))


@pytest.mark.parametrize(
    "fixture", [FIXTURE, FIXTURE.with_name("stackup_four.kicad_pcb")], ids=lambda p: p.stem
)
def test_fixture_loads(fixture: Path) -> None:
    """The authored boards load: the two-layer board and the four-layer board with a stack-up (c0101)."""
    version = supported_version()
    run = runner().load_board_svg(fixture)
    assert run.ok and run.outputs["out.svg"].lstrip().startswith(b"<?xml"), version


@pytest.mark.needs_corpus
@pytest.mark.parametrize("item", [i for i in READABLE_ITEMS if not i.heavy], ids=lambda i: i.id)
def test_rebuilt_corpus_board_loads(item: CorpusItem, tmp_path: Path) -> None:
    design, _ = read(require(item))
    rebuilt = tmp_path / item.path.name
    rebuilt.write_text(dumps(rebuild_board(design)), encoding="utf-8")
    run = runner().load_board_svg(rebuilt)
    assert run.ok and "out.svg" in run.outputs, item.id
