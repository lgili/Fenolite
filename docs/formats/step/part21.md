# STEP exchange files written for generated bodies

Change c0260. `fenolite.backends.step.write_bodies` writes one ISO 10303-21 exchange file per generated footprint
from its extruded bodies, so that `kicad-cli pcb export step` and the viewer find a 3D model. This page records
the format facts the writer relies on, each with its public source; the oracle is `kicad-cli pcb export step`,
which reads the file with its own STEP reader and runs as a separate process (`H-K-STEP-MODELS`). No STEP
library, reader or writer code was read, and no third-party CAD model was used. ISO's catalogue page of
ISO 10303-21 refused the fetch tool (HTTP 403) on 2026-10-30; nothing of the standard's text was read.

## File structure

| fact | source | label |
|---|---|---|
| The file starts with `ISO-10303-21;`, then a `HEADER` section and a `DATA` section, each closed by `ENDSEC;`; the example ends with `END-ISO-10303-21;` | S-0991 | INFERRED |
| The header holds, in this order, `FILE_DESCRIPTION(description, implementation_level)` (level `'2;1'` in the article), `FILE_NAME(name, time_stamp, author, organization, preprocessor_version, originating_system, authorization)` with an ISO 8601 time stamp, and `FILE_SCHEMA` naming the EXPRESS schema; other header fields may be empty strings | S-0991 | INFERRED |
| An instance is `#N=` with a positive integer N, the entity name in capitals and its explicit attribute values in order in parentheses; a reference may point before or after its instance | S-0991 | INFERRED |
| Strings are in single quotes; enumerations and booleans in capitals between dots (`.T.`, `.MILLI.`); an unset value is `$`; an explicit attribute re-declared as derived in a subtype is `*`; aggregates are parenthesised lists separated by commas; numbers are written as in programming languages | S-0991 | INFERRED |
| A complex instance of several leaf entities uses the external mapping: each constituent entity with its own attributes, in alphabetical order, in one pair of parentheses | S-0991 | INFERRED |
| The schema name of AP214 is `AUTOMOTIVE_DESIGN`, followed for new files by the third-edition object identifier `{ 1 0 10303 214 3 1 1 }` | S-0992 | INFERRED |

## Entities written (attribute order)

All from the EXPRESS pages of the AP214 AIM published by STEP Tools (S-0993), read for the explicit attributes
of each entity in Part 21 order (inherited first). Label: `INFERRED` until the oracle row below.

