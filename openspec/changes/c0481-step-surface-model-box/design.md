# Design: c0481

## D1 Trimmed curves only where there are no edges

A B-rep model may also name trimmed curves as edge geometry. A trimmed curve's span can exceed its edge,
so mixing both could grow a box that is right today. `_geometry` therefore adds trimmed-curve points
only for a representation that reaches no `EDGE_CURVE`.

## D2 Parameters

ISO 10303-42 parameterises a line by pnt + u · dir, where dir is the `VECTOR` with its magnitude, and a
circle or an ellipse by the angle from the placement's x axis, in the plane angle unit of the context.
`_context_radians` reads that unit as `_context_mm` reads the length unit. A context without one is
taken as radians. A trim given as a point wins over its parameter. Without `sense_agreement` the span
is the reverse one, from trim 2 to trim 1.

## D3 Shared extremes

The extremes of a conic within a span (`_extremes`) are shared by edges (`_arc`) and trimmed curves
(`_trimmed`).
