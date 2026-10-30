## Context

- c0307: the box model and `fenolite.enclosure` (→ `model`, `geometry`; only `cli` and root import it).
- c0308: the fit record `.fenolite/enclosure.json` with the box embedded, mount, pose, thickness,
  generated holes and zones (with limits), and face rules with apertures.
- `checks` imports only `core`, `model`, `geometry`, `backends.base`; `roles.rules` gets its judge injected
  (`verification-loop`, "Roles judge injected into the stage"). This change follows that pattern.
- `outward_height` is the single reader of a part's height from bodies (`design-model`, "Outward height of
  a part"); it must not read a 3D model reference.
- `judge_heights` (c0140) shows the area-under-footprint test: a footprint is under an area when the
  interior of a ring of its own face meets the area's interior.
- `fenolite models` locates every model file of a board (`docs/cli-contract.md`, "models").

## Goals / Non-Goals

**Goals**: one read-only stage with 2D and 2.5D findings that never pass the unknown; heights from bodies
and, conservatively, from STEP models; the same judge in the build guard; deterministic output.

**Non-Goals**: volumes and interference (stage 3), vendor STEP comparison, fixes.

## Decided

The six decided answers of c0306's `design.md` apply: no 3D kernel here, local vendor checks store only
results, stages 0 and 1 first.

## Decisions

### 1. The stage

`enclosure.fit` stands after `placement.rules` and before `roles.rules` in `STAGE_ORDER`, and in the same
place in `DOCUMENT_STAGES`. It is a default stage, runs no tool, is not an oracle stage, and needs the board
read. Skip reasons: `no-enclosure` (no record), `not-judged` (no judge passed). A record that fails its
reader gives `check.enclosure-unreadable` (error) and the stage is skipped with `read-refused`.
`fenolite check PATH --enclosure FILE` gives the stage that record instead of `.fenolite/enclosure.json`
(native boards, or a trial of another box).

`checks.enclosure.enclosure_stage(board, fit, frame, judge, bounds)` with `EnclosureJudge`, a protocol of
`checks.enclosure`: `(board, fit, extents, heights, bounds) -> (issues, summary, evidence)`. `cmd_check`
passes `fenolite.enclosure.judge.judge` and the model tops (decision 5).

### 2. 2D rules

All in the board frame, after applying the record's pose to the box (c0308, "Fit pose transform").

- **Outline.** The outline's rings (arcs flattened outward by the geometry kernel's rule) minus the usable
  area: a non-empty difference is `enclosure.outline-outside` (error) with the largest excursion and its
  place. Otherwise the margin per side (front, back, left, right) is reported, and a margin above 1 mm on
  any side gives `enclosure.outline-inside` (info).
- **Holes.** Per boss, the nearest hole (a part of `Fenolite_Holes`, a footprint pad with a drill and no
  copper net, or a model `Hole`) within `max(boss tolerance, 0.1 mm)` of its centre; none is
  `enclosure.hole-off-boss` (error). A found hole whose drill is below `screw.drill − 0.1 mm` or above the
  screw head diameter is `enclosure.hole-size` (warning). The 0.1 mm figures are Fenolite parameters.
- **Envelopes.** Each boss grown by `clearances.obstacle` against the courtyards of bottom-side parts, and
  each screw head (head diameter + clearance) against top-side courtyards: an overlap is
  `enclosure.boss-collision` (error), naming part and boss.
- **Zones present.** Each zone area of the record missing from the board is `enclosure.zone-missing`
  (warning); the zone is still judged from the record.
- **Thickness.** The board's stack-up thickness against the record's `thickness.value` (more than 0.05 mm
  apart) or a guide mount's `{min, max}`: `enclosure.thickness-mismatch` (error).

### 3. 2.5D rules

- **Heights.** For each zone and each footprint on its side whose face ring meets the zone (the test of
  `judge_heights`), with `dnp` and off-board footprints skipped: height from decision 4; above the zone's
  `max` is `enclosure.too-tall` (error), naming part, zone, height and limit.
- **Faces.** For a wall rule: the part's placed extent (courtyard, else pads) toward the wall; its distance
  to the wall's inner plane (cavity at the board's Z, from the box) must lie in `[−protrude, gap]`, else
  `enclosure.face-gap` (error). For `top` and `bottom` rules there is no distance test.
- **Apertures.** Each aperture's shape grown by its clearance, placed in its face frame (c0308, decision 6),
  must lie inside the face's `flat` rectangle, else `enclosure.aperture-off-face` (error). Two apertures of
  one face, or an aperture and the rectangle's edge, closer than the minimum web give `enclosure.web-thin`
  (warning). The minimum web is the face's wall thickness, a Fenolite parameter stated in the docs.

### 4. Heights

Order: `outward_height(footprint)` when not `None` (source `body`); else the model top of decision 5
(source `model`); else none.

- `body` above `max`: `enclosure.too-tall`.
- `model` at or below `max`: a pass, counted in `summary.heights.from_model`, with
  `enclosure.height-from-model` (info) so the user knows the proof's basis.
- `model` above `max`: `enclosure.height-unproved` (warning). A conservative top over the limit does not
  prove the part too tall.
- none: `enclosure.height-unknown` (warning). Never a pass.

`outward_height` stays the only reader of bodies; the model top is a separate, labelled input.

### 5. Conservative model top (`fenolite.enclosure.bounds`)

`model_top(step_text, offset, scale, rotate) -> int | None` in nm above the board face:

1. The file must be ISO 10303-21 (S-0954) with length unit millimetre (`SI_UNIT(.MILLI.,.METRE.)`), else
   `None`.
