---
topic: files
title: Reading, comparing and undoing
summary: Read a file Fenolite did not write, tell whether editing it is safe, compare two files or two designs, and undo a confirmed write.
---

# Reading, comparing and undoing

The commands of this page read files and answer. None runs a tool unless the page says so, and only
`fmt`, `convert` and `restore` write.

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
KiCad board.

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
