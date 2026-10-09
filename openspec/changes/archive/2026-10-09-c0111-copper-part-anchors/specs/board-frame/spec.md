## ADDED Requirements

### Requirement: Anchor points in a part's frame
`part_frame(design, component, *, number=None, index=None) -> PartFrame` SHALL return the map from the library frame of the footprint of `component` to the board frame, and `PartFrame.point(offset=Point(0, 0)) -> Point` SHALL return the board point of an offset in that frame, measured from the footprint's origin, or from the position of the pad that `number` and `index` name.
- In addition to the public names of "Board-frame module", `frame.py` MUST export `PartFrame` and `part_frame`, and `fenolite.backends.kicad` MUST re-export `part_frame`. Both are pure, as every function of the module is. `PartFrame` is a frozen dataclass with `footprint_id`, `at`, `rotation`, `side`, `base` and `pad_ids`.
- `component` MUST match as in `find_pads`: component paths first, references when no path matches. `at`, `rotation` and `side` MUST be the matched footprint's.
- Without `number`, `base` MUST be (0, 0) and `pad_ids` empty. With `number` (an `int` read as its decimal text), the pads named are those `find_pads` returns: with `index`, the `index`-th of them; without it, all of them, which MUST lie at one `position`. `pad_ids` MUST be the ids of the pads named, and `base` the stored position of the first, mirrored about local X when the footprint is on the bottom side: its position in the library footprint (`H-G-BOTTOM-STORE`).
- `point(d)` MUST be `Transform.placement(at, rotation, mirror=side == "bottom").apply(base + d)`: the offset turned as `H-G-ROT-DIR` turns a footprint's children, mirrored about local X on the bottom side, and rounded half to even once. So `part_frame(design, c, number=n, index=i).point()` MUST equal the `position` of that pad's `BoardPad`, and `part_frame(design, c).point(p)` MUST equal it too when `p` is the pad's position in the library footprint.
- `part_frame` MUST raise `KeyError` when no footprint matches or no pad has the number, with the messages of `find_pads`, and when `index` is beyond the pads of the number, naming the component, the number, the index and the count; and `ValueError`, naming the component, the number and the count, when the pads of the number lie at more than one position and no `index` is given.

#### Scenario: Part and pad points on both sides
- **GIVEN** the two designs of "Bottom footprint": `Mini_QFP-32_7x7mm_P0.8mm` placed for `U1` at (50 mm, 50 mm) at 0° on the bottom, and on the top
- **WHEN** `part_frame(design, "U1", number="1").point()` and `part_frame(design, "U1").point(Point(-4_150_000, -2_800_000))` are called on each
- **THEN** both calls return (45.85 mm, 52.8 mm) on the bottom design and (45.85 mm, 47.2 mm) on the top one, the positions of the two records of pad `1`

#### Scenario: An offset turns and mirrors with the part
- **GIVEN** `Frame_Anchor` placed for `U1` at (20 mm, 20 mm) at 90°, once on the top and once on the bottom; pad `4` lies at (1 mm, 0) in the library footprint, and its record is at (20 mm, 19 mm) in both designs
- **WHEN** `part_frame(design, "U1", number="4").point(Point(0, 1_000_000))` is called on each
- **THEN** it returns (21 mm, 19 mm) on the top and (19 mm, 19 mm) on the bottom

#### Scenario: Every pad at every angle
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_frame_anchor.py -k every_pad` places `Mini_QFP-32_7x7mm_P0.8mm` and `Frame_Anchor` with `place_footprint` at 0°, 90°, 180°, 270°, 30° and 45° on both sides
- **THEN** for every pad, `part_frame(…, number=n, index=k).point()` and `part_frame(…).point(<the pad's library position>)` equal its `BoardPad.position` to the nanometre

#### Scenario: Pads of one number at two positions
- **GIVEN** the design of "Pads sharing a number" (`Mini_Edge_Cases` for `J1`)
- **WHEN** `part_frame(design, "J1", number=1)` and `part_frame(design, "J1", number=1, index=1).point()` are called
- **THEN** the first raises `ValueError` naming `J1`, `1` and the count 2, and the second returns (2 mm, 0)

#### Scenario: Unknown part
- **GIVEN** the design of "The 270° case"
- **WHEN** `part_frame(design, "R9")` and `part_frame(design, "R1", number=1, index=1)` are called
- **THEN** each raises `KeyError`, the first naming `R9`, the second naming `R1` and the index
