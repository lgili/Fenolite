---
name: fenolite
description: Build, place, route, fill, check and export a printed-circuit board from a Python design script with the fenolite command line. Use it when a task is about a KiCad board that should be made or verified without opening a GUI.
---

# Fenolite: the board loop for an agent

Fenolite turns a Python design script into a KiCad 9 or 10 project and takes it to fabrication files.
Every command prints one JSON envelope, never asks a question, and writes only when told to.

## Rules that hold for every command

1. **`capabilities` first.** `fenolite capabilities --json` lists the commands, the routers and the
   external tools found on this machine, with their versions. Do not assume a tool is there.
   Read `result.matrix` before choosing an operation on a file kind: it says, per backend and kind,
   whether `detect`, `read`, `write` and the two round trips exist (`null` when they do not), at which
   evidence level, and which of them are `experimental`.
2. **Read the exit code before the output.**

   | exit | meaning | what to do |
   |---|---|---|
   | 0 | done | read `result` |
   | 1 | a bug in Fenolite | stop and report the error object; do not retry |
   | 2 | wrong usage | read `hint` in the error object and fix the command line |
   | 3 | bad input | the file named in `where` is missing or malformed: fix the input, not the command |
   | 4 | confirmation required | a writing command ran without `--dry-run` or `--confirm`: see rule 3 |
   | 5 | findings | the command worked and found problems: read `issues`, fix the design, run again |
   | 6 | an external tool is missing | install what `hint` names (`kicad-cli`, Java, a router), or choose another router |
   | 7 | a lossy operation was refused | nothing was written; pass `--allow-lossy` only if the loss named in `issues` is acceptable |

   On a non-zero exit, stderr holds one error object: `code`, `message`, `hint`, `retryable`.
3. **`--dry-run`, then `--confirm`.** A writing command writes nothing by default. `--dry-run` returns
   `result.plan`, the list of files it would write; `--confirm` writes them and returns a `receipt`
   with the SHA-256 of each. Look at the plan first whenever the files already exist: a confirmed
   write replaces them.
4. **Evidence.** Every envelope carries `evidence.level`. `KICAD-VERIFIED` means `kicad-cli` judged the
   result. Treat every level below it (`ORACLE-VERIFIED`, `CORPUS-VERIFIED`, `INFERRED`, `UNKNOWN`,
   `UNVERIFIED`) as unconfirmed: say so when you report, and let `fenolite check` decide.
5. **Issues.** `issues` is a list of `{code, severity, message, where}`. An `error` makes the exit code
   5; a `warning` or an `info` does not. `where` names a reference such as `R1-2`, or a place in a file.
6. **Small replies.** `--fields a,b.c` keeps only the named parts of `result`. `--format concise` keeps
   one issue per code with the counts: use it to fix one problem per iteration. `--limit N` cuts a long
   list to a page; the exit code still comes from the whole result.
7. **Same bytes twice.** Pass `--seed` and `--timestamp` when two runs must give identical files.

## The loop

Ten commands take the example from a script to fabrication files. Run them from the repository root,
in this order, and stop at the first non-zero exit code.

```fenolite-loop
fenolite capabilities --json
fenolite build examples/blink_2layer/design.py --out build/blink --dry-run --json
fenolite build examples/blink_2layer/design.py --out build/blink --confirm --json
fenolite place build/blink --strategy grid --confirm --json
fenolite route build/blink --router freerouting --confirm --json
fenolite fill build/blink --confirm --json
fenolite check build/blink --json
fenolite export build/blink -o build/blink/fab --all --manifest --confirm --json
fenolite render build/blink -o build/blink/views --svg --png --confirm --json
fenolite inspect build/blink/blink.kicad_pcb --json
```

What each step is for:

- `build` runs the design script and writes the project, the board, the rules file and the library
  tables. Parts without a position are left beside the board; a second build keeps what was placed,
  routed and filled since.
- `place --strategy grid` puts those parts on the board; when `build` reports `result.staged` empty, every
  part already has a position and this step changes nothing. `--move REF=X,Y` moves one part by hand.
- `route` closes the open nets. `result.unrouted` lists what the router left open; an empty list is not
  yet a proof, which is the job of `check`. `--router freerouting` needs Java 25 or newer and the Freerouting jar:
  `fenolite fetch freerouting --confirm` installs it once (or name your own with `FENOLITE_FREEROUTING_JAR`);
  `fenolite capabilities` lists the other routers.
- `route` closes the open nets: it selects every net that still has an open connection, also one that
  already holds copper. `result.unrouted` lists the nets that are still open after the run and
  `result.open` their connections; an empty list is not yet a proof, which is the job of `check`. `--router freerouting` needs Java 25 or newer and the Freerouting jar
  named by `FENOLITE_FREEROUTING_JAR`; `fenolite capabilities` lists the other routers.