| entity | explicit attributes, in order |
|---|---|
| `CARTESIAN_POINT` | name, coordinates (list of 1 to 3 reals) |
| `DIRECTION` | name, direction_ratios (list of 2 or 3 reals) |
| `VECTOR` | name, orientation (direction), magnitude |
| `LINE` | name, pnt (point), dir (vector) |
| `VERTEX_POINT` | name, vertex_geometry (point) |
| `EDGE_CURVE` | name, edge_start, edge_end, edge_geometry (curve), same_sense |
| `ORIENTED_EDGE` | name, `*` (edge_start, derived), `*` (edge_end, derived), edge_element, orientation |
| `EDGE_LOOP` | name, edge_list (the first edge starts where the last ends) |
| `FACE_OUTER_BOUND` | name, bound (loop), orientation |
| `AXIS2_PLACEMENT_3D` | name, location, axis (optional), ref_direction (optional) |
| `PLANE` | name, position (axis2_placement_3d) |
| `ADVANCED_FACE` | name, bounds, face_geometry (surface), same_sense |
| `CLOSED_SHELL` | name, cfs_faces |
| `MANIFOLD_SOLID_BREP` | name, outer (closed shell) |
| `ADVANCED_BREP_SHAPE_REPRESENTATION` | name, items, context_of_items; items are manifold solid B-reps, faceted B-reps, mapped items or axis placements, at least one solid |
| `APPLICATION_CONTEXT` | application |
| `APPLICATION_PROTOCOL_DEFINITION` | status, application_interpreted_model_schema_name, application_protocol_year, application |
| `PRODUCT_CONTEXT` | name, frame_of_reference, discipline_type |
| `PRODUCT` | id, name, description, frame_of_reference (set of product contexts) |
| `PRODUCT_DEFINITION_FORMATION` | id, description, of_product |
| `PRODUCT_DEFINITION_CONTEXT` | name, frame_of_reference, life_cycle_stage |
| `PRODUCT_DEFINITION` | id, description, formation, frame_of_reference |
| `PRODUCT_DEFINITION_SHAPE` | name, description, definition |
| `SHAPE_DEFINITION_REPRESENTATION` | definition, used_representation |
| `SI_UNIT` | `*` (dimensions, derived), prefix (optional; values include `milli`), name (values include `metre`, `radian`, `steradian`) |
| `UNCERTAINTY_MEASURE_WITH_UNIT` | value_component, unit_component, name, description |
| `GEOMETRIC_REPRESENTATION_CONTEXT` | coordinate_space_dimension (after `REPRESENTATION_CONTEXT`'s context_identifier and context_type) |
| `GLOBAL_UNIT_ASSIGNED_CONTEXT`, `GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT` | units; uncertainty |
| `STYLED_ITEM` | name, styles, item |
| `PRESENTATION_STYLE_ASSIGNMENT` | styles |
| `SURFACE_STYLE_USAGE` | side (`positive`, `negative`, `both`), style |
| `SURFACE_SIDE_STYLE` | name, styles |
| `SURFACE_STYLE_FILL_AREA` | fill_area |
| `FILL_AREA_STYLE` | name, fill_styles |
| `FILL_AREA_STYLE_COLOUR` | name, fill_colour |
| `COLOUR_RGB` | name, red, green, blue (each 0 to 1) |
| `MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION` | name, items, context_of_items |

## Fenolite's choices

- **One product, one solid per body.** The product is named after the footprint; each extruded body is a
  `MANIFOLD_SOLID_BREP` named after the body (`body`, `lead:1:foot`, `pin:3`, ...): a prism over its outline
  from `z_min` to `z_max`, with planar faces (`PLANE`), straight edges (`LINE` with a unit magnitude) and the
  outline turned counter-clockwise, so that every face's loop runs counter-clockwise about its outward
  normal and every edge is used once in each sense. Each solid has V − E + F = 2.
- **Frame and units.** Millimetres (`SI_UNIT(.MILLI.,.METRE.)`), the footprint's frame with Y up (the board's
  −Y), Z up from the mounting face: the frame KiCad places a model in (`docs/formats/kicad/libraries.md`, "Model
  placement").
- **Exact numbers.** Every coordinate is an exact decimal printed from integer nanometres (`1.27`, `5.`); a
  direction is printed from integer ratios (`1.`, `-1270000.`); no number has an exponent and no float is
  formatted. The uncertainty is `0.0001` mm.
- **Fixed order.** Instances are numbered in a fixed traversal: product structure, units and context, the axis
  of the origin, each solid (vertices, edges, faces, shell), the representations, the colours. Directions and
  colours are written once per file. The header names `Fenolite` without a version and takes the time stamp
  as an argument (`1970-01-01T00:00:00` by default): equal arguments give equal bytes.
- **Colours.** `body` dark grey (0.2), leads, pins and tabs light grey (0.8), applied with `STYLED_ITEM`.
- **Cylinders and spheres** (change c0423, `write_solids`). A cylinder is the prism over the regular polygon of
  `n` vertices on its circle; a sphere has two poles, `n/2 − 1` rings of `n` vertices, triangles at the poles
  and quadrilaterals between the rings. `n` is the smallest even number from 24 that keeps the sagitta
  `r·(1 − cos(π/n))` at 10 µm or less, at most 96. Each quadrilateral is an isosceles trapezoid, planar before
  the vertices are rounded to the nanometre and within the file's 0.0001 mm after. A face's plane takes its
  first vertex as origin, the cross product of its first two edges as normal and its first edge as
  reference direction, all from integer ratios. The entities are those of the prism: no curved surface is
  written. The header's description is `Fenolite component bodies`; `write_bodies` keeps
  `Fenolite extruded component bodies` and its bytes.
- **Application protocol year** `2000` and the context names (`automotive design`, `mechanical`, `part
  definition`, `design`) are Fenolite's labels; the oracle accepts them.

## Box of a model (c0449)

`fenolite.backends.stepbox.model_box` reads a STEP model that a KiCad project holds and gives the box of its
edges, which a conversion to Altium writes as a model body's outline and heights
(`docs/formats/altium/pcb-bodies.md`, "Written form of a model body"). It is Fenolite's own reader, written
from the file structure above and the entity pages below; no STEP library or parser code was read or run.
The attribute orders are those of the STEP Tools EXPRESS pages of the AP214 AIM (S-2082, read
2026-11-06), inherited attributes first. Label of the rows: `INFERRED`; hypothesis `H-G-STEP-BOX`.

| entity | explicit attributes, in order, that the reader uses |
|---|---|
| `VERTEX_POINT` | name, vertex_geometry (a point) |
| `EDGE_CURVE` | name, edge_start, edge_end, edge_geometry, same_sense |
| `AXIS2_PLACEMENT_3D` | name, location, axis (default +Z), ref_direction (default +X) |
| `CIRCLE`, `ELLIPSE` | name, position, radius; or semi_axis_1, semi_axis_2 |
| `SURFACE_CURVE`, `SEAM_CURVE`, `TRIMMED_CURVE` | name, curve_3d or basis_curve, … |
| `B_SPLINE_CURVE` and its subtypes | name, degree, control_points_list, … (in a complex instance the `B_SPLINE_CURVE` constituent holds no name) |
| `POLYLINE`, `POLY_LOOP`, `COORDINATES_LIST` | name, points; name, polygon; name, npoints, position_coords |
| `REPRESENTATION` and its `*SHAPE_REPRESENTATION` subtypes | name, items, context_of_items |
| `REPRESENTATION_RELATIONSHIP` | name, description, rep_1, rep_2 |
| `REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION` | transformation_operator; its rules require `transform_item_1` to be an item of `rep_1`'s context and `transform_item_2` of `rep_2`'s |
| `ITEM_DEFINED_TRANSFORMATION` | name, description, transform_item_1, transform_item_2 |
| `SHAPE_DEFINITION_REPRESENTATION` | definition, used_representation |
| `PRODUCT_DEFINITION_SHAPE` | name, description, definition |
| `NEXT_ASSEMBLY_USAGE_OCCURRENCE` | id, name, description, relating_product_definition, related_product_definition, reference_designator |
| `CONTEXT_DEPENDENT_SHAPE_REPRESENTATION` | representation_relation, represented_product_relation |
| `GLOBAL_UNIT_ASSIGNED_CONTEXT` | units |
| `SI_UNIT` | prefix (`si_prefix`: `.EXA.` to `.ATTO.`, `$` for none), name (`.METRE.`) |
| `CONVERSION_BASED_UNIT`, `LENGTH_MEASURE_WITH_UNIT` | name, conversion_factor; value_component, unit_component |
| `TRIMMED_CURVE` (c0481) | name, basis_curve, trim_1, trim_2, sense_agreement, master_representation; a trim is a set of `trimming_select`: a `CARTESIAN_POINT`, a `PARAMETER_VALUE` or a bare parameter |
| `LINE`, `VECTOR` (c0481) | name, pnt, dir; name, orientation, magnitude. The line's point at the parameter u is pnt + u · magnitude · orientation |
| `PLANE_ANGLE_MEASURE_WITH_UNIT`, `PLANE_ANGLE_UNIT` (c0481) | value_component, unit_component; a plane angle unit is an `SI_UNIT` of `.RADIAN.` or a `CONVERSION_BASED_UNIT` (a degree is 0.01745329… radian) |

The rules of the reader:

- **Points.** Each vertex point; for a circular or elliptic edge its two ends and each point of the curve,
  within the edge's span, where a coordinate is extreme (the span runs counter-clockwise about the
  placement's axis from start to end when `same_sense` is `.T.`, the other way otherwise; equal ends make a
  whole turn); the control points of a B-spline edge, whose curve lies in their hull; the points of polylines,
  poly loops and coordinate lists. A closed solid lies in the box of its edges unless a face bulges between
  them (a sphere or a torus); a box from control points may exceed the solid.
