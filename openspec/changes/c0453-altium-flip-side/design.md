# Design

## Altium's frame of a bottom part

Let `L` be a pad's place in the footprint, `o` the component origin and `R` its `ROTATION`. A top part puts
the pad at `o + rot(R)·L`, and a bottom part at `o + rot(R)·mirrorY(L)`. The census (S-2121) checks this on
every bottom part of the public documents whose pattern is also placed on the top, comparing pad by pad. It
counts 235 parts, 0 mirrored in X, and 3 that fit neither form. A pad's rotation `r` is `R + l` on the top
and `R − l` on the bottom.

## The flip

The session flips in place about the component origin: `x → 2·ox − x`. For a top part, `mirrorX · rot(R) =
rot(180 − R) · mirrorY`, so the bottom frame that describes the mirrored primitives has `ROTATION` 180 − R.
A pad at `R + l` must then read `(180 − R) − l = 180 − r`. The geometry of the mirrored pad is the shape at
`−r`, the same shape for every pad shape that is symmetric under a half turn, which every pad record's shape
is. From the bottom the same algebra gives `180 − R` again, so a flip back restores the record.

Altium's own flip of `D1` in J9 (S-2122) mirrors about the middle of the part, not about its origin, and
writes `ROTATION` 180 and pad rotations 180, from 0 and 0: the same frame rule. Fenolite keeps the origin.
The place differs, and the frame agrees.

Texts keep `−t` and toggle their mirror flag. Altium's J9 save holds rotation 0 for both texts, which is
what `−t` gives. Arcs keep `180 − end, 180 − start`. Tracks have no angle. Fills keep `−a`. A fill record is
a rectangle, for which `−a` and `180 − a` are the same shape. No public evidence sets a fill's angle apart.

## Bodies

`BODYPROJECTION` follows the side: 1 on every body of a bottom part and 0 on every top body in the eight
documents (S-2121). The flip toggles it. The body's layer already moves by the declared mechanical pairs
(c0430).

`MODEL.3D.ROTX`, `ROTY` and `DZ` agree for the same model on both sides. `MODEL.3D.ROTZ − R` agrees on 540
of the 846 pairs of row -08 and differs by 180 on 306 (rotation-symmetric models and turns per placement).
The flip therefore keeps `ROTZ − R`, and keeps `MODEL.2D.ROTATION − R`, which row -08 pairs in the same way.
The rule is INFERRED until the kit run shows Altium's own flip of a body.

## Kit

The VM agent runs the files in `~/fenolite-altium-checks/claude-2026-11-06/c0453-flip/`, outside the
repository. Each case is opened, read, saved, reopened and read again. The reading covers the side of the
part, every pad's place and rotation, the designator's layer and place, the silk, and the body's projection.
