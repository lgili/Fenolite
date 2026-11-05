# Fidelity evidence

Level 8 is **INFERRED**: Fenolite renders both sides. No native plot agreement is claimed.
`H-K-FID-PLOT-AGREE` and `H-K-FID-ZONE-OUTLINE` retain their measured levels.

## Preparation — 2026-11-01

The infrastructure checkpoint used `0.7.0.dev0`, base `eabbeeef38f54c0ff14ac2cbb0bd2234da464ff1`.
The actual strict census below uses signed source `613b6f1b98e1780bb04442afc0f3dbd883b5e644`.
The manifest selects 24 allow-listed demo boards and their 150 declared inputs at the two registered refs.
Inputs remain fetched external descriptors; generated code and projects stay in the test temporary folder.
No real board or converted code is committed here. NC/ND licences and restricted variants are excluded.

The initial sensor run on the infrastructure base reproduced 64 level-S differences and one presentation
difference, with levels 1–7 equal. After source-sheet and embedded-symbol preservation in prerequisite
`81f3bb1d`, the strict authored sensor/hierarchy/bus/Repeat controls pass all nine levels. Those former
differences were resolved by preserving source content, without acceptance, a level subset or tolerance.
The authored fixture is not a GUI save. Native KiCad upgrade/refill and exact-head CI proofs remain open.

## Corpus status

`accepted.toml` separates measured count baselines from explicit pending rows. Pending means **no reviewed baseline**, not equal or accepted; raw observations are recorded separately below.
The corpus test reports a pending skip until a reviewed baseline exists; it grants no task-6.2 or corpus-evidence verdict.
Measured rows compare every raw difference count in both directions: a larger count fails; a smaller count fails with a request to lower the entry.
The `fidelity-demos` census records only row ids, counts by level/kind, statuses and elapsed seconds. No source values or names enter the count baseline.

<!-- fidelity-corpus:begin -->
| row | licence | equal levels | counts | attribution | version | date | seconds |
|---|---|---|---|---|---|---|---|
| kicad-demo-10-0-6-pcb-01 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-02 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 24.42 |
| kicad-demo-10-0-6-pcb-03 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 3.819 |
| kicad-demo-10-0-6-pcb-04 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 4.288 |
| kicad-demo-10-0-6-pcb-05 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-06 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-07 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-08 | CC-BY-SA-4.0 | 1, 2, 3, 4, 6, 7, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 1.693 |
| kicad-demo-10-0-6-pcb-09 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-10 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 43.924 |
| kicad-demo-10-0-6-pcb-11 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-12 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 15.712 |
| kicad-demo-10-0-6-pcb-13 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-14 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 2.806 |
| kicad-demo-10-0-6-pcb-15 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 7.234 |
| kicad-demo-10-0-6-pcb-16 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 84.501 |
| kicad-demo-10-0-6-pcb-17 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-18 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-9-0-9-1-pcb-01 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-9-0-9-1-pcb-02 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-9-0-9-1-pcb-03 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 13.545 |
| kicad-demo-9-0-9-1-pcb-04 | CC-BY-SA-4.0 | not baselined | not baselined | undecided | — | — | — |
| kicad-demo-9-0-9-1-pcb-05 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 0.723 |
| kicad-demo-9-0-9-1-pcb-06 | CC-BY-SA-4.0 | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | fenolite | 0.7.0.dev0 | 2026-11-05 | 16.239 |
<!-- fidelity-corpus:end -->

Twelve rows above have a measured zero-count baseline, re-run on 2026-11-05 (c0401, "Attribution — 2026-11-05" below); pcb-14 (10.0.6) and pcb-05 (9.0.9.1) joined after their Fenolite causes were fixed. The other 12 have no reviewed all-level baseline. A complete run must provide actual counts, timing, version/date and a scoped attribution before moving a row out of pending.
The GUI-save and native application requirements remain open; an authored writer/readback test cannot establish them.

## Actual strict probe — 2026-11-01

The local probe used signed source `613b6f1b98e1780bb04442afc0f3dbd883b5e644`, every declared
project input and zero geometry tolerances. It ran the strict import/build/verify pipeline with no
lossy-import, acceptance or level-subset flag. The run failed 22 cases and skipped the two heavy
inputs in 186.16 seconds. Its 19 import refusals comprise 13 `FEN-3004` validation refusals and six
`FEN-7001` unexpressed-content refusals. Two inputs reached unequal comparisons; one manifest-declared
malformed input was refused before comparison. This is **not a passing fidelity or CI proof**.

