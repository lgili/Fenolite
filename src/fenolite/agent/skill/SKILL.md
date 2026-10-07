---
name: fenolite
description: Build, place, route, fill, check and export a printed-circuit board from a Python design script with the fenolite command line. Use it when a task is about a KiCad board that should be made or verified without opening a GUI.
---

# Fenolite: the board loop for an agent

Fenolite turns a Python design script into a KiCad 9 or 10 project and takes it to fabrication files.
Every command prints one JSON envelope, never asks a question, and writes only when told to.

This page is the start page of the agent guide. `fenolite guide --text` lists the other pages and
`fenolite guide <topic> --text` prints one. The pages that `fenolite guide` prints always belong to the
installed version. A skill folder copied by `fenolite skill install` names the version it came from in
the last line of its `SKILL.md`: when that differs from `fenolite --version`, read `fenolite guide`.

## Rules that hold for every command

1. **`fenolite capabilities --brief --json` first.** It lists the commands with one line each, the build
   targets, the routers and the external tools found on this machine, the pages of this guide and the
   starter projects. Do not assume a tool is there. `fenolite capabilities --command NAME --json` gives
   one command's arguments as data. `fenolite capabilities --json`, the long reply, holds
   `result.matrix`: read it before choosing an operation on a file kind. It says, per backend and kind,
   whether `detect`, `read`, `write` and the two round trips exist (`null` when they do not), at which
   evidence level, and which of them may still change. The status of each Altium write kind is read
   there and nowhere else.
2. **Read the exit code before the output.**

   | exit | meaning | what to do |
   |---|---|---|
   | 0 | done | read `result` |
   | 1 | internal failure | read `retryable`: when it is false (`FEN-1001`) this is a bug in Fenolite, so stop and report the error object. `FEN-1002` (a write failed) and `FEN-1003` (stopped by a signal) changed nothing: remove the cause and run the same command again |
   | 2 | wrong usage | read `hint` in the error object and fix the command line |
   | 3 | bad input | the file named in `where` is missing or malformed: fix the input, not the command |
   | 4 | confirmation required | nothing was written. `FEN-4001`: a writing command ran without `--dry-run` or `--confirm`, see rule 3. `FEN-4002`: the plan named by `--plan` is no longer the one you reviewed (a file changed): run `--dry-run` again and confirm the new id |
   | 5 | findings | the command worked and found problems: read `issues`, fix the design, run again |
   | 6 | an external tool is missing | install what `hint` names (`kicad-cli`, Java, a router), or choose another router |
   | 7 | a lossy operation was refused | nothing was written; pass `--allow-lossy` only if the loss named in `issues` is acceptable |

   On a non-zero exit, stderr holds one error object: `code`, `message`, `hint`, `retryable`. With
   `--progress` a long step also writes progress records there, one JSON line each, and the error
   object is the last line.
3. **`--dry-run`, then `--confirm`.** A writing command writes nothing by default. `--dry-run` returns
   `result.plan`, the list of files it would write, and `result.plan_id`; `--confirm` writes them and
   returns a `receipt` with the SHA-256 of each. Look at the plan first whenever the files already exist:
   a confirmed write replaces them. After a review, write with `--confirm --plan <plan_id>` and the same
   arguments: it writes the reviewed bytes without running the command, and its tools, a second time. A
   command writes all its files or none, and it writes none when it reports an `error`.
4. **Evidence.** Every envelope carries `evidence.level`. `KICAD-VERIFIED` means `kicad-cli` judged the
   result. Treat every level below it (`ORACLE-VERIFIED`, `CORPUS-VERIFIED`, `INFERRED`, `UNKNOWN`,
   `UNVERIFIED`) as unconfirmed: say so when you report, and let `fenolite check` decide.
5. **Issues.** `issues` is a list of `{code, severity, message, where}`. An `error` makes the exit code
   5; a `warning` or an `info` does not. `where` names a reference such as `R1-2`, or a place in a file.
