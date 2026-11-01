---
topic: board-workflow
title: Working on CAD files that a person also edits
summary: Copies and versions, a SHA-256 before every write, files a person has open, references between files, parallel editors, and honest reports.
---

# Working on CAD files that a person also edits

A real board is seldom edited by one hand. Its owner opens it in a CAD tool and saves while you work,
and another agent may work on the same project. Each of these can silently undo the other's work. No
check reports the loss: the file is valid, it only holds the wrong state. The habits below prevent it.
Fenolite's own writes already follow some of them (reviewed plans, receipts, `restore`). The rest are
yours to keep.

## Before the first write

- **Know the master.** Ask which file is the master, which folder is yours, and who else writes.
  Write the answer into your notes. The master can change during a project, for example when the owner
  stops using one tool and continues in another. Ask again when the owner names a new folder.
- **Work on a copy** in a folder of your own. Name the folder with the date and a version
  (`board_2026-05-04_v3`). Edit the master in place only when the owner says so, for that write.
- **Read before you write.** `fenolite inspect` summarises a file. `fenolite roundtrip` says whether a
  file that Fenolite did not write survives a read and a write. A file that fails `roundtrip` is
  edited by its own tool, not by you.

```fenolite-cmd
fenolite inspect board/board.kicad_pcb --json
fenolite roundtrip board/board.kicad_pcb --json
```

## Every write

1. **Take a baseline.** Take the SHA-256 of every file that the write will replace. Keep the copy that
   you last delivered: it is the baseline of the owner's next edits.
2. **Compare again right before the write.** If a hash changed, a person or another agent saved the
   file. Stop. Read the new file and see what changed against your baseline (`fenolite diff`). Then
   make your change again on top of it. Never write over a file whose hash moved.
3. **Write through a reviewed plan.** Run `--dry-run` and read `result.plan`. Then write with
   `--confirm --plan ID`. `FEN-4002` means an input changed after your review. Review again; do not
   force the write.
4. **Keep the envelope** of every confirmed write. Its receipt lists each written file with its
   SHA-256, and `fenolite restore` puts the backups back.
5. **Name items by what they are.** Name each item by its kind, geometry and net (or a designator),
   not by its index in a list: indices shift after any deletion. Assert that exactly one item matches,
   and state the old value you expect. An edit that finds two items, or a different old value, stops.
6. **Make one step per version.** A version folder holds one coherent step, such as the placement of
   the power stage or the ground rework. A short note says what changed and why. When the owner rejects
   a step, the version before it is still whole.

```fenolite-cmd
fenolite diff delivered/board.kicad_pcb current/board.kicad_pcb --json
fenolite manifest board --no-check --dry-run --json
fenolite restore build/route-envelope.json --dry-run --json
fenolite diff base/board.kicad_pcb mine/board.kicad_pcb --three-way theirs/board.kicad_pcb --out merged/board.kicad_pcb --dry-run --json
```

## Long edit chains

- **Deliver every output and every revision in a new folder.** Never overwrite a delivered one. Before a
  clean-up, archive with a hash manifest, and move files to the trash instead of deleting them.
- **Build the board as a staged chain** of scripts. Each stage reads the file of the stage before and
  writes a new one, and the whole chain runs again after any change upstream. Make each stage
  idempotent: running it twice gives the same file. Make each stage fail loudly, never half-way.
- **Gate every update from the schematic with an expected-change table.** List what should change,
  compare it with what the update proposes, and stop on any difference (`diff --allow`).
- **Prove that each write changed only what was planned:** compare the written file with the file before
  it (`fenolite diff`).
- **A read-back is not a native open.** A file that Fenolite reads back losslessly can still fail in the
  CAD tool. In a long chain of offline edits, have the owner open and save an early result in the tool.
  Give the owner an ordered checklist for each step that only the tool can do. When the tool crashes on a
  file, bisect with variants that each hold a single change.
- **Pin the version of Fenolite** that a chain uses, and record it with the outputs.

## Edits made in KiCad

- **Edits in KiCad survive a build.** Values, footprints and positions are merged three ways against
  `fenolite-base.json`, and `edit.unrecorded` names each kept edit. Record them with `sync --to-source`
  in `edits.toml`, and commit it.
- **A change on both sides is a `sync.conflict`.** Nothing is written. Choose a side with `--take`,
  build, then sync.

```fenolite-cmd
fenolite build design.py --out build --take cad:R1#value --dry-run --json
fenolite sync design.py --out build --to-source --dry-run --json
```

## Files that a person has open

- **The open copy wins.** A CAD tool holds the file it opened in memory. When it saves, it writes that
  old copy over your new one, and neither side reports an error. After you rewrite a file that a
  person may have open, say so plainly: close it without saving, then open it again.
