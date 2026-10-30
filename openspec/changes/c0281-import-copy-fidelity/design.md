## Context

- **Source.** `boards/ISSUES.md` of `lgili/fenolite-library` (branch `first-boards`, 2026-10-30): twelve
  issues found converting the KiCad demos with Fenolite `8dab89d6` (`circuits-as-code`). Upstream:
  `gitlab.com/kicad/code/kicad` at `97acc80c`, folder `demos/`. No third-party file enters this repository:
  the issues were reproduced on the demos shipped in the image `kicad/kicad:10.0.6` in a temporary folder,
  and every regression test uses fixtures authored for Fenolite.
- **What exists.** c0275 (`fenolite import --to python`, `PROVENANCE.json`, self-check), c0278
  (`verify-source`, levels 5 strict to 8, accepted differences), c0276 (drawn schematics, `extract`) are on
  `circuits-as-code`; c0278 task 2.4 (`compare_drawn`) and c0279 (library repository, `replay`, proof gate)
  are not implemented.
- **Archive order.** c0275, c0278 and c0279 first: this change ADDs requirements to `board-to-code`,
  `fidelity-proof` and `fenolite-library`, which those changes create.

## Goals / Non-Goals

**Goals**: an imported board is proved as a copy (never refused for its clearances); every loss the
import makes shows in its report or in the proof; the proof reports only differences of the design.

**Non-Goals**: see the proposal. The DSL gaps of the issue list (`text`, `dimension`, `teardrop`,
`via-span`, `net-tie`, `dnp`, `group`, outline width, user layers) stay with c0277 (`dsl-board-coverage`).

## Decisions

### 1. Copy mode (issue 1)

```
fenolite verify-source out/design.py --against upstream/cm5/CM5_MINIMA_3.kicad_pro --json   # copy: warn
fenolite verify-source out/design.py --against ... --copper-check refuse                    # explicit
fenolite build out/design.py --out build --confirm                                          # copy: warn
```

- **Where the mode lives.** In the import record, not in `design.py`: `PROVENANCE.json` gains `"copy":
  true` (the schema stays `fenolite.import-provenance.v0`; the member is optional). A design is a copy
  when the provenance file beside it (or `--provenance`) holds an import record, as the whole file
  (`schema` `fenolite.import-provenance.v0`) or as its member `import` (a library record,
  `fenolite.provenance.v0`), and that record's `copy` is not `false`. A record written before this change
  has no member and counts as a copy: every import is one. A person who takes a converted board as their
  own sets `"copy": false`, and the guard refuses again.
- **Effect.** No `--copper-check` given and a copy: the guard runs in `warn` (findings are warnings with
  the warn note, files are written). `verify-source` reports `build.copper_check` (`refuse` or `warn`) and
  `build.copy`; `build` reports `copper_check.mode_source` (`option`, `copy` or `default`). An explicit
  option always wins.
- **Alternatives.** A DSL call `design.copy_of(...)`: rejected, it puts proof state in the design and needs
  a new DSL name. Always `warn` in `verify-source`: rejected, a hand-written script should still be refused
  for a short (the c0278 contract builds "as `fenolite build` runs it").

### 2. Pads on no net (issue 2)

- The import draws one symbol per footprint (c0275 decision 8). A pad number on no net in every instance of
  that footprint gets no pin, so the build leaves the pad on no net, as the source's own symbol did (a
  shield or thermal pad without a pin). A number on a net in one instance and on no net in another keeps
  its pin; there level 2 below applies.
- Level 2 already reads a net named `unconnected-(…)` held by one pad as no net. It now counts distinct
  elements, not pads: two pads `0` of `J4` (one element `J4-0`) on `unconnected-(J4-0-Pad0)` are no net.
  The self-check (built without a schematic) and `verify-source` (built with one) then agree.

### 3. KiCad's clearance tolerance (issue 3), measured

Benches of `tests/kicad/copper/_copperparity.py` (authored), boundary rows at `c − δ`, `kicad-cli` 10.0.6
in the local image `kicad/kicad:10.0.6` (2026-10-30):

