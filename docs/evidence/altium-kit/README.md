# docs/evidence/altium-kit

The publication edition `2026-10-13-87c930fa` was prepared on 2026-10-14 and
passes 32 steps. It preserves the historical form observations while repeating
native saves in a neutral namespace; it is not a complete fresh replay.
See [its provenance and privacy review](2026-10-13-87c930fa-publication.md).
It is published as [supplemental evidence for v0.4.0](https://github.com/lgili/Fenolite/releases/download/v0.4.0/altium-kit-2026-10-13-87c930fa.zip),
with its downloaded digest and size verified. Its 27 passing candidates are now
labelled with the committed run, archive digest and typed-form qualifiers.
See [the remaining hypothesis inventory](2026-10-14-graduation-inventory.md).

The run records of the Altium verification kit (`docs/altium-kit.md`), one JSON file per run, named
`<run id>.json` (`<date>-<first 8 hex digits of the archive digest>`), with the schema
`fenolite.altium-kit-run.v0`.

- A record is written by `fenolite kit record DIR --out <repository> --confirm` and is never edited after
  it is committed. A second run is a second file.
- A record holds the kit digest, Fenolite's version, the Altium version, the operating system family, the
  outcome of every step, the verdict of every hypothesis, and the SHA-256 and size of every result file and
  of the archive. It holds no path outside the kit, no user name and no machine name.
- The archive of a run (`results.zip`) is not in the repository. It is an asset of the GitHub release that
  the run supports, named `altium-kit-<run id>.zip`; the record names it by digest and size, so anyone can
  match a published archive.
- A register row carries `ALTIUM-VERIFIED(kit; AD <major>.<minor>; <date>; <run id>)` only while a record
  here holds a passing verdict for it and the kit of that run is the kit the tree builds
  (`fenolite kit status` lists the runs and the stale rows).

Three partial native runs are recorded for 2026-10-13, in Altium Designer 26.5
on Windows: `2026-10-13-61513e18` (8 passed steps) and
`2026-10-13-e8794749` (26 passed steps, no failures, 6 pending), and
`2026-10-13-fccaa526` (3 passed steps, no failures, 29 pending) on the newly
generated kit after the full-library-update repair. The older two runs precede
the library change; their digests and verdicts remain historical.
A fourth run, `2026-10-13-462b38ba`, completes the corrected current kit:
32 passed steps, zero failures and zero pending. The archive digest is
`462b38ba3cc4812ddeea626865c8c097e50f0ed9f2473dc0f79a7455f80a4b93`
(1236513 bytes). The broader legacy/Part T/Viewer campaign remains incomplete.
The original native archives remain in ignored local storage and unpublished;
the reviewed publication derivative is linked above.
See [the acceptance campaign](../altium-native-acceptance.md)
for measured scopes, the original failed save and the remaining work.

Closure reconciliation, 2026-10-13 (c0091): the completed current run is
committed and a fresh `kit verify` passes. `kit status` lists four records,
no stale rows and no problems. This satisfies c0091's first-run proof.
Archive publication remains c0092 task 3.1; no write kind graduates merely
because this kit implementation is archived. The original native result
folder still reports privacy findings separately from its passing step verdict.

## Kit run of 2026-11-05 (c0385)

A Claude agent ran this kit at the maintainer's request (delegation of 2026-11-04) on 2026-11-05 (S-1590).
It is not the maintainer's own run. Altium Designer 24.5.2.23 (Trial), as `Client.GetProductVersion`
reports it, ran in the maintainer's Parallels Windows VM. c0385 renumbered the DIP-8 land, so the run
`2026-10-13-87c930fa` was stale for the samples `flat`, `libs`, `routed` and `board6`. This run repeats the
steps of those four samples, and it is recorded as `2026-11-05-e28d0bb1.json`.

- Kit: built at `7e0c4ba8` with `fenolite kit build` (seed 0, timestamp `2026-01-01T00:00:00Z`), Fenolite
  `0.7.0.dev0`. Kit digest `9d7e289915e57060ee95b24dd4b02428e6d35e2dfe95fce1df4573aee5af88ba`, script
  `685ab54f…`, samples `flat` `d06a59a5…`, `libs` `d49ef8ad…`, `routed` `3fc10dcb…`, `board6` `954b4d4d…`.
- Steps run: K1.1–K1.6, K1.8, K2.1, K2.3–K2.5, K3.1, K3.2, K4.1–K4.4, K5.1–K5.5, K6.1, K7.1, K7.2, K8.2,
  K8.3, K9.1 and K9.2. K1.7 and K2.2 (sample `tree`) were run too, because `H-A-KIT-COMPILE`,
  `H-A-KIT-RESAVE` and `H-A-WRITE-SCHDOC` also name those steps. `kit verify`: 31 steps pass, none fail,
  19 are skipped (`pour`, `pour4`, `slots` and K8.1, which keep the old run). 24 of the 25 stale rows get
  this run's label. So does `H-A-SCHX-TREE`, whose `tree` steps this run also passed. The conformance
  matrix's kit scope (`claims.KIT_SOURCE`) now names this run.
- `H-A-KIT-SCRIPT` is skipped. For each sample, the kit script compiles the project and writes
  `results/<sample>/messages.txt`. Its first append to `results/script.log`, a file that does not exist
  yet, then raises an `EInOutError` dialog ("The specified file was not found"), and the script pauses.
  Run » Run did not finish it, and neither did OK followed by Run » Stop, so no `script.log` exists. The
  compile steps K2.1 and K2.3–K2.5 therefore count as manual steps. By the coordinator's decision of 2026-11-05 (maintainer's
  delegation of 2026-11-04), the row goes back to `INFERRED`, its level before run `87c930fa`; c0389 task 6.1
  holds the script fix and the K2 rerun.
