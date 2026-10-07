---
topic: checks
title: Checking a board and reading the findings
summary: The stages of check, how to read an issue and explain it, evidence levels, keeping replies small, the netlist, parity and doctor.
---

# Checking a board and reading the findings

`fenolite check` is the judge of every change. It reads a project and writes nothing: exit 0 means no
finding of severity `error`, exit 5 means there is at least one.

```fenolite-cmd
fenolite check blink/build --json
fenolite check blink/build --stages model.validate,copper.clearance --json
fenolite check blink/build --stages placement.rules --json
fenolite check blink/build --format concise --json
fenolite check blink/build --json --fields stages --limit 20
```

## The stages

Without `--stages`, every stage of this table runs. `--stages A,B` selects some; two more stages,
`roundtrip.rt2` and `render`, run only when they are named.

| stage | what it judges | needs `kicad-cli` |
|---|---|---|
| `model.validate` | the design as data: references, nets, pins | no |
| `erc.kicad` | KiCad's electrical rules check on the schematic | yes |
| `copper.clearance` | Fenolite's own check of shorts and clearances on the copper | no |
| `placement.rules` | the `near` rules of the script, and the wire length and congestion of the placement | no |
| `zone.fill` | whether every zone is filled and its fill is current | yes |
| `drc.kicad` | KiCad's design-rule check on the board, unconnected items included | yes |
| `parity` | the board against the schematic, and symbol pins against footprint pads | no, for a project that `build` wrote |
| `netlist.assignment_compare` | the net of every pad, as the script, the board and KiCad see it | yes |
| `roundtrip` | whether the board survives being read and written back | no |

- `--stages model.validate,copper.clearance` is the fast check that runs anywhere: use it after each
  edit, and the whole check before you report.
- Selecting a stage that needs `kicad-cli` on a machine without it exits 6.
- An unrouted board exits 5: each open connection is a `kicad.drc.unconnected-items` error.
- `result.stages` holds one entry per stage with `status` (`ok`, `errors` or `skipped`), the `reason`
  of a skip, its own `evidence` and a `summary` of counts.

## Reading an issue

```json
{"code": "copper.short", "severity": "error", "where": "/kicad_pcb/segment[0], /kicad_pcb/segment[2]",
 "message": "copper of GND and VIN touches on F.Cu at (107.976091, 109.240987) mm"}
```

- **`code`** names the kind of finding and is stable: decide by the code, never by the message.
- **`severity`** is `error`, `warning` or `info`. Only an `error` makes the exit code 5.
- **`where`** names a reference (`R1`), a pad (`R1-2`), a net, or a place in a file, as above. The
  message of a copper finding gives the layer and the point, in file coordinates in millimetres;
  `fenolite region` with a small box around that point lists the items there (page `placement`).
- Findings of KiCad's own checks have codes that start with `kicad.drc.` and `kicad.erc.`, and carry
  KiCad's message.
- An issue also has a `hint`, which is often empty: the fix of a code is what `explain` says.

```fenolite-cmd
fenolite explain copper.short --json
fenolite explain kicad.drc.unconnected-items --json
fenolite explain FEN-6001 --json
```

`explain CODE` gives the `meaning` of an issue code or an error code and its `fix`. Ask it for every
code you have not met before; it reads a table and runs nothing.

## One fix per iteration

Change one thing, then check again. Two changes at once hide which one helped, and a finding often
disappears, or appears, as a consequence of another. Fix in this order: errors of the script (`build`),
`model.validate`, shorts, clearances, open connections, then the rest of KiCad's findings, then the
warnings you can explain. Do not silence a finding by loosening a rule you were given.

## Evidence

Every envelope carries `evidence.level`, and a check carries one per stage. The levels, from the
strongest: `KICAD-VERIFIED` (KiCad itself judged the result), `ORACLE-VERIFIED` (another tool did),
`CORPUS-VERIFIED` (it holds on the public test boards), `INFERRED` (Fenolite's own reading, not judged
by a tool), `UNKNOWN` and `UNVERIFIED` (not judged at all; a skipped stage has this level). An envelope
has the lowest level of its parts. Report the level with the result: a board whose `drc.kicad` stage
did not run is not checked, whatever the exit code says.

## Keeping replies small

- `--format concise` keeps one issue per code with its count: the right view of a long list.
- `--fields a,b.c` keeps only those parts of `result`. An unknown field exits 2 (`FEN-2002`).
- `--limit N` cuts the command's main list to a page, and `result.page.next` goes into `--cursor`.
- None of the three changes the exit code: it comes from the whole result.
- KiCad's report holds a limited number of findings per type; a `check.report-limit` warning says
  that a count is a lower bound. Fix what is listed and check again.

## The netlist and parity

```fenolite-cmd
fenolite netlist blink/build --source fenolite --min-pins 2 --json
fenolite parity blink/build --json
```

- `netlist` lists the components and the nets of the schematic. `--source fenolite` reads a schematic
  that `build` wrote, without a tool; without `--source`, `kicad-cli` reads any KiCad schematic.
- `parity` compares the board with the schematic: a footprint without a symbol, a pad on another net,
  a pin without a pad. `result.summary` counts each kind (`parity.*`), and each difference is an issue.
- `netlist.assignment-differs`, from the stage `netlist.assignment_compare`, means a pad is on another
  net than the script says: build again, and look for copper drawn on the wrong pad.

## What is installed

```fenolite-cmd
fenolite doctor --json
fenolite doctor --no-run --json
fenolite capabilities --brief --json
fenolite capabilities --command check --json
fenolite capabilities --json --fields matrix
```

- `doctor` reports each `kicad-cli` it finds with its version, and Java. `--no-run` lists the candidates
  and starts nothing. An exit 6 from any command is answered here.
- `capabilities --brief` is the small first reply; `--command NAME` gives one command's arguments as
  data; the long reply holds `matrix`, which says for each file kind what Fenolite can do with it and at
  which evidence level.

Read next: `recovery`, `routing`, `files`.
