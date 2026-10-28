# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite silk --designators`` (change c0212; capability silkscreen-layout, "Designator placement" and
"Placed designators checked"), on the authored benches of ``tests/_silkbench.py``. Hermetic: the ink is
estimated (``--measure estimate``) and no subprocess may start.

The geometry the assertions use is written here again, apart from ``fenolite.silk``: the pads of ``CHIP``
turned by 90 degrees, and plain rectangle distances."""

from __future__ import annotations

import dataclasses
import io
import json
import subprocess
from math import isqrt
from pathlib import Path
from typing import Any

import pytest
from _silkbench import SilkBoard, mixed, row
from _ties import MM

import fenolite.backends.kicad.cli as kicad_cli
import fenolite.silk.board as silk_board
from fenolite.backends.kicad.fields import field_anchor, field_angle, set_field
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.cli import main as cli_main
from fenolite.cli._examples import EXAMPLE_SILK
from fenolite.cli.cmd_silk import text_floor
from fenolite.core.coords import Point
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.design import Design
from fenolite.silk.board import field_rect
from fenolite.silk.extents import TextKey, estimate
from fenolite.silk.layout import Choice, Rect

DEG = 1_000_000
CLEARANCE = 150_000
Box = tuple[int, int, int, int]


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _write(folder: Path, design: Design, name: str = "silk") -> Path:
    board = folder / f"{name}.kicad_pcb"
    board.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    project = synthesize_project(design, target=10, board_name=name)
    board.with_suffix(".kicad_pro").write_text(project, encoding="utf-8", newline="\n")
    return board


def silk(
    monkeypatch: pytest.MonkeyPatch, folder: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    monkeypatch.chdir(folder)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["silk", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")


def _read(path: Path) -> Design:
    return read_board(path.read_text(encoding="utf-8"), file=path.name)


def _reference(fp: FootprintInstance) -> FootprintField:
    return next(f for f in fp.fields if f.name == "Reference")


def _refs(design: Design) -> dict[str, FootprintInstance]:
    assert design.board is not None
    names = {c.id: c.ref for c in design.circuit.components}
    return {names[fp.component_id]: fp for fp in design.board.footprints}


def text_box(fp: FootprintInstance, ref: str) -> Box:
    """The ink of a footprint's designator on the board, from its field and the estimated ink."""
    field = _reference(fp)
    assert field.thickness is not None
    key = TextKey(ref, field.size.w, field.size.h, field.thickness, field.h_justify, field.v_justify)
    ink = estimate(key)
    assert ink is not None
    anchor = field_anchor(fp, field)
    rect = field_rect(ink, field_angle(fp, field), field.mirrored).moved(anchor.x, anchor.y)
    return rect.x0, rect.y0, rect.x1, rect.y1


def chip_pads(fp: FootprintInstance) -> list[Box]:
    """The two pads of ``CHIP`` at 0 or 90 degrees, written out: 0.9 mm x 1 mm at x = -0.8 and +0.8 mm."""
    x, y = fp.position.x, fp.position.y
    half_w, half_h = 450_000, 500_000
    if fp.rotation == 90 * DEG:  # local (x, y) lies at (y, -x) on the board
        return [(x - half_h, y + d - half_w, x + half_h, y + d + half_w) for d in (-800_000, 800_000)]
    assert fp.rotation == 0
    return [(x + d - half_w, y - half_h, x + d + half_w, y + half_h) for d in (-800_000, 800_000)]


def chip_box(fp: FootprintInstance) -> Box:
    """The courtyard box of ``CHIP`` (3 mm x 1.5 mm) at 0 or 90 degrees."""
    x, y = fp.position.x, fp.position.y
    hw, hh = (750_000, 1_500_000) if fp.rotation == 90 * DEG else (1_500_000, 750_000)
    return x - hw, y - hh, x + hw, y + hh


def distance(a: Box, b: Box) -> int:
    dx = max(0, a[0] - b[2], b[0] - a[2])
    dy = max(0, a[1] - b[3], b[1] - a[3])
    return isqrt(dx * dx + dy * dy)


def test_the_example_board_is_the_bench() -> None:
    """``EXAMPLE_SILK`` is ``row()`` as ``write_board`` writes it for KiCad 10."""
    assert Path(EXAMPLE_SILK).read_text(encoding="utf-8") == write_board(row(), target=10).text


