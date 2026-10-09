# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board texts, drawings and dimensions in KiCad (capability kicad-oracle, "Board texts and dimensions are
probed"; hypotheses ``H-K-BOARD-TEXT`` and ``H-K-DIM``; change c0103).

Created boards on the rules bench of ``_rulebench`` (the canary pair, scoped to its own net), written with
``write_board`` for the running major. DRC is judged from the JSON report by violation type and item uuid.
All values are authored for these benches.
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.core.coords import Point, Size
from fenolite.model.base import Entity
from fenolite.model.board import Dimension, Graphic, Text
from fenolite.model.design import Design

MM = rb.MM
RULES = rb.with_scoped_canary("(version 1)\n")
TEXT_LAYERS = ("F.SilkS", "B.SilkS", "F.Fab", "Cmts.User", "Dwgs.User")
JUSTIFY = (
    ("center", "center"),
    ("left", "center"),
    ("right", "center"),
    ("center", "top"),
    ("center", "bottom"),
    ("left", "top"),
    ("left", "bottom"),
    ("right", "top"),
    ("right", "bottom"),
)
"""No justification, then each value of ``dsl.part.FIELD_JUSTIFY``."""
_SVG_NOISE = re.compile(r"<(title|desc)>.*?</\1>", re.DOTALL)


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def text(n: int, string: str, at: Point, layer: str, *, size: int = MM, thickness: int = 150_000,
         h: str = "center", v: str = "center") -> Text:  # fmt: skip
    return Text(
        id=_id("txt", n),
        text=string,
        position=at,
        layer=layer,
        size=Size(size, size),
        thickness=thickness,
        h_justify=h,  # type: ignore[arg-type]
        v_justify=v,  # type: ignore[arg-type]
    )


def with_items(bench: rb.Bench, **collections: tuple[Entity, ...]) -> rb.Bench:
    board = bench.design.board
    assert board is not None
    design = dataclasses.replace(bench.design, board=dataclasses.replace(board, **collections))  # type: ignore[arg-type]
    return rb.Bench(design, dict(bench.items))


def texts_bench() -> tuple[rb.Bench, tuple[Text, ...]]:
    """Texts on every drawing layer of ``TEXT_LAYERS`` with every justification, away from the copper."""
    texts: list[Text] = []
    for row, layer in enumerate(TEXT_LAYERS):
        for column, (h, v) in enumerate(JUSTIFY):
            at = Point((3 + 4 * column) * MM, (10 + 3 * row) * MM)
            texts.append(text(len(texts) + 1, "T", at, layer, h=h, v=v))
    return with_items(rb.builder().build(), texts=tuple(texts)), tuple(texts)


def dimensions() -> tuple[Dimension, ...]:
    """An aligned and an orthogonal dimension of each unit, the first two as the written scenario has
    them: 20 mm at four decimals, and 25.5 mm measured horizontally at two."""
    found: list[Dimension] = []
    for n, units in enumerate(("mm", "in")):
        y = (10 + 6 * n) * MM
        found.append(
            Dimension(
                id=_id("dim", 2 * n + 1),
                kind="aligned",
                layer="Dwgs.User",
                start=Point(10 * MM, y),
                end=Point(30 * MM, y),
                offset=-2 * MM,
                units=units,  # type: ignore[arg-type]
            )
        )
        found.append(
            Dimension(
                id=_id("dim", 2 * n + 2),
                kind="orthogonal",
                layer="Dwgs.User",
                start=Point(5 * MM, y + 3 * MM),
                end=Point(30_500_000, y + 4 * MM),
                offset=2 * MM,
                direction="horizontal",
                units=units,  # type: ignore[arg-type]
                precision=2,
            )
        )
    return tuple(found)


def dimensions_design() -> Design:
    return with_items(rb.builder().build(), dimensions=dimensions()).design


def named(report: DrcReport, uuid: str, *types: str) -> set[str]:
    """The types, among ``types`` (every type when empty), of the violations that name ``uuid``."""
    found = {v.type for v in report.violations if any(item.uuid == uuid for item in v.items)}
    return found & set(types) if types else found


@cache
def texts_run() -> tuple[rb.Bench, tuple[Text, ...], DrcReport | None]:
    bench, texts = texts_bench()
    return bench, texts, rb.drc(runner(), bench, RULES, major())


def _judged(bench: rb.Bench, report: DrcReport | None, found: bool) -> str:
    if report is None or not rb.canary_fired(report, bench):
        return "inconclusive"
    return rb.outcome(found)


def text_load() -> str:
    """``absent`` when the board loads and no violation names a text."""
    bench, texts, report = texts_run()
    return _judged(bench, report, report is not None and any(named(report, kicad_uuid(t)) for t in texts))


@cache
def small_text_run() -> tuple[rb.Bench, Text, DrcReport | None]:
    small = text(1, "SMALL", Point(30 * MM, 12 * MM), "F.SilkS", size=500_000, thickness=60_000)
    bench = with_items(rb.builder().build(), texts=(small,))
    return bench, small, rb.drc(runner(), bench, RULES, major())