| source of `c` | pair kinds | δ = 1 nm … 500 nm | δ = 501 nm, 600 nm, 1 µm, 1.5 µm, 2.5 µm |
|---|---|---|---|
| custom rule (0.2 mm) | track–track, via–track, via–via, pad–track, pad–pad, tht–track | clean | `clearance` |
| class (0.3 mm) | track–track, via–track, via–via, pad–track, pad–pad, tht–track | clean | `clearance` |
| board minimum (0.4 mm) | the same six | clean | `clearance` |
| class pair gap (0.15 mm, class clearance above) | the two tracks of a pair | clean | `clearance` |
| class and board minimum | arc–track | clean at 1 nm, `clearance` at 500 nm | `clearance` |

- KiCad reports a clearance only when the gap is below `c − 500 nm`, for straight items, vias and pads
  under every source; the class `diff_pair_gap` is a clearance between the two nets of a pair (as
  `H-K-PRO-PAIR` and `H-K-COPPER-PAIR` record). So the guard keeps the pair-gap rule and gains the tolerance.
- **Design.** `DesignRules.clearance_tolerance` (default 0); the KiCad rules source sets
  `KICAD_DRC_EPSILON_NM = 500` for both majors. `check_copper(..., tolerance=0)` judges a pair too close when
  its shapes are closer than `value − tolerance`; `copper_guard` and `copper_stage` pass the rules' value.
  Direct calls keep the strict rule ("Strict comparison" holds). Edge clearance is not measured and keeps
  the strict rule.
- **What remains.** The demo board `cm5_minima` has no clearance violation in KiCad 10.0.6; Fenolite's guard
  reported 390. Most pair-gap findings involve arcs, which the guard widens by twice its 1 µm band so that
  no violation is missed (`copper-check`, "Clearance findings"); that band is above KiCad's 500 nm and
  stays: under copy mode such findings are warnings. An exact arc distance is a follow-up (open question 2).
