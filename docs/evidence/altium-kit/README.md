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
