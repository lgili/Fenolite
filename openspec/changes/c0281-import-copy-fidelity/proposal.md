## Why

Converting the public KiCad demos into `lgili/fenolite-library` (2026-10-30, Fenolite `8dab89d6`) found
twelve problems (`boards/ISSUES.md` there). The worst blocks every proof: `verify-source` builds with the
copper guard in `refuse` mode, so a finished board whose clearances break Fenolite's rules proves nothing.
The maintainer's intent: an imported board is a copy of finished work; Fenolite copies it, never refuses
it for its clearances, and the copy is complete at every level, S included. The rest are unreported
losses and proof noise or gaps.

## What Changes

- **Copy mode.** The import record (`PROVENANCE.json`, `fenolite.import-provenance.v0`) gains `copy: true`.
  A design beside an import record, or a library record holding one as `import`, is a copy: `verify-source`
  and `build` then run the copper guard in `warn` mode (findings listed, never refused). `verify-source`
  gains `--copper-check {refuse,warn}`; an explicit option wins everywhere.
- **Pads on no net** stay on no net: the symbol the import draws has no pin for a pad number that no
  instance connects, and level 2 treats an `unconnected-(…)` net held by the pads of one element as no net.
- **Copper check agrees with KiCad's tolerance.** Measured on `kicad-cli` 10.0.6: KiCad's DRC reports a
  clearance only below the value minus 500 nm, for every pair kind and source, the class pair gap included.
  The KiCad rules source gives it to the guard. A pair gap stays a clearance, as in KiCad.
- **Losses reported.** A board outline stroke other than 0.1 mm is the unexpressed kind `outline-width`; a
  non-copper layer table other than the DSL board's is `layer-table`.
- **Proof fixes.** Level 7 matches graphics by geometry and reports a width as one `graphic-field`; level 6
  pairs layers by name (`layer-field` for a kind or an order); level 7 leaves out the lens property
  `fenolite.path`; opaque root items (teardrops, groups) are counted per kind (`opaque-count`); `--against
  x.kicad_pro` reads only that project's board and sheet tree.
- **Bottom-side field angles** survive the derive.
- **Level S gate.** `fidelity.proof.skipped` records why a level was skipped; the library gate accepts a
  skipped level only with a recorded reason other than `build-failed`, until c0276's extraction and c0278's
  level S lift it.
- **Replayable steps** never hold `--plan`; a writing step records `--confirm`.
- Issue 11 (J1 and J2 of `royalblue54L_feather`) is investigated and recorded.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `fidelity-proof` (c0278): ADDED "Copy mode in verify-source", "Original project files", "Import losses
  in the proof", "Skipped levels in the recorded proof".
- `board-to-code` (c0275): ADDED "Import record marks a copy", "Pads on no net in the vendored symbols",
  "Outline width and layer table reported".
- `design-equivalence`: ADDED "Level 2 open nets of one element", "Level 6 pairs layers by name", "Level 7
  graphic widths", "Level 7 leaves out the lens property", "Opaque items counted at level 7".
- `copper-check`: ADDED "Clearance tolerance of the tool".
- `design-dsl`: ADDED "Copy mode in build".
- `fenolite-library` (c0279): ADDED "Skipped levels in the proof gate", "Replayable conversion steps".
- `design-conversion`: ADDED "Bottom-side angles in a derived footprint".

## Non-goals

- No new DSL name: outline width, user layers, teardrops, texts and the other gaps stay with c0277.
- No drawn-schematic import and no level-S comparison (c0275 phase, c0278 task 2.4).
- No exact arc distance in the copper check (a follow-up).
- No third-party file in this repository: fixtures are authored for Fenolite (CC0).

## Evidence level required

- KiCad's 500 nm tolerance: `KICAD-VERIFIED (10.0.x)` from the local measurement, `INFERRED` for 9.0.x
  until the `kicad-9` job runs the bench (`H-K-COPPER-EPSILON`).
- Everything else `INFERRED`, proved by hermetic regression tests on authored fixtures.
