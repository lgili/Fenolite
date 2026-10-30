## Why

Stage 1 of the enclosure line (`docs/research/enclosures.md`, sections 5.1, 8 and 9). To design a board for
an off-the-shelf box, Fenolite needs the box as data: the cavity, where the board can sit, the bosses and
their screws, how tall parts may be under the lid and above the floor, and which faces can be drilled.
Datasheets give some of this directly and the rest only through boss, rib and lid positions. No tool found
in the research offers such a model as data that drives a board. Without it, c0308 (`design.fit`), c0309
(the fit check) and c0310 (face templates) have nothing to read.

## What Changes

- **A box model, `fenolite.enclosure.v0`.** One canonical JSON document per box: identity (what it fits,
  never a maker's name as our model's name), licence, provenance, outer extents, the cavity at floor and
  rim (draft), the lid, the obstacles that reach into the cavity (lid columns, ribs), one or more mount
  options (`bosses` with screws, `guides`, `floor`), each with its usable PCB area and height zones, the
  six faces with wall thickness and flat panel rectangle, Fenolite's fit clearances, per-field tolerances
  and per-field basis and evidence. Integer nm, a fixed frame (origin at the inside floor centre, Z up).
- **Strict reader and canonical writer** in `fenolite.model.enclosure`, schema `schemas/fenolite.enclosure.v0.json`
  generated with the others. A document that breaks the schema or a structural rule exits 3 with
  `FEN-3009`, naming the JSON pointer.
- **Derivation** in a new package `fenolite.enclosure`: the usable area and the zones of each mount option
  computed from cavity, draft, obstacles and clearances, so the stored values can be checked and the
  board side needs no geometry kernel.
- **Command actions** `fenolite enclosure show BOX` (read-only: validate, derive, report drift and the
  weakest evidence) and `fenolite enclosure derive BOX` (rewrite the derived fields through plan and
  confirm).
- **Fixture boxes authored for Fenolite**, CC0, with invented dimensions; a provenance block in every
  model. Real boxes go to `lgili/fenolite-library` later (stage 2, not specified here).

## Capabilities

### New Capabilities

- `enclosure-model`: the document, its frame, reader, writer, derivation, provenance and evidence rules.

### Modified Capabilities

- `package-layering`: MODIFIED "Allowed import edges" (the package `enclosure`).
- `cli-contract`: ADDED "Enclosure show and derive".

## Non-goals

- No board generation (c0308), no fit findings (c0309), no templates (c0310).
- No vendor drawing, photo, STEP or logo stored; no scraped catalogue (Decided).
- No 3D geometry: obstacles are vertical prisms with a Z range; drafted walls are linear between floor
  and rim. Snap-fits, gaskets and curved lids are out.
- No library of real boxes in this repository.

## Evidence level required

- Reader, writer and derivation: tested to `INFERRED` against hand-computed fixtures
  (`H-G-ENCL-DERIVED`, `H-G-ENCL-CANON`).
- A box field is never above `INFERRED`: a datasheet value is `INFERRED`, an assumed one `UNKNOWN`.
  A measured sample raises the field's basis, not its label; c0309 names the weakest evidence in its
  reply.

## Impact

- New: `src/fenolite/model/enclosure.py`, `src/fenolite/enclosure/` (`__init__.py`, `derive.py`,
  `frame.py`, `PROVENANCE.md`), `schemas/fenolite.enclosure.v0.json`, `tests/data/enclosure/`,
  `tests/unit/model/test_enclosure.py`, `tests/unit/enclosure/`.
- Changed: `tools/gen_schemas.py`, `cli/cmd_enclosure.py`, `cli/errors.py` (`FEN-3009`), `explain.toml`,
  `docs/design-model.md`, `docs/enclosures.md`, `docs/cli-contract.md`, the agent guide, registers,
  `openspec/README.md`, `CHANGELOG.md`.
- Depends on c0306 (the command `enclosure`).
- Size: about 6 design-days.