- `fill` refills the copper zones through `kicad-cli` 10. A board without zones needs no fill, and the
  step changes nothing there.
- `check` is the judge: the model, the electrical rules, the copper clearances, KiCad's own design-rule
  check, and the comparison of the nets between the script and the board. Exit code 0 means no error.
- `export` writes Gerber, drill, position and netlist files with a manifest; `render` writes views to
  look at; `inspect` reads a file back and reports what it holds.

Before you write a track by hand in the script (`design.track`, `design.via`), ask where the pads are:
`fenolite pads build/blink D1 --origin 100mm,100mm --json` lists each pad of `D1` with its position, layers
and net. With `--origin 100mm,100mm` the positions are in the frame of `place()`, so they go into the
script as they are. It reads the board and runs no tool.

## When a step fails

- **`check` exits 5.** Read `issues`. `kicad.drc.unconnected-items` means copper is missing between the
  two items of `where`: route again (`fenolite route … --rip` re-routes nets that already have copper), or
  add the copper in the script. `kicad.drc.*` codes carry KiCad's own message. `netlist.assignment-differs`
  means a pad is on another net than the script says. A count that `summary.limits` of the stage `drc.kicad`
  names (one `check.report-limit` warning per type) is a lower bound: KiCad's report stops at 499 or 199
  entries per type, so repair the reported findings and check again to see the next ones.
- **`route` lists nets under `unrouted`.** Give the router more room (move parts with `place --move`),
  or script the copper for those nets in the design file and build again.
  two items of `where`: run `route` again (open nets are selected again, and the copper already there
  stays; add `--rip` only when that copper is in the way), or add the copper in the script. `kicad.drc.*` codes carry KiCad's own message. `netlist.assignment-differs`
  means a pad is on another net than the script says.
- **`route` lists nets under `unrouted`.** Run `route` again: the copper of the first run is kept and
  the second run completes those nets from it. If they stay open, give the router more room (move parts
  with `place --move`), or script the copper for those nets in the design file and build again.
  `fenolite net BOARD NAME --json` shows which connections of a net are open, without running a tool;
  `--require-complete` makes `route` exit 5 and write nothing when a net stays open.
- **`build` exits 5 with `copper.short` or `copper.clearance`.** Copper on the board now collides with
  the design: a part was moved onto a track or onto an old zone fill. Refill (`fenolite fill`) or move
  the part, then build again.
- **Exit 6.** The envelope of `fenolite doctor --json` says which tool is missing and where it is
  looked for.

## Small questions between the steps

These commands read and answer; none of them runs a tool unless it says so.

- `fenolite explain CODE` says what an error code or an issue code means and what to do about it.
- `fenolite roundtrip FILE` before you edit a file that Fenolite did not write: exit 5
  (`roundtrip.failed`) means reading it and writing it back would change it, so edit it in KiCad.
- `fenolite diff A B` lists what changed between two boards, libraries or built models; a moved
  footprint is one change. `--view tree` says whether two KiCad files differ at all.
- `fenolite net BOARD [NAME]`, `fenolite region BOARD --box 10mm,5mm,30mm,20mm` and
  `fenolite neighbors BOARD R1` describe a net, a rectangle of the board and what is near a part.
- `fenolite netlist build/blink --source fenolite` lists the components and nets of a schematic that
  `build` wrote, without any tool; `--min-pins 2` hides the unconnected pins. For any other KiCad
  schematic leave `--source` out: `kicad-cli` reads it (exit 6 without the tool).
- `fenolite fmt FILE --check` says whether a file is in Fenolite's canonical print.
- `fenolite manifest build/blink --artifacts build/blink/fab --confirm`, after `export`, writes one
  file that lists every design file and exported file with its SHA-256 and a state (`generated`,
  `checked`, `roundtrip-ok`, `native-verified`); it runs the stages of `check`, so it needs
  `kicad-cli`. Read `held` of an entry to see what its next state is missing. Before you hand a folder
  over, `fenolite manifest build/blink --verify` says whether its files are still the listed ones.
- `fenolite kit build --out kit --confirm` writes the Altium verification kit, a run that a person performs
  in Altium Designer; `fenolite kit verify kit` judges the files that run left. You cannot perform the run:
  nothing starts Altium (`docs/altium-kit.md`).
- **Undo.** Keep the envelope of a confirmed write. When `receipt.undo` is not `null`,
  `fenolite restore ENVELOPE.json --confirm` puts the backups back. It refuses when a file changed since
  the write, and it never deletes a file.

## Limits

The loop above is proved for v0.1 on two-layer boards, for KiCad 9.0 and 10.0. What Fenolite does not
do, and what was and was not proved for this version, is in `docs/release/v0.1.md`. The full
contract of the command line is in `docs/cli-contract.md`, and the design script in `docs/dsl.md`.