Both compared inputs are equal at S. Their remaining counts are recorded without assigning a cause:
one has seven level-3 footprint-name differences and one level-8 render-pixels difference; the other
has five level-7 graphic-missing differences and one level-8 render-pixels difference. Attribution
remains undecided, and all 24 acceptance baselines remain pending review.

The value-free [observations](../../tests/kicad/fidelity/observed.json) retain every level/kind count,
refusal code and actual timing. No result is promoted or accepted. Rows where import/input was refused
have no comparison counts; they are not zero counts. Native application and exact-head CI gates remain open.

<!-- fidelity-observed:begin -->
| row | outcome | equal levels | raw differences | attribution | version | date | seconds |
|---|---|---|---|---|---|---|---|
| kicad-demo-10-0-6-pcb-01 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 11.171 |
| kicad-demo-10-0-6-pcb-02 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 3.431 |
| kicad-demo-10-0-6-pcb-03 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 0.749 |
| kicad-demo-10-0-6-pcb-04 | compared | 1, 2, 4, 5, 6, 7, S | 3:footprint-name=7, 8:render-pixels=1 | undecided | 0.7.0.dev0 | 2026-11-01 | 6.36 |
| kicad-demo-10-0-6-pcb-05 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 2.228 |
| kicad-demo-10-0-6-pcb-06 | heavy-skipped | not compared | not compared | undecided | — | — | — |
| kicad-demo-10-0-6-pcb-07 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 9.075 |
| kicad-demo-10-0-6-pcb-08 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 0.216 |
| kicad-demo-10-0-6-pcb-09 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 8.963 |
| kicad-demo-10-0-6-pcb-10 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 5.233 |
| kicad-demo-10-0-6-pcb-11 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 12.699 |
| kicad-demo-10-0-6-pcb-12 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 4.815 |
| kicad-demo-10-0-6-pcb-13 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 25.911 |
| kicad-demo-10-0-6-pcb-14 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 0.545 |
| kicad-demo-10-0-6-pcb-15 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 1.062 |
| kicad-demo-10-0-6-pcb-16 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 48.974 |
| kicad-demo-10-0-6-pcb-17 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 25.755 |
| kicad-demo-10-0-6-pcb-18 | heavy-skipped | not compared | not compared | undecided | — | — | — |
| kicad-demo-9-0-9-1-pcb-01 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 0.558 |
| kicad-demo-9-0-9-1-pcb-02 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 5.467 |
| kicad-demo-9-0-9-1-pcb-03 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 4.359 |
| kicad-demo-9-0-9-1-pcb-04 | input-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 0.09 |
| kicad-demo-9-0-9-1-pcb-05 | compared | 1, 2, 3, 4, 5, 6, S | 7:graphic-missing=5, 8:render-pixels=1 | undecided | 0.7.0.dev0 | 2026-11-01 | 2.319 |
| kicad-demo-9-0-9-1-pcb-06 | import-refused | not compared | not compared | undecided | 0.7.0.dev0 | 2026-11-01 | 4.848 |
<!-- fidelity-observed:end -->

## Scoped outline audit — 2026-11-01

The six former `outline-width` refusals were rerun on signed
`888ca838fa41b1b9bc16e4039ec55e233400b1e5` (`0.7.0.dev0`) with the same declared inputs and strict
import/build/verify pipeline. No lossy permission, acceptance, tolerance or level subset was added.
All six got past their width refusal, but the run still **failed six cases in 232.69 seconds**:
one import self-check refused repeated-sheet footprint variants, and five comparisons differed.
This is a scoped measurement, not a new 24-row census, accepted baseline or passing fidelity proof.

| row | outcome | equal levels | remaining raw differences | seconds |
|---|---|---|---|---:|
| kicad-demo-10-0-6-pcb-02 | import-refused (`FEN-5001`, `drawn.repeated-value-differs`) | not compared | not compared | 13.352 |
| kicad-demo-10-0-6-pcb-05 | compared, differs | 1, 2, 4, 5, 6, 7, S | 3:footprint-name=7, 8:render-pixels=1 | 66.213 |
| kicad-demo-10-0-6-pcb-08 | compared, differs; 5/S skipped | 1, 2, 4, 6, 7, 8 | 3:footprint-name=3 | 7.197 |
| kicad-demo-10-0-6-pcb-09 | compared, differs; S skipped | 1, 2, 4, 5, 6, 8 | 3:footprint-name=100, 7:field-pose=3101 | 118.225 |
| kicad-demo-10-0-6-pcb-14 | compared, differs | 1, 2, 3, 4, 6, S | 5:track-width=4, 7:graphic-missing=3, 8:render-pixels=1 | 8.214 |
| kicad-demo-9-0-9-1-pcb-01 | compared, differs | 1, 2, 4, 5, 6, S | 3:footprint-name=1, 7:opaque-count=1, 8:render-pixels=1 | 14.501 |

