# c0423 design

## Decision 1: KiCad's model pose, measured (`H-K-MODEL-POSE`)

**Probe.** Each probe board holds one footprint at (20, 15) mm. Its model is an authored STEP prism with six
distinct vertices: the triangle (0, 0), (3, 0), (0, 1) mm, from 0.5 mm to 2.5 mm. The cases cover:

- the top and the bottom side;
- a footprint angle of 0° and 25°;
- offset (0, 0, 0) and (1, 2, 3);
- `rotate` (0,0,0), (30,0,0), (0,40,0), (0,0,50), (30,40,50), (90,0,90) and (0,90,90).

That gives 56 boards. `kicad-cli pcb export stl --user-origin 0x0mm` writes the vertices in a frame with X
right, Y up (the board's −y) and Z up. The 10.0.6 runs add `--no-board-body`. On 9.0.9 that option makes the
export fail ("No valid PCB assembly"), so those runs keep the board body and drop its eight corners.

**Result.** Every hypothesis tried: 6 orders of the three turns, 8 sign choices, a flip about X or Y, and
the sign of the footprint angle. One fits all 56 cases on both majors, every vertex within 1 µm:

```
p_board = T(x, −y, face) · Rz(θ) · F · (Rz(−c) · Ry(−b) · Rx(−a) · p + o)
```

- `(a, b, c)` are the `rotate` values: the turn about X is applied first, then Y, then Z, each clockwise
  seen from its positive axis (by −a, −b, −c).
- `o` is the `offset`, Y up, added after the turns and before the flip.
- `F` is the identity on the top and a half turn about X on the bottom: `(x, y, z) → (x, −y, −z)`.
- `θ` is the footprint's angle as written (counter-clockwise in a Y-up view) on both sides.
- `face` is where KiCad seats models: 0.085 mm beyond the 1.51 mm board body on each side, for a board
  of 1.6 mm. A model's Z is measured from its face, as Altium's is.

The 2026-10-28 row `H-K-MODEL-PLACE` is the Z-only case of this. Fenolite's `ModelPlacement` holds the
negated file angles and Y down, as today (`_fpmap.placement_node`). KiCad therefore applies
`Rz(rz) · Ry(ry) · Rx(rx)` with the placement's own counter-clockwise angles, which is the order of
Altium's `Rz · Ry · Rx`.

## Decision 2: the solve

The source pose of a model is `BodyModel`'s (`H-A-BODY-MODEL-PLACE`):
`T(position, face) · F · (R_A · p + (0, 0, z))`, with `R_A = Rz(rz) · Ry(ry) · Rx(rx)` in the same Y-up
frame. Equating it with KiCad's pose for every `p` gives the following, with `F` self-inverse:

```
R_K = F · Rz(−θ) · F · R_A          (top: Rz(−θ)·R_A; bottom: Rz(θ)·R_A)
o   = F · Rz(−θ) · (Δx, Δy, 0) + (0, 0, z)
```

Here `Δ` is the model position less the footprint's, in Y up. `R_K` is decomposed as `Rz(γ) · Ry(β) · Rx(α)`:

- `β = atan2(−r20, √(r00² + r10²))`, `α = atan2(r21, r22)`, `γ = atan2(r10, r00)`;
- when `cos β` is below 1e−9, `α = 0` and `γ = atan2(−r01, r11)`.

The placement is `rotation = (α, β, γ)` in µdeg, each brought into (−180°, 180°] and rounded half to even.
The offset is in nm with Y down. On the top with no turn about X or Y, this gives the offset and angle of
c0223 to the nanometre and the µdeg, so those placements keep their bytes.

## Decision 3: bodies become model files

KiCad has no body. A body reaches KiCad as a model file, or it is a loss:

| body | written as | report (`body`) |
|---|---|---|
| kind `model`, its model placed | nothing more: the model carries it | changed, "carried by its embedded model" |
| kind `model`, no embedded data | the prism over its outline | changed, the prism reason |
| `MODEL.MODELTYPE` 0 or absent | the prism over its outline | changed, "written as a generated STEP model" |
| type 2, square outline, no turn about X or Y | a cylinder: centre and diameter from the outline's box, from standoff to overall | changed, same |
| type 3, square outline whose side equals the height span | a sphere: centre at the box centre and mid-height, radius half the span | changed, same |
| type 2 or 3 that does not fit | the prism over its outline (it holds the shape) | changed, "written as the prism over its outline" |
| `projection_unknown`, no `z_min`/`z_max`, fewer than three outline points or no area | nothing | lost, with the reason |

- **Model frame.** On the top the file is the outline with Y up, as `backends.step` already writes it.
  On the bottom the outline is given with Y mirrored, so that after KiCad's flip `F` the body lies where the
  source puts it. Both are placed with offset 0 and rotation 0: a pad-frame point `p` lies at
  `position + R(θ)·p` (`FootprintInstance`), which is KiCad's transform with `o = 0` and `R_K = I` on either
  side.
- **The model type** comes from the record, as `models3d.body_forms` reads it beside `body_models`: one
  read of the document, keyed by the body's locator. The model and its ids do not change.
- **Facets.** The number of sides `n` is the smallest that keeps the sagitta `r·(1 − cos(π/n))` at 10 µm
  or less, at least 24 and at most 96. A sphere has `n` meridians and `n/2` bands. Its quadrilaterals are
  isosceles trapezoids, so they are planar before nm rounding, and they stay within the file's
  0.0001 mm accuracy after it. A cylinder is a prism over the regular `n`-gon.
- **Files** are `model_file(library, footprint, bytes)`: the same folder and naming as extracted models, so
  equal bytes share one file.

## Decision 4: the files the board names, and the import

- The kept model files are every file that a written library footprint **or the board** names. Today only
  the library counts, so a model of a second instance whose library footprint came from the first instance
  is left out.
- `body` and `model` join `convert.WARNED_LOSSES`. A remaining loss gives a `convert.lossy` warning in
  `convert` and in `import`, which keeps the conversion's issues (c0409).
- The import already derives its library from the converted board and writes the model files the
  footprints name (c0409, B9). With every model placed, it holds every model reference of the conversion.

## Risks

- **Altium's bottom flip.** That flip is about X by c0193's box comparison, which also fit about Y for 151
  of 181 bodies. A box cannot tell the two apart for symmetric parts. This change uses the row as
  measured. An Altium-side check of an asymmetric bottom model is a follow-up for the Altium round queue.
- **Sizes.** A large sphere can have up to 4 608 faces. The cap keeps each such file under a few MB.
