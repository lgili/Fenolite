# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layer tables of n copper layers for the table probes (capability kicad-oracle, "Created layer tables
are probed on both majors"; hypothesis H-K-PCB-LAYERS; change c0100, design Decisions 2 and 10).

``rows(n)`` is the test's own statement of the row rule, for any n: the rows of the two-copper table with
one row ``(2k + 2, "In<k>.Cu", "signal")`` per inner layer k = 1 … n − 2 right after ``F.Cu``. It also
gives the table of 3, which ``layers.created_layers`` refuses to create. A hermetic test compares it
with ``created_layers(n)`` for the counts Fenolite creates.
"""

from __future__ import annotations

import dataclasses
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from _boards import created_board

from fenolite.backends.kicad.layers import CREATED_ROWS, layer_kind
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.ids import derived_id
from fenolite.model.base import ExtBag
from fenolite.model.board import Layer
from fenolite.model.design import Design

Row = tuple[int, str, str, str | None]
COUNTS: tuple[int, ...] = (2, 4, 6, 8)
ODD = 3
"""The negative control: a count KiCad refuses."""
TARGETS: tuple[int, ...] = (9, 10)
PROJECT = "{}\n"


def rows(copper: int) -> tuple[Row, ...]:
    """The table of ``copper`` copper layers by the row rule, for any count of at least 2."""
    assert copper >= 2
    inner: tuple[Row, ...] = tuple((2 * k + 2, f"In{k}.Cu", "signal", None) for k in range(1, copper - 1))
    return CREATED_ROWS[:1] + inner + CREATED_ROWS[1:]


def table(copper: int) -> tuple[Layer, ...]:
    """``rows(copper)`` as model layers, with the KiCad number, type and user name in ``ext["kicad"]``."""
    layers: list[Layer] = []
    for ordinal, (number, name, row_type, user_name) in enumerate(rows(copper)):
        pairs = [("number", str(number)), ("type", row_type)]
        if user_name is not None:
            pairs.append(("user_name", user_name))
        layers.append(
            Layer(
                id=derived_id("lay", "kicad", f"layer:{name}"),
                ext={"kicad": ExtBag(None, tuple(pairs))},
                name=name,
                kind=layer_kind(name, row_type),
                ordinal=ordinal,
            )
        )
    return tuple(layers)


def copper_rows(layers: tuple[Layer, ...]) -> tuple[tuple[str, str, str, str | None], ...]:
    """Number, name, type and user name of each copper row, in table order."""
    found = []
    for layer in layers:
        if layer.kind == "copper":
            bag = dict(layer.ext["kicad"].payload)
            found.append((bag["number"], layer.name, bag["type"], bag.get("user_name")))
    return tuple(found)


def board(copper: int) -> Design:
    """The created test board with its layer table replaced by the table of ``copper`` layers, and
    without its stack-up: the stack-up of ``created_board(2)`` names two copper layers, and the writer
    refuses one whose copper entries are not the table's (c0101, "Stack-up written to boards"). The
    probes judge the table alone; KiCad derives its default stack-up, as it did when c0100 measured."""
    design = created_board(2)
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=table(copper), stackup=None)
    return dataclasses.replace(design, board=board)


@cache
def text(copper: int, target: int) -> str:
    return write_board(board(copper), target=target).text


@dataclass(frozen=True)
class TableRun:
    loaded: bool
    gerbers: tuple[str, ...]
    resaved: tuple[tuple[str, str, str, str | None], ...] | None


def _gerber_layers(outputs: object) -> tuple[str, ...]:
    names = []
    for name in outputs:  # type: ignore[attr-defined]
        stem = str(name).rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if stem.endswith("_Cu"):
            names.append(stem.rsplit("-", 1)[-1].replace("_", "."))
    return tuple(sorted(names))


@cache
def table_run(copper: int, target: int) -> TableRun:
    """Load (``pcb drc`` with a parsed report), copper Gerbers and, on 10.0, the re-saved copper rows."""
    from _probes import runner

    cli = runner()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "b.kicad_pcb"
        path.write_text(text(copper, target), encoding="utf-8")
        project = path.with_suffix(".kicad_pro")
        project.write_text(PROJECT, encoding="utf-8")
        extra = {project.name: project}
        loaded = cli.drc(path, files=extra).report is not None
        run = cli.run(["pcb", "export", "gerbers", "-o", "g/", path.name], files={path.name: path, **extra})
        gerbers = _gerber_layers(run.outputs) if run.ok else ()
        resaved = None
        if loaded and cli.major() >= 10:
            saved = cli.upgrade_board(path, files=extra).decode("utf-8")
            back = read_board(saved)
            assert back.board is not None
            resaved = copper_rows(back.board.layers)
    return TableRun(loaded, gerbers, resaved)


def load_outcome(copper: int, target: int) -> str:
    return "load" if table_run(copper, target).loaded else "reject"


def gerber_outcome(copper: int, target: int) -> str:
    expected = tuple(sorted(row[1] for row in rows(copper) if row[1].endswith(".Cu")))
    return "equal" if table_run(copper, target).gerbers == expected else "different"


def resave_outcome(copper: int, target: int) -> str:
    return "equal" if table_run(copper, target).resaved == copper_rows(table(copper)) else "different"


def table_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """The ``pcb-layers-*`` probes. A major loads the texts up to its own format, so the target-10 text
    runs on 10.0 only; the re-save runs on 10.0 only, because 9.0 has no ``pcb upgrade`` (S-0037)."""
    probes: dict[str, tuple[object, tuple[int, ...]]] = {}
    for target in TARGETS:
        majors = (9, 10) if target == 9 else (10,)
        for copper in COUNTS:
            probes[f"pcb-layers-{copper}-t{target}"] = (
                lambda copper=copper, target=target: load_outcome(copper, target),
                majors,
            )
            probes[f"pcb-layers-gerbers-{copper}-t{target}"] = (
                lambda copper=copper, target=target: gerber_outcome(copper, target),
                majors,
            )
            probes[f"pcb-layers-resave-{copper}-t{target}"] = (
                lambda copper=copper, target=target: resave_outcome(copper, target),
                (10,),
            )
        probes[f"pcb-layers-odd-t{target}"] = (lambda target=target: load_outcome(ODD, target), majors)
    return probes