Skipped levels above retain the existing missing-side/routing reasons and are not equal. Difference
attribution remains undecided; no count is accepted. The historical observations and all 24 pending
ratchets above are unchanged. An authored CC0 line/arc project passes all nine levels after width
preservation, without acceptance. These local controls remain `INFERRED`; native application and
exact-head whole-batch/CI proof remain open.

## Strict census — 2026-11-04

The census reran every `rtf` root on `468d8a61` (`0.7.0.dev0`) with KiCad 10.0.6 on macOS. It used the
same strict import/build/verify pipeline, with no lossy permission, acceptance, tolerance or level subset.
It took 549.09 seconds over 24 rows, two of them heavy rows that were skipped. Ten rows had no difference at any level they
reached. Each of them is now a measured `[[row]]` of `accepted.toml` with `counts = {}`, so any new difference fails the
ratchet. Their seconds in the table above come from the corpus test run itself. Five rows differ and keep
`pending`, because the attribution of their differences is undecided. Five imports were refused, one
`verify-source` was refused, and the malformed input was refused before comparison. None of these is a zero count.
The corpus test then ran with the new ratchet: `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/fidelity -rA`
gave 11 passed (10 measured rows and the zone-outline probe) and 14 pending skips in 570.67 seconds, run serially.
This is a local measurement on the maintainer's Mac. It is not the kicad-10 CI job, and no level is raised.

| row | outcome | equal levels | raw differences | seconds |
|---|---|---|---|---:|
| kicad-demo-10-0-6-pcb-01 | import-refused (`FEN-5001`) | not compared | not compared | 12.587 |
| kicad-demo-10-0-6-pcb-02 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 22.9 |
| kicad-demo-10-0-6-pcb-03 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 4.432 |
| kicad-demo-10-0-6-pcb-04 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 4.64 |
| kicad-demo-10-0-6-pcb-05 | import-refused (`FEN-3004`) | not compared | not compared | 0.583 |
| kicad-demo-10-0-6-pcb-06 | heavy-skipped | not compared | not compared | 0.03 |
| kicad-demo-10-0-6-pcb-07 | import-refused (`FEN-5001`) | not compared | not compared | 10.891 |
| kicad-demo-10-0-6-pcb-08 | compared, equal; 5/S skipped | 1, 2, 3, 4, 6, 7, 8 | none | 1.496 |
| kicad-demo-10-0-6-pcb-09 | verify-source refused (`FEN-3004`) | not compared | not compared | 32.424 |
| kicad-demo-10-0-6-pcb-10 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 52.225 |
| kicad-demo-10-0-6-pcb-11 | import-refused (`FEN-5001`) | not compared | not compared | 17.192 |
| kicad-demo-10-0-6-pcb-12 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 24.172 |
| kicad-demo-10-0-6-pcb-13 | compared, differs | 1, 2, 3, 4, 5, 6, S, 8 | 7:opaque-count=1, 7:zone-field=1 | 90.403 |
| kicad-demo-10-0-6-pcb-14 | compared, differs | 1, 2, 3, 4, 6, 7, S, 8 | 5:track-width=4 | 4.316 |
| kicad-demo-10-0-6-pcb-15 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 11.009 |
| kicad-demo-10-0-6-pcb-16 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 139.083 |
| kicad-demo-10-0-6-pcb-17 | import-refused (`FEN-5001`) | not compared | not compared | 25.88 |
| kicad-demo-10-0-6-pcb-18 | heavy-skipped | not compared | not compared | 0.016 |
| kicad-demo-9-0-9-1-pcb-01 | compared, differs | 1, 2, 3, 4, 5, 6, S | 7:opaque-count=1, 8:render-pixels=1 | 3.94 |
| kicad-demo-9-0-9-1-pcb-02 | compared, differs | 1, 2, 3, 4, 5, 6, S, 8 | 7:opaque-count=1, 7:zone-field=1 | 29.943 |
| kicad-demo-9-0-9-1-pcb-03 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 25.565 |
| kicad-demo-9-0-9-1-pcb-04 | malformed input refused | not compared | not compared | 0.045 |
| kicad-demo-9-0-9-1-pcb-05 | compared, differs | 1, 2, 3, 4, 5, 6, S, 8 | 7:graphic-missing=5 | 1.118 |
| kicad-demo-9-0-9-1-pcb-06 | compared, equal | 1, 2, 3, 4, 5, 6, 7, S, 8 | none | 34.2 |

