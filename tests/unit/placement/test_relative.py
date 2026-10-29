# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The resolution of relative requests, block poses and frame strategies (change c0255; capability
placement-in-code, "Relative placement resolution", "Measuring boxes", "Resolution order", "Unresolved
references", "Block poses applied" and "Strategy groups without a pose")."""

from __future__ import annotations

from collections.abc import Mapping

from fenolite.core.coords import Point
from fenolite.dsl import Design, block, mm, row
from fenolite.dsl.convert import BOARD_ORIGIN
from fenolite.dsl.relative import block_layouts, frames, relative_requests, top_layout, turns
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import Transform
from fenolite.placement.relative import Absolute, Footprint, PadBox, Placed, Resolution, Scene, resolve

MM = 1_000_000
ORIGIN = BOARD_ORIGIN
CHIP = Footprint(
    BBox(-2 * MM, -MM, 2 * MM, MM),
    (
        PadBox("1", Point(-MM, 0), BBox(-1_500_000, -600_000, -500_000, 600_000)),
        PadBox("2", Point(MM, 0), BBox(500_000, -600_000, 1_500_000, 600_000)),
    ),
)
"""A 4 mm × 2 mm part with two 1 mm × 1.2 mm pads 2 mm apart, authored for these tests."""
WIDE = Footprint(BBox(-3 * MM, -MM, 3 * MM, MM), (PadBox("1", Point(0, 0), BBox(-MM, -MM, MM, MM)),))


def _design() -> Design:
    design = Design("rel")
    design.board(mm(40), mm(30))
    return design


def _part(container, ref: str):  # type: ignore[no-untyped-def]
    return container.part(ref, "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")


def _scene(design: Design, footprints: Mapping[str, Footprint] | None = None) -> Scene:
    absolute = {
        path: Absolute(p.request.x, p.request.y, p.request.rotation, p.request.side, p.request.locked)
        for path, p in design.parts.items()
        if p.request is not None
    }
    feet = {path: (footprints or {}).get(path, CHIP) for path in design.parts}
    return Scene(
        footprints=feet,
        frames={key: items.items for key, items in frames(design).items()},
        absolute=absolute,
        relative=relative_requests(design),
        turns=turns(design),
        blocks=block_layouts(design),
        origin=ORIGIN,
        top=top_layout(design),
        board=BBox(ORIGIN.x, ORIGIN.y, ORIGIN.x + 40 * MM, ORIGIN.y + 30 * MM),
        staging=Point(ORIGIN.x + 45 * MM, ORIGIN.y),
    )


def _box(resolution: Resolution, path: str, footprint: Footprint = CHIP, pad: str | None = None) -> BBox:
    placed = resolution.placements[path]
    transform = Transform.placement(placed.at, placed.rotation, placed.side == "bottom")
    if pad is not None:
        found = next(p for p in footprint.pads if p.number == pad)
        return transform.apply_bbox(found.box)
    return transform.apply_bbox(footprint.extent)


def test_a_capacitor_by_its_pad() -> None:
    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    u1.place(mm(14), mm(15))
    c5.place(right_of=u1.pad(2), gap=mm("0.5"), by=c5.pad(1))
    resolution = resolve(_scene(design))
    assert not resolution.issues
    assert _box(resolution, "C5", pad="1").x0 == _box(resolution, "U1", pad="2").x1 + 500_000
    assert resolution.placements["C5"].at.y == resolution.placements["U1"].at.y
    (record,) = resolution.records
    assert record.request == "right_of=U1.pad(2) gap=0.5mm by=pad(1)"
    assert record.refs[0].ref == "U1.pad(2)" and record.at == resolution.placements["C5"].at


def test_turned_part() -> None:
    design = _design()
    mcu, sen = _part(design, "MCU"), _part(design, "SEN")
    mcu.place(mm(10), mm(10))
    sen.place(right_of=mcu, gap=mm(3), rot=90)
    resolution = resolve(_scene(design, {"SEN": WIDE}))
    turned = _box(resolution, "SEN", WIDE)
    assert turned.width == 2 * MM and turned.height == 6 * MM
    assert turned.x0 == _box(resolution, "MCU").x1 + 3 * MM
    assert (turned.y0 + turned.y1) // 2 == (_box(resolution, "MCU").y0 + _box(resolution, "MCU").y1) // 2


def test_non_quarter_turn_rounds_outward() -> None:
    design = _design()
    mcu, sen = _part(design, "MCU"), _part(design, "SEN")
    mcu.place(mm(10), mm(10))
    sen.place(right_of=mcu, gap=mm(1), rot=30)
    resolution = resolve(_scene(design))
    assert _box(resolution, "SEN").x0 == _box(resolution, "MCU").x1 + MM


