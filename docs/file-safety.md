# File safety

Fenolite edits files that someone else owns: a board open in KiCad, a project in a synced folder, a copy
that still points at its old folder. These commands keep those files safe (change c0201). The contract of
each command is in `docs/cli-contract.md`.

```console
fenolite doctor --sessions project
fenolite snapshot project/board.kicad_pcb --out work --confirm
fenolite publish work --to project --receipt work/snapshot.json --dry-run
fenolite refs work --repoint C:/old/libs=C:/new/libs --dry-run
```

## Open files

KiCad keeps a lock file `~<file name>.lck` beside each file it holds open, and removes it on close (S-0828,
S-0829). `fenolite doctor --sessions PATH` lists those under `PATH`, a lock whose file is gone as `stale`,
and every writing command adds `safety.open-session` (warning) for each file of its plan that has one. A
save in KiCad would overwrite the write, or the write would be lost on KiCad's next save: close the file
first. Another tool's lock file is not detected, because no public source recorded here gives its name.

## Files kept only online

A sync client (OneDrive, iCloud Drive) may keep a file only online. Reading it makes the client download it,
and may block. Fenolite reads the attributes the operating system documents for such a file, never its
content: on Windows `FILE_ATTRIBUTE_OFFLINE`, `FILE_ATTRIBUTE_RECALL_ON_OPEN` or
`FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS` (S-0830), on macOS `SF_DATALESS` (S-0831). `snapshot`, `publish` and
`refs` stop before any read with `FEN-3007` (exit 3, retryable); `doctor --sessions` lists such files.

## A copy no save interrupted

`fenolite snapshot PATH --out DIR` copies a design file with its companions (the documents of its stem, the
library tables beside it, and what they name inside the folder: sheets, libraries, 3D models), or every
project file of a folder. It reads every file, then checks every hash again; a file saved in between is read
again, at most three times, and one that never settles is `safety.unstable` (nothing copied).
`DIR/snapshot.json` lists each file with its SHA-256.

## Putting the copy back

`fenolite publish SRC --to DST --receipt RECEIPT` replaces a file of `DST` only when its hash is the one the
receipt recorded: the `snapshot.json` of the copy, or the envelope of Fenolite's last write there. A file the
owner saved since is `safety.changed-since-receipt`, and nothing is written; with `--skip-changed` that
file stays and the others are written. New files are added, equal files are not written, nothing is
deleted, and every replaced file keeps its `.bak`.

## Paths a project holds

`fenolite refs PATH` lists the `uri` of each library table row, the `Sheetfile` of each sheet, the 3D model
paths of boards and footprints, the drawing sheets of a KiCad project, and each `DocumentPath` of an
Altium project, with whether each resolves inside the project. `--repoint OLD=NEW` rewrites the paths that
start with `OLD`, in the KiCad documents only, changing those atoms and nothing else.

The level is `INFERRED` (`H-G-SNAPSHOT-STABLE`, `H-G-PROJECT-REFS`, `H-K-PRO-LOCK`): `kicad-cli` opens no
editor, so no oracle run writes a lock file.