## Attribution — 2026-11-05 (c0401)

The rows the 2026-11-04 census left without a zero count were re-run on `origin/dev` `1169f10d` with KiCad
10.0.6 (macOS `kicad-cli`), through the same strict pipeline, with no acceptance, tolerance or level subset.
The counts matched the census. Each note names the level, the object and the evidence; the full table is in
`openspec/changes/c0401-fidelity-census-follow-up/design.md`. This is a local measurement, not the kicad-10
CI job, and no level is raised.

Differing rows (task 1.1):

- **kicad-demo-10-0-6-pcb-14**, 5:track-width=4 — **Fenolite, comparator.** Both boards hold the same
  coincident tracks (one 0.3 mm and two 0.29997 mm wide, same ends and net, on each copper side); strict
  matching paired equal keys in file order. Fixed by c0401 task 1.3; the row now has no difference at any level.
- **kicad-demo-9-0-9-1-pcb-05**, 7:graphic-missing=5 — **Fenolite, import/build.** The outline is one
  Edge.Cuts `gr_rect`; the import made it `board(outline=…)` and the build wrote four `gr_line`s. Fixed by
  c0401 task 1.4; the row now has no difference at any level.
- **kicad-demo-9-0-9-1-pcb-02**, 7:opaque-count=1 (teardrop), 7:zone-field=1 — **Fenolite, derived teardrop
  caches.** The import leaves out the 176 teardrop caches; the c0340 same-tool proof refills both sides with
  KiCad 10.0.6 and gets 178 caches each, of different exact geometry. Same mechanism as c0384's first
  finding; owned by c0384.
- **kicad-demo-9-0-9-1-pcb-01**, 7:opaque-count=1 (teardrop) — **Fenolite, proof scope.** The import leaves
  out 6 teardrop caches, and the c0340 proof refuses the board before running KiCad ("unqualified
  non-quarter parent pose": custom, rotated pads). It needs its own change.
- **kicad-demo-9-0-9-1-pcb-01**, 8:render-pixels=1 — **input inconsistency carried by a Fenolite model
  limit.** One symbol's `Footprint` field is empty and visible in the schematic while its board footprint is
  set; a `Part` holds one footprint, so the build writes the id into the field (872/37894 pixels). It needs
  its own change.
- **kicad-demo-10-0-6-pcb-13** stays with c0384.

Refused rows (task 2.1), each an intended refusal:

- **kicad-demo-10-0-6-pcb-01** (`FEN-5001`, `build.schematic-netlist-differs`) — **input.** KiCad 10.0.6's
  own netlist puts a connector's mounting pin on GND, but the board footprint has no pad of that number.
- **kicad-demo-10-0-6-pcb-11** (`FEN-5001`, same check) — **input.** KiCad 10.0.6's netlist puts one
  connector pin on GND; the board pad is `unconnected-(…)`: the board was not updated from the schematic.
- **kicad-demo-10-0-6-pcb-07** and **-17** (`FEN-5001`, `kicad.project.too-new-key`) — **input, mixed
  versions.** KiCad 9 board (20241229) and schematics (20250114) with a project resaved by KiCad 10; the
  self-check targets the board's major and refuses keys only 10.0 writes.
- **kicad-demo-10-0-6-pcb-05** (import `FEN-3004`) — **corpus.** The project declares a worksheet the
  manifest does not fetch.
- **kicad-demo-10-0-6-pcb-09** (verify-source `FEN-3004`) — **input.** The unrouted board has no project
  of its own stem, so one side has no native project context.

Heavy rows (task 2.2), measured locally with `FENOLITE_HEAVY=1` in 306 s, peak resident memory 1.95 GB:

- **kicad-demo-10-0-6-pcb-06** — import `FEN-7001` after 268.8 s: 24 dimension styles, 6 Dwgs.User drawings
  and 2 placement rule areas the DSL cannot express. It stays pending as a refusal.
- **kicad-demo-10-0-6-pcb-18** — import `FEN-3004` after 35.0 s: the project declares a worksheet the
  manifest does not fetch. It stays pending as a refusal.

The kicad-10 CI job sets `FENOLITE_HEAVY=1`, so both rows run there as soon as they leave `pending`.