def test_edges_and_alignment() -> None:
    design = Design("edges")
    board = design.board(mm(40), mm(30))
    j1, r1, r2 = _part(design, "J1"), _part(design, "R1"), _part(design, "R2")
    j1.place(left=board.left + mm(2), center_y=board.center_y)
    r1.place(below=j1, gap=mm(1), align="start")
    r2.place(above=j1, align="end")
    resolution = resolve(_scene(design))
    box = _box(resolution, "J1")
    assert box.x0 == ORIGIN.x + 2 * MM and (box.y0 + box.y1) // 2 == ORIGIN.y + 15 * MM
    assert _box(resolution, "R1").y0 == box.y1 + MM and _box(resolution, "R1").x0 == box.x0
    assert _box(resolution, "R2").y1 == box.y0 and _box(resolution, "R2").x1 == box.x1


def test_topological_order_whatever_the_paths() -> None:
    design = _design()
    a, b, c = _part(design, "A"), _part(design, "B"), _part(design, "C")
    c.place(mm(5), mm(5))
    b.place(right_of=c)
    a.place(right_of=b)
    resolution = resolve(_scene(design))
    assert _box(resolution, "A").x0 == _box(resolution, "B").x1 == _box(resolution, "C").x1 + 4 * MM


def test_a_cycle() -> None:
    design = _design()
    a, b = _part(design, "A"), _part(design, "B")
    a.place(right_of=b)
    b.place(right_of=a)
    resolution = resolve(_scene(design))
    assert [(i.code, i.severity, i.where) for i in resolution.issues] == [
        ("layout.relative-cycle", "error", "A, B")
    ]
    assert "A" not in resolution.placements and "B" not in resolution.placements


def test_reference_left_in_staging() -> None:
    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    c5.place(right_of=u1)
    resolution = resolve(_scene(design))
    (found,) = resolution.issues
    assert (found.code, found.severity) == ("layout.relative-unresolved", "warning")
    assert "C5" in found.where and "U1" in found.where
    assert not resolution.placements


def test_pose_a_block_moved_and_turned() -> None:
    design = _design()

    @block
    def buck(b):  # type: ignore[no-untyped-def]
        u = _part(b, "U")
        u.place(mm(0), mm(0))
        _part(b, "L").place(right_of=u, gap=mm(1))

    p1 = design.use(buck, "buck1")
    p1.place(mm(10), mm(8), rot=90)
    resolution = resolve(_scene(design))
    u, inductor = resolution.placements["buck1/U"], resolution.placements["buck1/L"]
    assert u.at == Point(ORIGIN.x + 10 * MM, ORIGIN.y + 8 * MM)
    assert u.rotation == inductor.rotation == 90_000_000
    assert _box(resolution, "buck1/L").y1 + MM == _box(resolution, "buck1/U").y0
    assert resolution.blocks["buck1"].at == u.at and resolution.blocks["buck1"].rotation == 90_000_000


def test_pose_relative_to_a_block_and_nested_blocks() -> None:
    design = _design()

    @block
    def inner(b):  # type: ignore[no-untyped-def]
        _part(b, "R").place(mm(0), mm(0))

    @block
    def outer(b):  # type: ignore[no-untyped-def]
        first = b.use(inner, "i1")
        first.place(mm(1), mm(1))
        second = b.use(inner, "i2")
        second.place(right_of=first, gap=mm(1))

    p1 = design.use(outer, "o1")
    p1.place(mm(5), mm(5))
    p2 = design.use(outer, "o2")
    p2.place(below=p1, gap=mm(2), align="start")
    resolution = resolve(_scene(design))
    assert resolution.placements["o1/i1/R"].at == Point(ORIGIN.x + 6 * MM, ORIGIN.y + 6 * MM)
    assert _box(resolution, "o1/i2/R").x0 == _box(resolution, "o1/i1/R").x1 + MM
    assert _box(resolution, "o2/i1/R").y0 == _box(resolution, "o1/i1/R").y1 + 2 * MM
    assert _box(resolution, "o2/i1/R").x0 == _box(resolution, "o1/i1/R").x0


def test_a_block_without_pose_keeps_board_coordinates() -> None:
    design = _design()

    @block
    def plain(b):  # type: ignore[no-untyped-def]
        _part(b, "R").place(mm(7), mm(9))
        _part(b, "C").place(right_of=b.children[0])

    design.use(plain, "p")
    resolution = resolve(_scene(design))
    assert resolution.placements["p/R"].at == Point(ORIGIN.x + 7 * MM, ORIGIN.y + 9 * MM)


