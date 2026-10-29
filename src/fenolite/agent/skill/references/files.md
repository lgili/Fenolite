---
topic: files
title: Reading, comparing and undoing
summary: Read a file Fenolite did not write, tell whether editing it is safe, compare two files or two designs, and undo a confirmed write.
---

# Reading, comparing and undoing

The commands of this page read files and answer. None runs a tool unless the page says so, and only
`fmt`, `convert`, `restore`, `view --export` and `diff --three-way` write.

## What is in a file

```fenolite-cmd
fenolite inspect blink/build/blink.kicad_pcb --json
fenolite inspect blink/build/blink.kicad_sch --json
fenolite inspect blink/altium/blink.PcbDoc --streams --json
```

`inspect FILE` reads a KiCad board, footprint, symbol library, schematic or drawing sheet, or an Altium
document, and reports its `kind`, its `format_version`, the KiCad `major` that wrote it, a `status`
(`supported`, or why it is not) and `counts`: footprints, pads, nets, tracks, vias, zones. Start here
with any file you are handed. `--streams` lists the streams of an Altium compound file.

For more than counts, `net`, `pads`, `region` and `neighbors` (pages `routing`, `placement`) read any
KiCad board. To look at a board or an Altium sheet, or at every one of a project, without its tool:

```fenolite-cmd
fenolite view blink/altium/blink.PrjPcb --json
fenolite view blink/altium/blink.PrjPcb --doc blink.SchDoc --json
fenolite view blink/build/blink.kicad_pcb --export blink/views/board.html --dry-run --json
fenolite view blink/build/blink.kicad_pcb --check checks.json --report conversion.json --report fabrication.json --json
fenolite view blink/build/blink.kicad_pcb --serve --run-timeout 900 --no-browser --port 0
fenolite view blink/build/blink.kicad_pcb --serve --no-run --no-browser
fenolite view blink/build/blink.kicad_pcb --serve --allow-actions --no-browser
fenolite view blink/build/blink.kicad_pcb --roles run --export blink/views/roles.html --dry-run --json
```

`view` replies with the project's documents and a summary of one board, or of the one `--doc` names;
`--compare OLD` draws what changed since OLD (a board or sheet) and counts it in `result.compare`; `--variant NAME` shows an Altium variant; `--check FILE|run` draws `check` findings and counts them in `result.check`; `--select REF` opens at a part or net; `--marks FILE` lists a person's review marks (`fenolite.review.v0`) in `result.marks`; `--theme` takes a KiCad colour theme; `--export` plans one HTML page that a person opens, and `--serve`
(for a person, not an agent) serves it live. A served page can run `check`, `analyze`, `ready` and
`equivalent` itself, read-only, one at a time, stopped after `--run-timeout SECONDS` (600); `--no-run`
serves recorded results only, and `result.serve.runs` counts the runs by final state.
`--allow-actions` lets the person write through the page: fill, tidy, silk, test points, DRC waivers,
moves, exports and BOM, each a reviewed plan confirmed with `--confirm --plan`; `result.serve.writes`
lists the receipts, and `fenolite restore` undoes one. `--roles FILE|run` draws the net roles of `fenolite
roles BOARD --check` on each board (role colours, loops, Kelvin pairs, role findings) and counts them in
`result.roles`; a served page with `--allow-actions` can confirm inferred roles as a reviewed plan.

`result.review` and the page's Review panel distinguish not-run, passed, failed and limited stages.
`--report FILE` loads a recorded convert/export reply, once per command; use `--check` for checks.
Loading does not run the operation. Missing/mismatched input hashes remain historical and limited;
a matching hash binds only the named document. Original hints and Locate support reviewing findings,
not marking them fixed. Export generation alone does not attest successful readback or fabrication readiness.

## Is it safe to edit this file?

```fenolite-cmd
fenolite roundtrip blink/build/blink.kicad_pcb --json
fenolite roundtrip blink/build/blink.kicad_pcb --level rt0 --json
```

Before Fenolite changes a file it did not write, ask `roundtrip`, which writes the file back in memory
only:

- `rt0`: parsing the file, printing it and parsing it again gives an equal tree;
- `rt1` (the default): also, Fenolite's rebuild of the board or schematic gives an equal tree, design
  and unmodelled content;