6. **One fix per iteration.** Change one thing, then run `fenolite check` again: it is the judge of
   every change. `--format concise` keeps one issue per code with the counts, which is what this needs.
   `--fields a,b.c` keeps only the named parts of `result`, and `--limit N` cuts a long list to a page;
   the exit code still comes from the whole result.
7. **Same bytes twice.** Pass `--seed` and `--timestamp` when two runs must give identical files.

## The loop

Ten commands take a new project from an empty folder to fabrication files. Run them in this order, in a
folder of your own, and stop at the first non-zero exit code. Only `kicad-cli` has to be installed.

```fenolite-loop
fenolite capabilities --brief --json
fenolite init blink --confirm --json
fenolite build blink/design.py --out blink/build --dry-run --json
fenolite build blink/design.py --out blink/build --confirm --json
fenolite place blink/build --strategy grid --confirm --json
fenolite route blink/build --router direct --confirm --json
fenolite fill blink/build --confirm --json
fenolite check blink/build --json
fenolite export blink/build -o blink/fab --all --manifest --confirm --json
fenolite render blink/build -o blink/views --svg --png --confirm --json
```

What each step is for:

- `init` writes `blink/design.py`, a starter script: a header, a resistor and a LED from the built-in
  catalog, which needs no KiCad library. Edit that script to make your own board;
  `fenolite catalog list` shows the parts it can name.
- `build` runs the design script and writes the project, the board, the schematic, the rules file and
  the library tables. Parts without a position are left beside the board; a second build keeps what was
  placed, routed and filled since.
- `place --strategy grid` puts those parts on the board. The starter places every part itself, so
  `build` reports `result.staged` empty and this step changes nothing here; it matters as soon as a
  script leaves a part without `place()`. `--move REF=X,Y` moves one part by hand.
- `route` closes the open nets: it selects every net that still has an open connection, also one that
  already holds copper. `--router direct` is built in: it joins the two pads of a net with one straight
  track and checks nothing, which is enough for the starter because its placement was chosen for it. A
  real board needs a real router (`capabilities --brief` says which are available and why not) or
  copper written in the script. `--router freerouting` needs Java 25 or newer and the Freerouting jar:
  `fenolite fetch freerouting --confirm` installs it once (or name your own with
  `FENOLITE_FREEROUTING_JAR`). `result.unrouted` lists the nets that are still open after the run and
  `result.open` their connections; an empty list is not yet a proof, which is the job of `check`.
- `fill` refills the copper zones through `kicad-cli`. The starter has no zone, so the step changes
  nothing here; it matters on every board with a zone, after each change of its copper.
- `check` is the judge: the model, the electrical rules, the copper clearances, KiCad's own design-rule
  check, and the comparison of the nets between the script and the board. Exit code 0 means no error.
- `export` writes Gerber, drill, position and netlist files with a manifest; `render` writes views to
  look at.

Before you write a track by hand in the script (`design.track`, `design.via`), ask where the pads are:
`fenolite pads blink/build D1 --origin 100mm,100mm --json` lists each pad of `D1` with its position,
layers and net. With `--origin 100mm,100mm` the positions are in the frame of `place()`, so they go into
the script as they are. It reads the board and runs no tool.

## When a step fails

- **`check` exits 5.** Read `issues`. `kicad.drc.unconnected-items` means copper is missing between the
  two items of `where`: run `route` again (open nets are selected again, and the copper already there
  stays; add `--rip` only when that copper is in the way), or add the copper in the script.
  `kicad.drc.*` codes carry KiCad's own message. `netlist.assignment-differs` means a pad is on another
  net than the script says. A count that `summary.limits` of the stage `drc.kicad` names (one
  `check.report-limit` warning per type) is a lower bound: KiCad's report stops at 499 or 199 entries
  per type, so repair the reported findings and check again to see the next ones.
- **`route` lists nets under `unrouted`.** Run `route` again: the copper of the first run is kept and
  the second run completes those nets from it. If they stay open, give the router more room (move parts
  with `place --move`), choose another router, or script the copper for those nets in the design file
  and build again. `fenolite net BOARD NAME --json` shows which connections of a net are open, without
  running a tool; `--require-complete` makes `route` exit 5 and write nothing when a net stays open.