def test_a_request_wins_over_the_strategy() -> None:
    design = _design()

    @block
    def grouped(b):  # type: ignore[no-untyped-def]
        r1 = _part(b, "R1")
        _part(b, "C1").place(below=r1)
        _part(b, "R2")
        b.layout(row(gap=mm(1)))

    design.use(grouped, "g").place(mm(0), mm(0))
    resolution = resolve(_scene(design))
    r1, r2, c1 = (_box(resolution, f"g/{k}") for k in ("R1", "R2", "C1"))
    assert r1.x0 == ORIGIN.x and r2.x0 == r1.x1 + MM and c1.y0 == r1.y1 and c1.x0 == r1.x0
    assert (
        resolution.placements["g/R1"].source == "strategy"
        and resolution.placements["g/C1"].source == "relative"
    )


def test_a_group_stays_together() -> None:
    design = _design()

    @block
    def grouped(b):  # type: ignore[no-untyped-def]
        for name in ("R1", "R2", "R3"):
            _part(b, name)
        b.layout(row())

    design.use(grouped, "g")
    resolution = resolve(_scene(design))
    boxes = [_box(resolution, f"g/R{i}") for i in (1, 2, 3)]
    assert boxes[0].x0 == ORIGIN.x + 45 * MM and {b.y0 for b in boxes} == {ORIGIN.y}
    assert boxes[1].x0 == boxes[0].x1 and boxes[2].x0 == boxes[1].x1
    assert all(resolution.placements[f"g/R{i}"].staged for i in (1, 2, 3))
    assert resolution.staging_end == boxes[2].x1 + 2 * MM and resolution.blocks["g"].staged


def test_a_turn_with_a_strategy() -> None:
    design = _design()
    design.layout(row(at=(mm(1), mm(1))))
    _part(design, "R1").place(rot=90)
    resolution = resolve(_scene(design))
    assert resolution.placements["R1"].rotation == 90_000_000
    assert _box(resolution, "R1").x0 == ORIGIN.x + MM and _box(resolution, "R1").y0 == ORIGIN.y + MM


def test_fixed_reference_is_followed() -> None:
    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    u1.place(mm(14), mm(15))
    c5.place(right_of=u1, gap=mm(1))
    moved = Placed(Point(ORIGIN.x + 20 * MM, ORIGIN.y + 5 * MM), 0, "top")
    resolution = resolve(_scene(design), {"U1": moved})
    assert resolution.placements["U1"].at == Point(ORIGIN.x + 14 * MM, ORIGIN.y + 15 * MM)
    assert resolution.placements["C5"].at == Point(ORIGIN.x + 25 * MM, ORIGIN.y + 5 * MM)


def test_reuse_places_by_local_path() -> None:
    design = _design()

    @block
    def reused(b):  # type: ignore[no-untyped-def]
        _part(b, "U")
        _part(b, "L")
        _part(b, "X")
        b.layout(reuse="buck.kicad_pcb")

    design.use(reused, "r").place(mm(20), mm(5))
    scene = _scene(design)
    scene = Scene(
        **{
            **{name: getattr(scene, name) for name in scene.__dataclass_fields__},
            "reuse": {
                "r": {"U": Placed(Point(0, 0), 0, "top"), "L": Placed(Point(5 * MM, 0), 90_000_000, "top")}
            },
        }
    )
    resolution = resolve(scene)
    assert resolution.placements["r/U"].at == Point(ORIGIN.x + 20 * MM, ORIGIN.y + 5 * MM)
    assert resolution.placements["r/L"].at == Point(ORIGIN.x + 25 * MM, ORIGIN.y + 5 * MM)
    assert resolution.placements["r/L"].source == "reuse" and resolution.missing == (("r", "X"),)


def test_equal_inputs_equal_records() -> None:
    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    u1.place(mm(14), mm(15))
    c5.place(right_of=u1, gap=mm(1))
    first, second = resolve(_scene(design)), resolve(_scene(design))
    assert first.placements == second.placements and first.records == second.records
    assert first.digest() == second.digest()


def test_a_strategy_beyond_the_outline() -> None:
    design = _design()
    design.layout(row(at=(mm(30), mm(1))))
    for name in ("R1", "R2", "R3"):
        _part(design, name)
    resolution = resolve(_scene(design))
    (found,) = resolution.issues
    assert (found.code, found.severity, found.where) == ("layout.strategy-overflow", "warning", "top")
    assert found.message.endswith("puts R3 beyond the outline")