- Observed values: K3.2 = 0 (the change order held 12 changes, all done); K4.1 true (three Clearance
  rules and two Width rules as listed); K4.3 = 1, K4.4 = 1. `drc.html` is Altium's own HTML report:
  10 violations in all. "Create Report File" was off by default and was switched on. K5.2 = 6 copper
  layers. K5.3: through, blind Top–Mid Layer 1, and buried Mid Layer 1–Internal Plane 1. K5.4: Via and
  Track checked; Copper, SMD Pad and TH Pad not. K5.5: the four texts as listed, `Tensão 5 V` saved as
  0xE3. K7.1 true, with no message; the Schematic Prints output names `routed.SchDoc` as its source, not
  `[Project]`. K7.2: 23 output files. The BOM output reported "Files Generated: 0". K8.2 `Flat`,
  K8.3 `B`, K9.2 = 0.
- K1.8 is typed `false`. No sample document showed a repair, upgrade or error dialog on opening or saving.
  The agent's own mistake caused one error: a Save As went to the script editor's document, so the first
  K1.1 save said "a file is already open with that path". The wrong file was removed, and the retry
  saved without a message.
- `kit verify` reports 26 privacy findings: VM paths in the saved boards and in `drc.html`, and the
  VM's home folder in `eco.PcbDoc`. The archive (`e28d0bb1…`, 2087805 bytes) stays in local storage,
  unpublished. Nothing was copied from another project. Every document was closed with Don't Save after
  its result was written.

## Author report of 2026-10-07 (opening only)

On 2026-10-07 the author reported that the projects of the kit built from `5adad054` opened in Altium
Designer 26 with no problem. That is not a kit run: no step was carried out, no file that Altium saved has
been received, nothing was recorded with `fenolite kit record`, and no `H-A-KIT-*` row moves. The same
report is on `docs/evidence/altium-schematic.md` and `docs/evidence/altium-pcb.md`.

2026-10-07 (change c0134): catalog symbols that the kit's five projects place changed (hidden pin names,
larger blocks), so the kit that the tree builds is no longer the kit of `5adad054` byte for byte: the
schematic and the schematic library of each project differ, the boards do not. Nobody has opened it.

## Returned kit folder of 2026-10-07

The author returned the kit folder the same day with saved documents of three samples and an empty form.
It is not a recorded run: `fenolite kit verify` fails every step of the sample `flat`, because step K1.5
made Altium rewrite the kit's own project file; with that file restored, five steps pass and none fails on
a difference; `fenolite kit record` would refuse the folder. No `H-A-KIT-*` row moves. The account is on
`docs/evidence/altium-pcb.md` ("Returned folders of 2026-10-07"); the kit's own defects it showed are
change c0139.

## The maintainer's decision of 2026-10-08 for 0.3.0, and the revalidation it owes

On 2026-10-08 the maintainer decided that the kit did not change since his run of 2026-10-07 and that it is
accepted as validated by that run for the release 0.3.0 (S-0615). The kit run of session 2 (Part K) was not
made.

- **What the decision is.** An exception, by the maintainer, to the condition of change c0092 that a write
  kind needs `ALTIUM-VERIFIED(kit)` from a recorded run that is not stale. It is recorded in the release
  record of 0.3.0 (`docs/release/v0.3.md`) and under task 3.1 of c0092.
- **What it is not.** No run record is written, no run id or archive digest exists, and no row carries
  `ALTIUM-VERIFIED(kit)`: the run of 2026-10-07 was refused by `fenolite kit verify` as returned (above), its
  form was empty, and `fenolite kit record` would refuse the folder. No `H-A-KIT-*` row moves.
- **What this page also records.** The kit that the tree builds is not the kit of the folder of 2026-10-07
  byte for byte: since then change c0134 changed the pin texts of the catalog symbols the samples place,
  change c0144 added the pin-map records of the LED `D1` to the schematics of four samples, and change c0148
  sets bit 0x20 on every pin of every schematic document and schematic library it writes. The boards are
  unchanged by the three.
- **Revalidation, owed after 0.3.0.** The kit is to be run again in Altium on the kit that the tree builds,
  verified with `fenolite kit verify` and recorded with `fenolite kit record --confirm`, with its archive
  published as this page says. That recorded run is also the revalidation of change c0148 (the pin bits of
  every schematic document and schematic library) in the kit's own steps. The exception holds for 0.3.0
  only; after it, the kit condition of c0092 asks for this recorded run. In 0.3.0 no write kind left
  `experimental` in any case: each fails another condition of the rule (`docs/release/v0.3.md`,
  "Graduation of the Altium write").
