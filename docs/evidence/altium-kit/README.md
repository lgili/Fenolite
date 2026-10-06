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