- **Write a new version folder** rather than replace a file that may be open. The owner opens the new
  folder when ready.
- **A window you cannot see is still open.** Do not assume that a GUI session is closed.

## Working on the owner's project

```fenolite-cmd
fenolite doctor --sessions project --json
fenolite snapshot project/board.kicad_pcb --out work --confirm --json
fenolite publish work --to project --receipt work/snapshot.json --dry-run --json
fenolite refs work --json
fenolite refs work --repoint C:/old/libs=C:/new/libs --dry-run --json
```

Do not edit the owner's files in place while they may be open:

1. `doctor --sessions` lists the files open in KiCad (`safety.open-session`) and the files a sync client
   keeps only online. Ask the owner to close them; every writing command repeats that warning for a file
   of its plan.
2. `snapshot` copies the board with its companions only when no save fell inside the copy, and writes
   `snapshot.json`. Work on the copy.
3. `publish` puts the copy back. It replaces a file only when its hash is still the one of
   `snapshot.json`. A file the owner saved since is `safety.changed-since-receipt`, and nothing is written:
   tell the owner, take a new snapshot, and do the edit again. Keep the envelope of the publish: it is the
   receipt of the next one.
4. `refs` lists the paths the documents hold. `refs.outside` means the copy still depends on another folder;
   `--repoint OLD=NEW` rewrites a prefix in the KiCad documents.

Exit 3 with `FEN-3007` means a file is kept only online: ask the owner to make the folder available offline.

## Files that point at each other

- **References break on a move.** A project points at its sheets, libraries, drawing documents and
  output jobs, and some tools store those references as absolute paths. After you copy or rename a
  folder, list every reference. Repoint each reference that still names the old place, or report it.
  A drawing that points at a board in the old folder prints the old board without any warning.
- **Decide which is master: the board or the library.** Once the board has been edited (silkscreen
  trimmed, 3D bodies placed, pads changed), the board is the master. Make the library from the board's
  footprints. Never push an older library onto the board: an update from the library undoes, part by
  part, every change made on the board.
- **Edit a third-party file carefully.** A file that Fenolite did not write may hold content that no
  reader understands, such as embedded models or settings. Change one kind of thing at a time, have the
  owner open the result in the CAD tool, and only then repeat the change on more parts. One bad record
  can stop the tool from saving.

## Parallel editors

- **One folder per editor.** When another agent or a person works on the same project at the same
  time, take a separate folder and say which one is yours. Do not merge their work into yours unasked,
  and never write into their folder. When asked, `diff --three-way` merges both editors' changes into
  one KiCad board through a plan, and stops on a conflict (`diff.conflict`).
- **Name what a version holds.** Before you hand a version over, say what it holds and what it does
  not hold. For example: "v5 has the new placement; the routing edits made this afternoon are not in it."

## What you report

- **Label what is not measured.** Label every synthetic, estimated or simulated result as such. A
  measurement against a configured value is not compliance, and a picture of a board is not a review.
- **Say what you did not check.** Write lines such as "Not opened in the CAD tool" or "Creepage not
  measured on the bottom side". A result that `fenolite check` judged below `KICAD-VERIFIED` is
  unconfirmed, and your report says so.
- **Keep a log** of every write: the date, the file, the hash before and after, what changed and why.
- **Never invent** a measurement, a limit, a clause of a standard, a signature or an approval. When a
  number is needed and nobody gave it, ask for it.
- **Propose before you apply.** Show a change as filled before-and-after pictures, apply it only after
  the owner approves, and never make the owner's design decisions: list them with their options.
- **Ask before you install or download a tool,** and before you commit or publish anything. Keep CAD
  files that are not yours out of version control.

## Typical failures

- **Ten files overwritten.** A quick "copy what changed" sent ten files to the shared project folder.
  The owner had saved all ten in the CAD tool an hour earlier, and the copy overwrote that work. Only
  the cloud drive's version history brought it back. Comparing each target with the last delivered
  copy would have skipped those ten files and reported them.
- **A window open for hours.** The owner had the board open in a CAD tool while scripts rewrote and
  routed it. A save from that window would have thrown the new routing away. The agent told the owner
  to close the window without saving and to open it again. It did not close the owner's tool itself.
- **A library update that undid a day's work.** The board's silkscreen and 3D bodies had been fixed on
  the board. Someone then ran "update from library" with the old library, and every part went back to
  its old form. The library had to be made from the board again.
- **A copied project that printed the old board.** A project folder was copied to a new version. Its
  drawing documents still held absolute paths to the old folder, so the new release printed the old
  board.

Read next: `board-review`, `files`, `recovery`.