2. A file whose shape representation uses more than one placement transform between products (an
   assembly with `ITEM_DEFINED_TRANSFORMATION`) gives `None` in v0.
3. The bound box is the union of every `CARTESIAN_POINT`, and of the box `centre ± radius` of every
   `CIRCLE`, `SPHERICAL_SURFACE` and `TOROIDAL_SURFACE` (major plus minor radius), entity names read from
   the schema (S-0959). B-spline curves lie inside the bounding box of their control points
   (S-0960; the same for surfaces is INFERRED), which are `CARTESIAN_POINT`s, so the box contains them.
4. The eight corners are scaled, turned and offset as the footprint's `model` token says
   (`docs/formats/kicad/libraries.md`, `H-K-MODEL-PLACE`), and the largest Z is the top.

`cmd_check` locates each footprint's first STEP model with the `models` locator (a `.wrl` path takes its
`.step` sibling), reads it once per path, and passes `bounds: {footprint id → top}`. No file is copied or
kept; no request is made. Reading a model counts toward no budget beyond the stage's.

### 6. Evidence and summary

Stage evidence: `Evidence.combine` of `INFERRED` (`H-G-ENCL-FIT-CHECK`, plus `H-K-ENCL-MODEL-TOP` when a
model top was used) and the box's weakest field. `summary` holds `box` (`id`, `sha256`), `mount`,
`outline` (`inside`, margins), `holes` (`judged`, `failed`), `heights` (`judged`, `failed`, `from_model`,
`unproved`, `unknown`), `faces` (`judged`, `failed`), `apertures` (`judged`, `failed`, `thin`), and
`weakest`. A box with no field of basis `measured` or `local-step` gives `enclosure.model-unverified`
(warning): "first board in this box: check a sample before ordering".

### 7. Build guard

With a fit, the build's placement guard runs the judge on the planned board read back and reports every
finding with a severity no higher than `warning`; `result.placement.rules` gains the family `enclosure`
with the counts. A build never refuses for a fit.

## Codes

| code | severity | when |
|---|---|---|
| `check.enclosure-unreadable` | error | the fit record fails its reader |
| `enclosure.outline-outside` | error | part of the outline lies outside the usable area |
| `enclosure.outline-inside` | info | the outline is inside, with a margin above 1 mm on a side |
| `enclosure.hole-off-boss` | error | no hole within tolerance of a boss centre |
| `enclosure.hole-size` | warning | the hole on a boss does not suit its screw |
| `enclosure.boss-collision` | error | a courtyard overlaps a boss or screw-head envelope |
| `enclosure.zone-missing` | warning | a zone area of the record is not on the board |
| `enclosure.thickness-mismatch` | error | the board thickness differs from the fit's or the guide range |
| `enclosure.too-tall` | error | a part's body is taller than its zone's limit |
| `enclosure.height-from-model` | info | a part passed on its conservative model top |
| `enclosure.height-unproved` | warning | only a model top is known and it is above the limit |
| `enclosure.height-unknown` | warning | no body and no model top under a zone |
| `enclosure.face-gap` | error | a face part is too far from its wall or reaches too far into it |
| `enclosure.aperture-off-face` | error | an aperture leaves its face's flat rectangle |
| `enclosure.web-thin` | warning | a web between apertures or to the edge is below the minimum |
| `enclosure.model-unverified` | warning | the box has no field measured from a sample or a local STEP |

No new `FEN-` code: findings exit 5 with `FEN-5001` as every stage's do; a broken record named by
`--enclosure` exits 3 with c0307's `FEN-3009`.

## Hypotheses registered by this change

- `H-G-ENCL-FIT-CHECK`: on the seeded fixtures (one good board, one bad board per rule), the stage gives
  exactly the seeded findings and nothing on the good board.
- `H-K-ENCL-MODEL-TOP`: for the official models of the pinned library used by the examples, the model top
  is never below the top of the same part in `kicad-cli pcb export vrml` 10.0.x of a one-part board.

## Evidence per behaviour

| behaviour | level |
|---|---|
| 2D and 2.5D rules | `INFERRED` (`H-G-ENCL-FIT-CHECK`) |
| model top | `INFERRED`, `ORACLE-VERIFIED(kicad-cli)` for the measured models |
| stage reply | lower of the above and the box's weakest field |

## Risks / Trade-offs

- **Courtyards stand for bodies** in the 2D envelope rule. A part without a courtyard is judged by its pads
  and gets no pass for missing data: its height rule still needs a body or model.
- **Model tops can be loose** (control points far outside a curved surface): a loose top gives
  `height-unproved`, never a wrong pass.
- **Draft**: the face distance uses the cavity at the board's Z, so a drafted wall is judged where the
  part stands.

## Open Questions

1. Through-hole leads below the board: judge them against bottom zones with an assumed protrusion?
   Recommended: not in v0; add `enclosure.lead-unknown` later with a public figure for lead length.
2. Should `fenolite place` run the judge? Recommended: later, with the same warning rule as the build.
3. Should the margin threshold of `outline-inside` (1 mm) be a box clearance? Recommended: a parameter of
   the stage (`--enclosure-margin`) only if users ask.
4. Read VRML models when no STEP sibling exists? Recommended: no in v0; the result is `height-unknown`.

## Relation to the other changes

Judges what c0308 recorded against c0307's model. c0310's templates use the same aperture placement and
refuse to write when this judge gives an aperture error. Stage 3 later adds a 3D interference finding
through gmsh, labelled `ORACLE-VERIFIED(gmsh)`.

## Size

About 6 design-days: stage and injection 1, 2D rules 1.5, heights and faces 1.5, model tops and the KiCad
measurement 1.5, guard, codes and docs 0.5.