- `H-K-COPPER-EPSILON` is registered; 9.0.x stays `INFERRED` until the `kicad-9` job runs the bench.
- **Second run.** `tests/kicad/copper/test_drc_tolerance.py` (rows at exactly `c − 500 nm` and `c − 501 nm`,
  the guard's tolerance included) passed in the same image: KiCad and Fenolite agree on all 38 rows.
- **The demos.** `kicad-cli pcb drc` 10.0.6 on `cm5_minima`: no `clearance`, two `copper_edge_clearance`
  (Fenolite: the same two); on `tiny_tapeout`: 9 `clearance` and 3 `shorting_items`. Fenolite's check of the
  upstream boards with the KiCad rules source, before and after the tolerance: `cm5_minima` 390 → 310
  `copper.clearance` (158 `pair-gap`, 112 `class`, 40 `zone`), `tiny_tapeout` 111 → 90 (63 `class`, 27
  `zone`) and the same 3 shorts. What remains is mostly arcs judged with the widened band (gaps 0.5 µm to
  2.4 µm short) and fills against items at the zone's clearance (open question 2 and a follow-up on fills);
  under copy mode they are warnings and the proof runs.

### 4. Losses the import reports (issues 4 and 5)

- `outline-width`: the root `Edge.Cuts` items whose stroke width is not the 0.1 mm a DSL board writes
  (`OUTLINE_WIDTH`); one row with the count.
- `layer-table`: the names of the source's non-copper layers differ from those of the DSL board of its
  copper count (`layers.created_layers`); one row per extra or missing name set, examples the names.
- Both are explained at level 6 or 7 only; the self-check compares levels 1 to 5, so the import still
  passes, and the proof shows the loss as one difference per item until c0277 expresses them.

### 5. Proof fixes (issues 4, 5, 7, 8, 9)

- **Level 7 graphics** match by layer, kind, normalised geometry and fill; a matched pair compares `width`
  as `graphic-field` (field `width`). An outline drawn 0.2 mm upstream and 0.1 mm built is one difference
  per segment instead of two `graphic-missing`.
- **Level 6 layers** match by name. A name on one side only is `layer-missing` (`where`
  `<kind>:<name>`); a matched pair of another kind is `layer-field` (field `kind`); when the common names
  stand in another relative order, one `layer-field` with field `order`. Ordinals are positions and are
  not compared.
- **Lens property.** Level 7 leaves out the footprint field `fenolite.path` (`LENS_FIELDS`): the build
  writes it as the lens key; it is not design.
- **Opaque items.** `verify-source` counts the opaque root items of each side by kind (the heads the
  import's coverage scan names: `teardrop`, `group`, `generated`, `image`…) and adds one level-7
  `opaque-count` per kind whose counts differ (`where` `board:opaque:<kind>`, `a` and `b` the counts). The
  equivalence package names no backend, so the cli computes the counts and adds the differences before the
  accepted rules apply. A board without its 165 teardrops fails until the difference is accepted.
- **One project.** `--against x.kicad_pro` (or a folder that resolves to one project) reads and records
  only `x.kicad_pro`, `x.kicad_pcb`, `x.kicad_dru` and the sheet tree of `x.kicad_sch`
  (`sch.sheet_files`); level 8 renders only those sheets.

### 6. Bottom-side angles (issue 6)

- A bottom footprint is placed with local angle `φ` as `(−φ + θ) mod 360°` (`embed._angles`); the derive
  turned a stored angle back as `stored − θ` on both sides. On the bottom it is now `θ − stored`, the
  inverse, for pads, properties and texts. R39 of `video` (bottom, θ = 0, Reference at 270°) gives a
  library angle of 90° and builds back to 270°.

### 7. Level S and the gate (issue 10)

- `verify-source` keeps skipping level S with `drawn-unavailable` and now records the reasons:
  `fidelity.proof.skipped` maps each skipped level to its reason (`{"S": "drawn-unavailable"}`).
- The library gate (c0279) accepts a level `skipped` only with a recorded reason other than `build-failed`;
  the derived result is unchanged (`pass`, `pass-with-accepted`) and lists the skipped levels.
- **How it is lifted.** c0276's `extract` exists; level S needs c0278 task 2.4 (`compare_drawn`) and the
  import of the drawn schematic (c0275 phase "drawn schematic"). When both land, `verify-source` runs level
  S for a board whose build has a drawn schematic, the reason `drawn-unavailable` disappears, and the gate
  then fails a skipped S on such a board.

### 8. Replayable steps (issue 12)

- A plan id hashes the working folder (`cli/plans.py`), so `--confirm --plan ID` cannot replay elsewhere,
  by design (a plan is a reviewed local act). A recorded step never holds `--plan`: a writing step is
  recorded with `--confirm` alone, which runs the command and writes the same bytes with the same inputs
  and `--timestamp`. `library audit` refuses a step holding `--plan`; `replay` runs steps as recorded.

### 9. Issue 11 (investigated, 2026-10-30, demos of `kicad/kicad:10.0.6`)

- **J2 on the edge** is upstream geometry: the board's top edge is at y = 93.55 mm and the pads of J2
  touch it. KiCad 10.0.6 `pcb drc` on the demo reports 12 `copper_edge_clearance` for J2 and 16 for J1
  (actual 0 mm), as Fenolite's guard does. The build places J2 and the outline exactly as upstream.
- **J1** is left out (`footprint`) because its pads carry `chamfer` on a bottom footprint and the flip does
  not cover `chamfer` (`embed.FLIP_UNSUPPORTED`). Mirroring chamfer corners is a follow-up (open question 3).
- **Commands.** `docker run --rm kicad/kicad:10.0.6 kicad-cli pcb drc --format json --severity-all --units mm
  RoyalBlue54L-Feather.kicad_pcb` on a copy of `/usr/share/kicad/demos/royalblue54L_feather` (28
  `copper_edge_clearance`, 183 `drill_out_of_range`, 13 `clearance`); `fenolite import … --allow-lossy` then
  `fenolite build out/design.py --copper-check warn`, and a comparison of the `Edge.Cuts` items and of the J2
  placement of both boards (equal); `library.not-local` names J1 in the import's issues.

### 10. The demos after this change (temporary folder, demos of `kicad/kicad:10.0.6`)

- `video`: levels 1, 2, 4, 5, 6 `equal` (level 2 was `differs`: J4 pads `0`); level 7 holds 22
  `graphic-field` (the 0.2032 mm outline, reported as `outline-width`), 2 `dimension-missing`, 1
  `text-missing`; no `field-pose` (R39 and `fenolite.path` are gone).
- `kit-dev-coldfire-xilinx_5213`: level 6 holds 2 `layer-missing` (`Eco1.User`, `Eco2.User`, reported as
  `layer-table`) instead of 14 ordinal differences, and 2 `stackup-field` (silkscreen material, reported).
- `cm5_minima`: builds in copy mode and every level runs. Level 7 keeps 106 `field-pose` of the instances' own
  properties (`Part Description`, `LCSC`, `Field4`…), which the build places with default poses: instance
  field placements belong to c0277 ("Not yet" of `docs/import.md`), and 2 `opaque-count` (15 `generated`, 4
  `group`).

## Codes introduced

| code | severity | when |
|---|---|---|
| `equiv.layer-field` | error | level 6: a layer of one name has another kind, or the layers stand in another order |
| `equiv.graphic-field` | error | level 7: a matched graphic differs in width |
| `equiv.opaque-count` | error | level 7: the opaque root items of a kind differ in count |

No new `FEN-` code; no new `fidelity.*` or `import.*` code (the two unexpressed kinds use
`import.item-unexpressed`).

## Hypotheses registered by this change

| id | statement | settled by |
|---|---|---|
| `H-K-COPPER-EPSILON` | KiCad's DRC reports a copper clearance only below the value in force minus 500 nm, for every pair kind and source, the class pair gap included | `tests/kicad/copper/test_drc_tolerance.py` in the `kicad-9` and `kicad-10` jobs |

## Files

- Changed: `cli/cmd_verify_source.py`, `cli/cmd_build.py`, `cli/cmd_import.py`, `importer/provenance.py`,
  `importer/vendor.py`, `importer/coverage.py`, `importer/emit/design.py`, `checks/copper.py`,
  `backends/base.py`, `backends/kicad/copperrules.py`, `backends/kicad/embed.py`,
  `checks/equivalence/{levels,rules,shapes,model}.py`, `cli/data/explain.toml`, schemas, `docs/import.md`,
  `docs/fidelity.md`, `docs/equivalence.md`, `docs/formats/kicad/copper.md`, `docs/hypotheses.md`,
  `docs/cli-contract.md`, the agent guide page `checks`, `CHANGELOG.md`.
- New: `fenolite.importer.provenance.copy_mode`, `tests/kicad/copper/test_drc_tolerance.py`, regression
  tests under `tests/unit/`.

## Evidence level per behaviour

| behaviour | level before merge |
|---|---|
| KiCad's 500 nm tolerance | `KICAD-VERIFIED (10.0.x)` locally; the CI job confirms; 9.0.x `INFERRED` |
| copy mode, pads on no net, losses, proof fixes, derive angles | `INFERRED`, hermetic regression tests |

## Risks / Trade-offs

- **Copy mode hides real errors in a copy.** They stay listed as warnings; `"copy": false` restores the
  refusal; a hand-written script is never a copy.
- **Fewer symbol pins** changes the vendored symbols of existing library boards; their replay gives new
  bytes once (c0279's replay records the Fenolite version).

## Open Questions

1. Should `fenolite check` also read copy mode? Recommended: no, `check` judges, it never refuses a write.
   Decided 2026-10-30: no.
2. An exact arc distance in the copper check, so the arc band no longer reports gaps KiCad accepts?
   Recommended: a later change with its own parity rows. Decided 2026-10-30: later.
3. Mirror pad chamfer corners in the bottom flip, so footprints like J1 of `royalblue54L_feather` import?
   Recommended: a later change with a KiCad oracle row. Decided 2026-10-30: later.
4. Is the tolerance the same on 9.0.x? Recommended: assume 500 nm (`copper-boundary-1nm` absent and
   `-1um` present are recorded for 9.0.9) and confirm in the `kicad-9` job. Decided 2026-10-30: as
   recommended.