- `rt2`: also, KiCad's own checks give the same findings for the file and for Fenolite's copy of it
  (a project, with `kicad-cli`).

`result.level` is the highest level that holds. Exit 5 with `roundtrip.failed` (`where`: the first
difference) means the write would change the file: edit it in KiCad, not with Fenolite.

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

## What changed between two files?

```fenolite-cmd
fenolite diff blink/build/blink.kicad_pcb blink/other/blink.kicad_pcb --json
fenolite diff blink/build blink/other --json
fenolite diff blink/build/blink.kicad_pcb blink/other/blink.kicad_pcb --view tree --json
```

`diff A B` compares two boards, footprint files, symbol libraries, built projects (their `.fenolite/`
designs) or Altium files by meaning: `result.equal`, a `summary` per kind and `differences`, each with a
`path` and a `change` (a moved footprint is one change). `--view tree` gives the `first_difference` of
the two trees. It exits 0 either way: read `result.equal`.

```fenolite-cmd
fenolite diff blink/build/blink.kicad_pcb blink/routed/blink.kicad_pcb --allow track,via,arc --json
fenolite diff blink/base.kicad_pcb blink/ours.kicad_pcb --three-way blink/theirs.kicad_pcb --out blink/merged.kicad_pcb --dry-run --json
fenolite diff blink/altium/blink.PcbDoc blink/saved/blink.PcbDoc --view records --json
```

- `--allow KINDS` gates the difference: each change of another kind is a `diff.not-allowed` error (exit
  5) naming its path. Use it after a step that should only route, to prove that nothing else moved.
- `--three-way THEIRS --out FILE` plans `THEIRS` with the changes from `A` to `B` applied, item by item
  (KiCad boards only). An item that `THEIRS` changed too is `diff.conflict` and nothing is written: ask
  the owner, never pick a side. `diff.unmergeable` means the boards are of two KiCad versions.
- In the records view, records that differ only in the spelling of a value (`10mil` and `10.0mil`) are
  counted in `result.resave` and left out of `differences`: a plain save, not an edit.

## Are two designs equivalent?

```fenolite-cmd
fenolite equivalent blink/build blink/other --json
fenolite equivalent blink/build blink/other --level 2 --json
fenolite equivalent blink/build blink/altium/blink.PrjPcb --frame relative --json
```

`equivalent A B` compares level by level (1 components, 2 netlist, 3 footprints, 4 placement, 5
routing), also a KiCad project with an Altium one, up to the highest level both hold (`--level 2`: the
circuits only). Exit 0 with `result.equivalent` true, or exit 5 with one `equiv.*` issue per difference,
at a reference, a pin or a net. `--tolerance-nm N`, `--frame relative` (one translation removed) and
`--ignore-ref GLOB` loosen it. With two paths it runs no tool.

## Converting a project

```fenolite-cmd
fenolite convert blink/build --to altium --out blink/altium --dry-run --json
```

`result.report` counts what is written, changed or lost per kind and reason. A lost pad, copper or
fitted flag needs `--allow-lossy` (exit 7); an unexplained difference exits 5.

## The canonical print

```fenolite-cmd
fenolite fmt blink/build/blink.kicad_pcb --check --json
fenolite fmt blink/build/blink.kicad_pcb --dry-run --json
```

`fmt FILE --check` says whether a KiCad file is in Fenolite's canonical print (`result.formatted`) and
writes nothing; a file that is not gives `fmt.would-change` and exit 5. `fmt FILE --confirm` rewrites
it in that print: the content stays and only the layout changes. It is not KiCad's formatter: KiCad may
lay the file out again when it saves it.

## Undoing a confirmed write

Every confirmed write returns a `receipt` in its envelope: each written file with its SHA-256, and
`undo`, which names the backups of the files it replaced. Keep the envelope of a write you may want to
take back; write it to a file as the command prints it.

```fenolite-cmd
fenolite restore blink/last-write.json --dry-run --json
fenolite restore blink/last-write.json --confirm --json
```

`restore ENVELOPE` puts the backups of that write back (`--in DIR`: the folder it ran in). It refuses
when a written file changed since (`restore.changed-since`), never deletes a file the write created
(`restore.kept`), and has nothing to do when `receipt.undo` is `null` (`--no-backup`). Its own receipt
undoes it.

Read next: `checks`, `altium`, `recovery`.
