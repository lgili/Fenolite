---
topic: files
title: Reading, comparing and undoing
summary: Read a file Fenolite did not write, tell whether editing it is safe, compare two files or two designs, and undo a confirmed write.
---

# Reading, comparing and undoing

The commands of this page read files and answer. None runs a tool unless the page says so, and only
`fmt` and `restore` write.

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

For more than counts, ask the board: `fenolite net`, `fenolite pads`, `fenolite region` and
`fenolite neighbors` (pages `routing` and `placement`) work on any KiCad board, also one that Fenolite
did not write.

## Is it safe to edit this file?

```fenolite-cmd
fenolite roundtrip blink/build/blink.kicad_pcb --json
fenolite roundtrip blink/build/blink.kicad_pcb --level rt0 --json
```

Before a command of Fenolite changes a file that Fenolite did not write, ask `roundtrip`. It reads the
file and writes it back in memory, and writes nothing to disk:

- `rt0`: parsing the file, printing it and parsing it again gives an equal tree;
- `rt1` (the default): also, Fenolite's rebuild of the board or schematic gives an equal tree, an equal
  design and the same content that Fenolite does not model;
- `rt2`: also, KiCad's own checks give the same findings for the file and for Fenolite's copy of it
  (a project, with `kicad-cli`).

`result.level` is the highest level that holds. Exit 5 with `roundtrip.failed` means reading the file
and writing it back would change it, and `where` is the first difference: edit that file in KiCad, not
with Fenolite.

## What changed between two files?

```fenolite-cmd
fenolite diff blink/build/blink.kicad_pcb blink/other/blink.kicad_pcb --json
fenolite diff blink/build blink/other --json
fenolite diff blink/build/blink.kicad_pcb blink/other/blink.kicad_pcb --view tree --json
```

`diff A B` compares two boards, footprint files, symbol libraries, built projects or Altium files.

- The default view compares what the files mean: `result.equal`, a `summary` of added, removed and
  changed items per kind, and `differences`, each with a `path` and a `change`. A moved footprint is
  one change, however many lines of the file moved.
- `--view tree` compares the files as trees: `equal`, and `first_difference`, the first place where
  they differ. Use it to say whether two KiCad files differ at all.
- `diff` exits 0 whether the files are equal or not: read `result.equal`.
- Two built folders compare the designs they hold (`.fenolite/`): parts, nets, rules.

## Are two designs equivalent?

```fenolite-cmd
fenolite equivalent blink/build blink/other --json
fenolite equivalent blink/build blink/other --level 2 --json
fenolite equivalent blink/build blink/altium/blink.PrjPcb --frame relative --json
```

`equivalent A B` answers level by level, and it can compare a KiCad project with an Altium one:

| level | compares |
|---|---|
| 1 | the components |
| 2 | the netlist |
| 3 | the footprints |
| 4 | the placement |
| 5 | the routing |

- Without `--level`, it runs up to the highest level both sides hold. `--level 2` asks only whether
  the circuits are the same.
- Exit 0 and `result.equivalent` true, or exit 5 with one `equiv.*` issue per difference, located at
  a reference, a pin or a net.
- `--tolerance-nm N` allows a distance between two positions; `--frame relative` removes one
  translation of the whole board; `--ignore-ref GLOB` leaves parts out.
- With two paths it runs no tool.

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

- `restore ENVELOPE` puts the backups of that one write back. `--in DIR` names the working directory
  the write ran in, when it is not the current one.
- It refuses when a written file changed since the write (`restore.changed-since`), so nothing is half
  undone.
- It never deletes a file: a file that the write created stays, with `restore.kept` (info).
- When `receipt.undo` is `null` there is nothing to restore; a write with `--no-backup` keeps no
  backup.
- `restore` is itself a write: its own receipt undoes it.

Read next: `checks`, `altium`, `recovery`.