- **Surface models (c0481).** A representation that reaches no edge, such as a
  `GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION` of `CURVE_BOUNDED_SURFACE`s, gives the points of its
  trimmed curves instead.
  - On a line: its two trims.
  - On a circle or an ellipse: its two trims and each extreme within the span. A parameter is an angle in
    the context's plane angle unit (the radian when it names none). The span runs counter-clockwise from
    `trim_1` to `trim_2` when `sense_agreement` is `.T.`, from `trim_2` to `trim_1` otherwise.
  - A representation with edges is measured by its edges alone.
- **Units.** Each representation's points are scaled by the length unit of its context: an `SI_UNIT` of the
  metre with its prefix, or a `CONVERSION_BASED_UNIT` through its `LENGTH_MEASURE_WITH_UNIT` (an inch is
  25.4 mm). A context without a length unit is taken as millimetres.
- **Assemblies.** A relationship with an item-defined transformation places `rep_1` in `rep_2` by bringing
  `transform_item_1` onto `transform_item_2`. Exporters write the pair in either order, so the component is
  the representation whose product is the `related_product_definition` of the usage that the relationship's
  `CONTEXT_DEPENDENT_SHAPE_REPRESENTATION` names; the public models hold both orders (S-2081). A relationship
  without a transformation joins two representations in one frame. A representation placed several times
  counts at each placement, up to 1000.

## Oracle

| fact | source | label | hypothesis |
|---|---|---|---|
| `kicad-cli pcb export stl` of a converted board places every vertex of the generated prisms, cylinders and spheres and of the extracted models where the source puts them, within 2 µm, on 9.0.9 and 10.0.6 (change c0423; `tests/kicad/convert/test_altium_model_pose.py`) | S-1820 | KICAD-VERIFIED (9.0.x, 10.0.x; 2026-11-05) | H-K-MODEL-POSE |
| `kicad-cli pcb export step` of a board whose footprints name generated STEP models adds one `NEXT_ASSEMBLY_USAGE_OCCURRENCE` per footprint and prints no `Could not add 3D model`; measured on 10.0.6 on 2026-10-30 by `tests/kicad/export/test_generated_models.py` (9.0 in CI) | S-0020, S-0029 | INFERRED until both majors pass in CI | H-K-STEP-MODELS |
