# c0481: the box of a STEP surface model

## Why

A conversion to Altium writes each STEP model of a footprint as a body. The body's outline and heights
come from the model's box (`stepbox.model_box`, c0449). `model_box` measures edges only. A model that
holds bounded surfaces and no edge (`GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION` of
`CURVE_BOUNDED_SURFACE`s) therefore has no box. Its body is lost with "the STEP model holds no edge
whose box Fenolite can measure".

On the maintainer's board (private; codes and counts only), 1 of 183 models is lost this way, in F2 and
in F5. A vendor's surface model is a common case.

## What Changes

- A representation that reaches no edge is measured by its `TRIMMED_CURVE`s:
  - over a `LINE`: its two trims;
  - over a circle or an ellipse: its trims and each extreme within the span.
- A trim is a point or a parameter. A line's parameter scales its `VECTOR`; a conic's is an angle in the
  context's plane angle unit (`PLANE_ANGLE_UNIT`: radian, or a conversion-based unit such as the degree).
- A representation with edges is measured as before.

## Impact

- `src/fenolite/backends/stepbox.py`, `docs/formats/step/part21.md`.
- No box of an edge model changes.