def text_height() -> str:
    """``present`` when a 0.5 mm silkscreen text with a 0.06 mm stroke gives both text findings."""
    bench, small, report = small_text_run()
    wanted = {"text_height", "text_thickness"}
    return _judged(bench, report, report is not None and named(report, kicad_uuid(small), *wanted) == wanted)


@cache
def copper_run(kind: str) -> tuple[rb.Bench, Entity, DrcReport | None]:
    """A copper text (``text``) or a copper line (``line``) across a track of net ``S1``."""
    made = rb.builder()
    made.single("track", "S1")
    y = made.tracks[-1].start.y
    item: Entity
    if kind == "text":
        item = text(1, "CU", Point(15 * MM, y), "F.Cu", size=2 * MM, thickness=300_000)
        bench = with_items(made.build(), texts=(item,))
    else:
        item = Graphic(
            id=_id("gfx", 1),
            kind="line",
            layer="F.Cu",
            points=(Point(15 * MM, y - 2 * MM), Point(15 * MM, y + 2 * MM)),
            width=200_000,
        )
        bench = with_items(made.build(), graphics=(item,))
    return bench, item, rb.drc(runner(), bench, RULES, major())


def text_copper_short() -> str:
    """``present`` when a copper text over a track gives ``shorting_items`` naming the track."""
    bench, _item, report = copper_run("text")
    (track,) = bench.uuids("track")
    return _judged(bench, report, report is not None and bool(named(report, track, "shorting_items")))


def graphic_copper_silent() -> str:
    """``absent`` when a copper line across a track is named by no violation and the track by no
    ``shorting_items`` or ``clearance``."""
    bench, item, report = copper_run("line")
    (track,) = bench.uuids("track")
    found = report is not None and bool(
        named(report, kicad_uuid(item)) or named(report, track, "shorting_items", "clearance")
    )
    return _judged(bench, report, found)


def dim_load() -> str:
    """``present`` when a board with the four dimensions loads (a DRC report with the canary)."""
    bench = with_items(rb.builder().build(), dimensions=dimensions())
    report = rb.drc(runner(), bench, RULES, major())
    return _judged(bench, report, True)


def _plot(board_text: str) -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(board_text, encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(rb.PROJECT, encoding="utf-8")
        args = ["pcb", "export", "svg", "--layers", "Dwgs.User", "--mode-single", "--exclude-drawing-sheet"]
        run = runner().run(
            [*args, "-o", "out.svg", board.name],
            files={board.name: board, "bench.kicad_pro": folder / "bench.kicad_pro"},
        )
    if not run.ok or "out.svg" not in run.outputs:
        return None
    return _SVG_NOISE.sub("", run.outputs["out.svg"].decode("utf-8"))


def wrong_cache(board_text: str) -> str:
    """The board text with the cache of its first dimension replaced: another value at another place."""
    right = '(gr_text "20.0000 mm"\n\t\t\t(at 20 10 0)'
    assert board_text.count(right) == 1, "the bench no longer writes the cache text this probe replaces"
    return board_text.replace(right, '(gr_text "99 mm"\n\t\t\t(at 20 1 0)')


def dim_recompute() -> str:
    """``equal`` when the ``Dwgs.User`` plots of the board and of its copy with a wrong cache text are
    the same: KiCad recomputes the text of a dimension on load."""
    written = write_board(dimensions_design(), target=major()).text
    first, second = _plot(written), _plot(wrong_cache(written))
    if first is None or second is None:
        return "inconclusive"
    return "equal" if first == second else "different"


def dim_resave() -> str:
    """``equal`` when ``pcb upgrade --force`` writes "20.0000 mm" and "25.50 mm" for the first two
    dimensions, starting from a wrong cache text for the first (10.0 only)."""
    written = wrong_cache(write_board(dimensions_design(), target=major()).text)
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "bench.kicad_pcb"
        board.write_text(written, encoding="utf-8")
        saved = runner().upgrade_board(board).decode("utf-8")
    read = read_board(saved, file="bench.kicad_pcb", issues=[])
    assert read.board is not None
    found = '"20.0000 mm"' in saved and '"25.50 mm"' in saved and '"99 mm"' not in saved
    return "equal" if found and len(read.board.dimensions) == 4 else "different"


Probes = dict[str, tuple[object, tuple[int, ...]]]


def item_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    return {
        "text-board-load": (text_load, both),
        "text-height": (text_height, both),
        "text-copper-short": (text_copper_short, both),
        "graphic-copper-silent": (graphic_copper_silent, both),
        "dim-load": (dim_load, both),
        "dim-recompute": (dim_recompute, both),
        "dim-resave-text": (dim_resave, (10,)),
    }


__all__ = [
    "JUSTIFY",
    "TEXT_LAYERS",
    "dim_load",
    "dim_recompute",
    "dim_resave",
    "dimensions",
    "dimensions_design",
    "graphic_copper_silent",
    "item_probes",
    "text_copper_short",
    "text_height",
    "text_load",
    "texts_bench",
    "wrong_cache",
]
