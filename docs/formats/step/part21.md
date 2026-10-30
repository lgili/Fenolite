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
- **Application protocol year** `2000` and the context names (`automotive design`, `mechanical`, `part
  definition`, `design`) are Fenolite's labels; the oracle accepts them.

## Oracle

| fact | source | label | hypothesis |
|---|---|---|---|
| `kicad-cli pcb export step` of a board whose footprints name generated STEP models adds one `NEXT_ASSEMBLY_USAGE_OCCURRENCE` per footprint and prints no `Could not add 3D model`; measured on 10.0.6 on 2026-10-30 by `tests/kicad/export/test_generated_models.py` (9.0 in CI) | S-0020, S-0029 | INFERRED until both majors pass in CI | H-K-STEP-MODELS |
