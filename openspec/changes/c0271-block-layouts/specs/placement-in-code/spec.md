## ADDED Requirements

### Requirement: Mirrored block poses
`inst.place(..., side="bottom")` SHALL mirror the instance in its block frame before its pose's turn and translation: each child's position `(x, y)` becomes `(−x, y)`, its side is flipped and its rotation is the one the model's footprint flip gives. Each pad of a mirrored instance MUST be the mirror image, about the pose's vertical axis, of the same pad of a top instance with the same pose, within 1 nm.

#### Scenario: The same block on both sides
- **GIVEN** two instances of the authored divider with one layout, `a.place(mm(10), mm(8))` and `b.place(mm(10), mm(8), side="bottom")`
- **WHEN** `uv run pytest tests/unit/placement/test_relative.py -k mirrored` resolves them
- **THEN** every part of `b` is on the bottom, and each of its pads lies within 1 nm of the mirror about x = 10 mm of the same pad of `a`

### Requirement: Mirrored copper and rigid flips
Copper placed by a mirrored pose SHALL map each layer to its mirror in the stack. When the side of a block's pose differs from the side recorded by the previous build, kept children MUST be moved by the new pose composed with the inverse of the old one, mirror included, with their copper on mirrored layers, and the build MUST give `layout.block-moved`.

#### Scenario: A laid-out block flipped in code
- **GIVEN** a confirmed build of `a` with its layout copper, after which the script adds `side="bottom"` to `a.place(...)`
- **WHEN** the build runs again with `--confirm`
- **THEN** every part of `a` is on the bottom at its mirrored position, its tracks are on `B.Cu`, `issues` hold one `layout.block-moved` naming `a`, and the copper check finds nothing new
