# ADR-0005: Sheet templates: a neutral drawing sheet built from closed, sourced specifications

## Status
Accepted (2026-10-02)

## Context
Plan item 0012 and v0.1 acceptance item 4 ask for one drawing sheet, generated from a neutral template,
that KiCad draws on an A3 and an A4 board. Drawing sheets carry an organisation's identity more than any
other file, so Fenolite must never ship one taken from an organisation, from KiCad's own sheets or from a
standard's copyrighted figures. The figures it may use come from public previews of ISO 5457:1999 and
ISO 7200:2004 shown by a distributor (S-0077, S-0078) and from S-0079, read for facts only.

## Decision
1. **A neutral drawing sheet in the model.** `fenolite.model.presentation.DrawingSheet` holds a setup and
   items (`SheetShape`, `SheetText`, `SheetBitmap`). It is a definition outside `Design`: one sheet serves
   many boards and sizes, so it is never stored in the `.fenolite/` layer files. `templates` builds it,
   `backends.kicad.wks` writes it; neither package imports the other.
2. **Neutral tokens, KiCad map in the backend.** Sheet texts hold neutral tokens (`{title}`, `{doc_id}`,
   `{param:NAME}`, …). `wks.KICAD_TOKENS` maps them to KiCad variables; KiCad-only variables and legacy
   `%` codes keep a read item opaque, and the writer refuses texts that KiCad would resolve unexpectedly.
3. **A closed TOML format.** `*.sheet.toml` has a closed key set, millimetre lengths read exactly, no
   expressions and no includes. Every problem is reported at once as `template.*` issues.
4. **Provenance per number.** A shipped example lists every number under `[provenance.values]`, mapped to
   `fenolite-choice` or to a registered public source; a residue test allows only S-0077, S-0078 and
   S-0079.
5. **Corner-anchored zones as a Fenolite choice.** Every point is an offset from a corner of the margin box,
   so one sheet serves every listed size. ISO 5457 counts reference fields from the centring axes, which no
   corner can express for two sizes; the examples count them from the frame corners and draw no centring
   marks.
6. **Facts only from the ISO previews, and no conformance claim.** The naming gate of 2026-10-02 found
   every S-0077 figure of the example in the preview text, so the example keeps the name
   `iso5457_generic`. It found the ISO 7200 data field names in the S-0078 preview text, but the 180 mm
   title-block width only in the distributor's summary, so the labels cite S-0078 and the width is a
   Fenolite choice. No example claims conformance with ISO 5457 or ISO 7200.

## Alternatives
- **Templates that produce KiCad trees directly.** Rejected: the second backend (v0.4) needs the same sheet.
- **One file per paper size.** Rejected: acceptance item 4 asks for one sheet on two sizes, and an agent
  passes a single `--drawing-sheet`.
- **ISO zones exact for one declared size.** Rejected: the fields would be misplaced on the other size.
- **One provenance line per file.** Rejected: it cannot show which number came from where.
- **Reading KiCad's default sheet or the kicad-templates sheets "for measurement".** Rejected: any likeness
  would then be unprovable.

## Consequences
- Agents and users write their own sheets in a small, checked format; Fenolite ships two generic examples
  under CC0 and no organisation's sheet.
- `fenolite template build` writes one `.kicad_wks` that KiCad 9.0 and 10.0 load; the drawn content is
  verified against `fenolite.templates.layout` by the oracle in `tests/kicad/sheets/`.
- Polygons and vector logos stay opaque items; importing a user's `.kicad_wks` into a template, DSL sheet
  keywords and a second-backend token map are follow-ups.
- This ADR becomes `Accepted` only after the maintainer reviews it, both examples and their provenance
  tables, in the maintainer's own commit with a `LEGAL-ANNEX.md` row.

## Evidence
S-0035, S-0036, S-0075, S-0076 (worksheet syntax and variables); S-0077, S-0078, S-0079 (figures, facts
only); hypotheses `H-K-WKS-CORNER`, `H-K-WKS-REPEAT`, `H-K-WKS-PAGE1`, `H-K-WKS-VARS`, `H-K-WKS-SVG`;
tests `tests/kicad/sheets/test_sheet_probes.py`, `tests/kicad/sheets/test_sheet_acceptance.py` and
`tests/residue/test_template_residue.py`.
