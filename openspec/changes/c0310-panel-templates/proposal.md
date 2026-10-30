## Why

Stage 1 of the enclosure line (`docs/research/enclosures.md`, sections 6.2, 8 and 9). The research calls a
1:1 drilling template per face of a purchased box "probably the single most useful hobbyist feature": print
it, tape it on the wall, drill. A CNC, laser or front-panel service takes the same drawing as DXF. Today a
user measures each connector by hand and transfers it to the box. After c0308 the board knows its box, its
pose and the aperture of every part that faces a wall, the lid or the floor, so the template is a drawing
of data Fenolite already holds. It needs no 3D kernel.

## What Changes

- **New action `fenolite enclosure templates PATH --out DIR [--faces LIST] [--formats svg,pdf,dxf]
  [--enclosure FILE]`.** For each face that holds an aperture (or each face `--faces` names) it writes
  `DIR/<face>.svg`, `DIR/<face>.pdf` and `DIR/<face>.dxf`, through the reviewed-plan protocol, all files or
  none.
- **What a template holds**, drawn as seen from outside: the face's outer rectangle and its split line, the
  flat drillable rectangle (dashed), a datum corner, each opening (the aperture grown by its clearance)
  with a centre cross and its size, the reference of its part, the box id, the face name, "print at 100 %"
  and, in SVG and PDF, a 100 mm scale bar. Edge connectors, LEDs, buttons and displays are all apertures
  declared with `fit.face()` (c0308).
- **Exact scale.** SVG sizes in `mm` with a millimetre `viewBox` (S-0955); PDF pages in points of 1/72 inch
  with `/PrintScaling /None` (S-0956); DXF in millimetres (`$INSUNITS` 4, S-0957), lines, arcs and circles
  only. Coordinates come from integer nm with fixed decimals.
- **Byte-identical.** The same board, record and options give the same bytes; no date unless `--timestamp`
  is given, and then only in the PDF's information dictionary. The receipt lists every file's SHA-256.
- **Checked first.** c0309's judge runs on the faces' aperture rules; an `enclosure.aperture-off-face`
  error plans no write (exit 5). `enclosure.template-empty` (info) for a named face without an
  aperture, `enclosure.template-large` (warning) when a page exceeds A4.

## Capabilities

### New Capabilities

- `enclosure-templates`: face frames on paper, the content of a template, the three writers and their
  determinism.

### Modified Capabilities

- `cli-contract`: ADDED "Enclosure templates command".

## Non-goals

- No milling program, no tool paths, no service's own file format.
- No panels in the board-panel sense (`fenolite panel`, c0173): "panel" here is a face of a box, and the
  codes are `enclosure.template-*` to keep the two apart.
- No tiling of large faces over several sheets in v0 (open question).
- No 3D kernel, no STEP.

## Evidence level required

- Geometry and bytes: `INFERRED` by unit tests (`H-G-ENCL-TEMPLATE-BYTES`).
- Files read by independent readers: `INFERRED` until `H-G-ENCL-TEMPLATE-FILES` is measured.
- Printed scale: `INFERRED` until the maintainer's author report (`H-G-ENCL-TEMPLATE-SCALE`).

## Impact

- New: `src/fenolite/enclosure/templates.py`, `src/fenolite/enclosure/svg.py`, `pdf.py`, `dxf.py`, tests
  under `tests/unit/enclosure/` and `tests/unit/cli/`, golden files under `tests/data/enclosure/templates/`,
  `docs/formats/templates/{svg,pdf,dxf}.md`.
- Changed: `cli/cmd_enclosure.py`, `explain.toml`, `docs/enclosures.md`, `docs/cli-contract.md`, the agent
  guide (`fabrication.md`), registers, `openspec/README.md`, `CHANGELOG.md`.
- Sources: S-0955 to S-0957.
- Depends on c0308 (apertures and the record) and c0309 (the judge).
- Size: about 5 design-days.