- **`route` reports `route.budget-exhausted`.** `fenolite route … --timeout S` bounds the whole step; the
  copper of the router runs that finished is written. Run `route` again to continue with the nets still
  open, or raise `--timeout`.
- **`build` exits 5 with `copper.short` or `copper.clearance`.** Copper on the board now collides with
  the design: a part was moved onto a track or onto an old zone fill. Refill (`fenolite fill`) or move
  the part, then build again.
- **Exit 6.** The envelope of `fenolite doctor --json` says which tool is missing and where it is
  looked for.

## Small questions between the steps

These commands read and answer; none of them runs a tool unless its page says so. Each page holds their
command lines, which the tests run.

- `checks`: `fenolite explain CODE` says what an error code or an issue code means and what to do about
  it; `fenolite netlist`, `fenolite parity` and `fenolite doctor` are there too.
- `placement`: `fenolite pads` (above), `fenolite region` and `fenolite neighbors` say what is where.
- `routing`: `fenolite net BOARD NAME` describes one net and its open connections.
- `files`: `fenolite inspect` reads a file back; `fenolite roundtrip FILE` before you edit a file that
  Fenolite did not write; `fenolite diff` and `fenolite equivalent` compare; `fenolite fmt --check`;
  `fenolite restore ENVELOPE.json --confirm` undoes a confirmed write, so keep its envelope.
- `fabrication`: `fenolite manifest`, after `export`, lists every file with its SHA-256 and a state;
  `fenolite bom` and `fenolite pnp` give the assembly tables.
- `recovery`: one tested recipe per exit code, and `fenolite skill install --dir DIR --confirm`, which
  copies this guide into a folder that an agent reads skills from.
- `altium`: The Altium verification kit (`fenolite kit`) is a run that a person performs in Altium Designer
  and is not this guide: `fenolite kit build` writes its files and `fenolite kit verify` judges what the
  run left, but nothing starts Altium, so you cannot perform it.

## The pages

`fenolite guide <topic> --text` prints one of these. Read `design-script` before you write a script and
`recovery` when a command exits with a code that is not 0.

<!-- pages:begin -->
- `altium`: build --target altium, what it writes, the status of each written file kind as capabilities reports it, and the kit that a person runs.
- `checks`: The stages of check, how to read an issue and explain it, evidence levels, keeping replies small, the netlist, parity and doctor.
- `commands`: The complete list: each public command, whether it writes, and every argument with its help.
- `design-script`: The shape of a script: design, modules, nets, parts, lengths with units, the board frame, and the edit and build cycle.
- `dsl-reference`: The complete list: each name a design script imports from fenolite.dsl, with its signature.
- `fabrication`: export, the bill of materials, the position table, the manifest and its states, render, and what is not produced.
- `files`: Read a file Fenolite did not write, tell whether editing it is safe, compare two files or two designs, and undo a confirmed write.
- `footprints`: Footprint and Symbol from dimensions when no library has the part, and what a person must still check against the datasheet.
- `parts`: Where symbols and footprints come from, how a pin is named, pad_map, values with units, user properties and typed interfaces.
- `placement`: place() in the script, staged parts and the grid strategy, moving a part on the board, where the pads are, and text fields.
- `recovery`: One tested recipe per exit code from 2 to 7 and for shorted copper, the table of every error code, and reading the guide itself.
- `routing`: Which router does what, route with --nets and --rip, what unrouted means, copper written in the script, zones and fill.
- `rules`: Net classes against minimums, rules with selectors, the stack-up, whose numbers apply, and analyze for current, clearance and creepage.
<!-- pages:end -->

## Limits

- The releases prove the loop on two-layer boards, for KiCad 9.0 and 10.0. `build --target altium` also
  writes an Altium project: the status and the evidence level of each of its file kinds are in
  `result.matrix` of `fenolite capabilities --json`, and they change from release to release.
- The `direct` router is for the starter and for boards as simple. It never looks at clearances.
- The full contract of the command line (`docs/cli-contract.md`), the design script (`docs/dsl.md`) and
  what was and was not proved for each release (`docs/release/`) are in the source repository.