def test_dense_row(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Dense row of resistors": ten parts at 1.6 mm; no designator meets a pad or another
    designator, each is nearer to its own part than to any other, and their edges facing the row line up."""
    board = _write(tmp_path, row())
    code, env, err = silk(
        monkeypatch, tmp_path, board.name, "--designators", "--measure", "estimate", "--confirm"
    )
    assert code == 0, err
    result = env["result"]
    assert result["placed"] == 10 and result["unplaced"] == 0 and result["changed"] is True
    assert result["aligned"] == [[f"R{n}" for n in range(1, 11)]]
    assert [found["code"] for found in env["issues"]] == ["silk.estimated"]
    assert env["evidence"] == {
        "level": "INFERRED",
        "oracle": None,
        "hypotheses": ["H-K-SILK-DRC", "H-K-SILK-ESTIMATE"],
    }
    parts = _refs(_read(board))
    texts = {ref: text_box(fp, ref) for ref, fp in parts.items()}
    pads = [pad for fp in parts.values() for pad in chip_pads(fp)]
    for ref, box in texts.items():
        assert all(distance(box, pad) >= CLEARANCE for pad in pads), ref
        assert all(distance(box, other) >= CLEARANCE for name, other in texts.items() if name != ref), ref
        own = distance(box, chip_box(parts[ref]))
        assert all(own < distance(box, chip_box(fp)) for name, fp in parts.items() if name != ref), ref
        field = _reference(parts[ref])
        assert field_angle(parts[ref], field) == 90 * DEG and field.size.h == MM
        assert (field.h_justify, field.v_justify, field.mirrored) == ("center", "center", False)
    assert len({box[3] for box in texts.values()}) == 1  # one line faces the row
    code, env, _ = silk(
        monkeypatch, tmp_path, board.name, "--designators", "--measure", "estimate", "--dry-run"
    )
    assert code == 0 and env["result"]["placed"] == 10


def test_both_sides_and_turned_parts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Top and bottom parts at 0, 90 and 30 degrees: each designator lands on its side's silkscreen, reads at
    0 or 90 degrees, is mirrored on the bottom only, stays inside the board, and clears the hole."""
    board = _write(tmp_path, mixed())
    code, env, err = silk(
        monkeypatch, tmp_path, board.name, "--designators", "--measure", "estimate", "--confirm"
    )
    assert code == 0, err
    assert env["result"]["placed"] == 7
    parts = _refs(_read(board))
    hole = parts["H1"]
    hole_box = (
        hole.position.x - 1_500_000,
        hole.position.y - 1_500_000,
        hole.position.x + 1_500_000,
        hole.position.y + 1_500_000,
    )
    for ref, fp in parts.items():
        field = _reference(fp)
        assert field.layer == ("F.SilkS" if fp.side == "top" else "B.SilkS"), ref
        assert field.mirrored is (fp.side == "bottom"), ref
        assert field_angle(fp, field) in (0, 90 * DEG), ref
        box = text_box(fp, ref)
        assert CLEARANCE <= box[0] and box[2] <= 40 * MM - CLEARANCE, ref
        assert CLEARANCE <= box[1] and box[3] <= 30 * MM - CLEARANCE, ref
        assert distance(box, hole_box) >= CLEARANCE, ref


def test_keep_moves_only_blocked_texts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--keep``: after a first placement, the designator of ``R3`` is put back on its pads; a second run
    moves it alone."""
    board = _write(tmp_path, row())
    code, _, err = silk(
        monkeypatch, tmp_path, board.name, "--designators", "--measure", "estimate", "--confirm"
    )
    assert code == 0, err
    design = _read(board)
    assert design.board is not None
    before = _refs(design)
    moved = set_field(before["R3"], "Reference", anchor=before["R3"].position, angle=0)
    footprints = tuple(moved if fp.id == moved.id else fp for fp in design.board.footprints)
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))
    board.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    code, env, err = silk(
        monkeypatch, tmp_path, board.name, "--designators", "--keep", "--measure", "estimate", "--confirm"
    )
    assert code == 0, err
    rows = {row_["ref"]: row_["status"] for row_ in env["result"]["placements"]}
    assert rows["R3"] == "placed" and all(status == "kept" for ref, status in rows.items() if ref != "R3")
    after = _refs(_read(board))
    for ref in before:
        if ref != "R3":
            assert _reference(after[ref]).position == _reference(before[ref]).position, ref
    assert text_box(after["R3"], "R3") != text_box(moved, "R3")


def test_refs_leave_the_others_in_the_way(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--refs R1``: only ``R1`` moves; the designators of the others stay over their pads and ``R1``'s new
    place keeps clear of them."""
    board = _write(tmp_path, row(3))
    code, env, err = silk(
        monkeypatch,
        tmp_path,
        board.name,
        "--designators",
        "--refs",
        "R1",
        "--measure",
        "estimate",
        "--confirm",
    )
    assert code == 0, err
    assert [r["ref"] for r in env["result"]["placements"]] == ["R1"]
    parts = _refs(_read(board))
    assert _reference(parts["R2"]).position == Point(0, 0)
    r1 = text_box(parts["R1"], "R1")
    assert distance(r1, text_box(parts["R2"], "R2")) >= CLEARANCE


def test_no_room(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A part whose outline leaves no room beside it: ``silk.no-place``, nothing written."""
    bench = SilkBoard(width=5 * MM, height=3500 * MM // 1000)
    bench.place("R1", Point(2500 * MM // 1000, 1750 * MM // 1000))
    design = bench.build()
    board = _write(tmp_path, design)
    before = board.read_bytes()
    code, env, err = silk(
        monkeypatch, tmp_path, board.name, "--designators", "--measure", "estimate", "--confirm"
    )
    assert code == 0, err
    (found,) = [i for i in env["issues"] if i["code"] == "silk.no-place"]
    assert found["severity"] == "warning" and found["where"] == "R1"
    assert env["result"]["unplaced"] == 1 and env["result"]["changed"] is False
    assert board.read_bytes() == before


def test_a_failed_check_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A place that the search should never give (``R1`` on its own pads) is caught by the check:
    ``silk.check-failed``, exit 5, nothing written."""
    board = _write(tmp_path, row(2))
    before = board.read_bytes()
    real = silk_board.arrange

    def wrong(*args: Any, **kwargs: Any) -> Any:
        plan = real(*args, **kwargs)
        key, choice = next(iter(plan.placed.items()))
        parts = args[0]
        part = next(p for p in parts if p.key == key)
        centre = Point((part.box.x0 + part.box.x1) // 2, (part.box.y0 + part.box.y1) // 2)
        rect: Rect = choice.look.ink.moved(centre.x, centre.y)
        plan.placed[key] = Choice(centre, choice.look, rect, 0, choice.slot)
        return plan

    monkeypatch.setattr(silk_board, "arrange", wrong)
    code, env, _ = silk(
        monkeypatch, tmp_path, board.name, "--designators", "--measure", "estimate", "--confirm"
    )
    assert code == 5
    codes = {i["code"] for i in env["issues"]}
    assert "silk.check-failed" in codes and env["result"]["changed"] is False
    assert board.read_bytes() == before


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--designators", "--angles", "45"),
        ("--designators", "--sizes", "0.5mm"),
        ("--designators", "--clearance", "1"),
        ("--designators", "--out", str(Path("/abs.kicad_pcb").resolve())),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    board = _write(tmp_path, row(2))
    code, _, err = silk(monkeypatch, tmp_path, board.name, *args, "--measure", "estimate", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_text_floor_from_the_project(tmp_path: Path) -> None:
    """The least text height and stroke come from the project's rules, else KiCad's defaults."""
    project = tmp_path / "p.kicad_pro"
    data = json.loads(synthesize_project(row(1), target=10, board_name="p"))
    data["board"]["design_settings"]["rules"]["min_text_height"] = 1.0
    data["board"]["design_settings"]["rules"]["min_text_thickness"] = 0.12
    project.write_text(json.dumps(data), encoding="utf-8")
    assert text_floor(project) == (1_000_000, 120_000)
    assert text_floor(None) == (800_000, 80_000)
    project.write_text("{}", encoding="utf-8")
    assert text_floor(project) == (800_000, 80_000)


def test_sizes_and_angles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--sizes 1.2mm`` and ``--angles 0`` are the only looks tried; the stroke keeps the field's ratio."""
    board = _write(tmp_path, mixed(("top",)))
    code, env, err = silk(
        monkeypatch,
        tmp_path,
        board.name,
        "--designators",
        "--sizes",
        "1.2mm",
        "--angles",
        "0",
        "--measure",
        "estimate",
        "--dry-run",
    )
    assert code == 0, err
    rows = env["result"]["placements"]
    assert {(r["angle"], r["height"], r["stroke"]) for r in rows} == {(0, 1_200_000, 180_000)}
    assert env["result"]["settings"]["sizes"] == [1_200_000] and env["result"]["settings"]["angles"] == [0]


def _hide_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    empty = tmp_path / "empty-path"
    empty.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv("FENOLITE_KICAD_CLI", raising=False)
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", tmp_path / "missing" / "kicad-cli")
    monkeypatch.setattr(kicad_cli, "windows_kicad_clis", lambda: ())


def test_without_a_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``auto`` without a tool estimates; ``kicad`` and ``--drc`` without one exit 6."""
    _hide_kicad(monkeypatch, tmp_path)
    board = _write(tmp_path, row(2))
    code, env, err = silk(monkeypatch, tmp_path, board.name, "--designators", "--dry-run")
    assert code == 0, err
    assert env["result"]["measure"]["source"] == "estimate"
    assert "silk.estimated" in {i["code"] for i in env["issues"]}
    for extra in (("--measure", "kicad"), ("--drc",)):
        code, _, err = silk(monkeypatch, tmp_path, board.name, "--designators", *extra, "--dry-run")
        assert code == 6 and err["code"] == "FEN-6001"
