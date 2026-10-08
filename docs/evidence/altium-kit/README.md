# docs/evidence/altium-kit

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

No run is recorded yet.

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
