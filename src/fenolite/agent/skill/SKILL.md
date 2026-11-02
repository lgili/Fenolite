---
name: fenolite
description: Build, inspect, route, check and export KiCad boards from Python.
---

# Fenolite: the board loop for an agent

Build KiCad 9/10 projects and fabrication files from Python. Commands return JSON.
`fenolite guide --text` lists pages; `fenolite guide <topic> --text` prints one. Pages belong to the
installed version. A copy's footer names the version it came from; if it differs from
`fenolite --version`, use the installed guide.

## Rules for every command

1. Run `fenolite capabilities --brief --json` first. Check available tools and targets. Use
   `fenolite capabilities --command NAME --json` for arguments and the full reply's `result.matrix`
   for per-format read/write/round-trip status and evidence. Read Altium write status there.
2. Read the exit code before output:

   | exit | meaning and action |
   |---|---|
   | 0 | done; read result |
   | 1 | `FEN-1001`: report a bug; `FEN-1002`/`FEN-1003`: nothing changed, fix the cause and retry; `FEN-1004`: rollback incomplete, retain recovery files and inspect before retrying |
   | 2 | wrong usage; fix the command using hint |
   | 3 | bad input; inspect where and repair the input |
   | 4 | confirmation needed; `FEN-4001`: review a dry run; `FEN-4002`: inputs or targets changed, review a new plan |
   | 5 | findings; read issues, fix one problem, check again |
   | 6 | an external tool is missing; install the named tool or choose an available operation |
   | 7 | loss refused; accept --allow-lossy only after reviewing the specific loss |

   On nonzero exit stderr ends with an error object: code, message, hint, retryable. `--progress`
   also writes earlier progress records. Preserve `result.recovery.preserved` and inspect
   `result.recovery.failed` on incomplete rollback.
3. Writes require `--dry-run` or `--confirm`. Preview first; inspect `result.plan` and `result.plan_id`.
   Use the same arguments with `--confirm --plan ID` to replay reviewed bytes without rerunning
   the command or tools. Error findings plan no write. Receipts hold written hashes and backups;
   keep them for `fenolite restore`. Failed writes roll back; incomplete rollback is `FEN-1004`.
4. Read `evidence.level`. Only `KICAD-VERIFIED` states that KiCad judged the result. Treat lower levels
   (`ORACLE-VERIFIED`, `CORPUS-VERIFIED`, `INFERRED`, `UNKNOWN`, `UNVERIFIED`) as unconfirmed and say so.
5. Issues carry code, severity, message, where, hint and retryable. Errors cause exit 5; warnings and
   info do not. Use issue codes and subject identities.
6. **One fix per iteration.** Change, then check. `--format concise` groups findings; `--fields a,b.c` selects
   result fields and `--limit N` paginates. The exit code still judges the full result.
7. Supply `--seed` and `--timestamp` for reproducible bytes. Build executes trusted Python as your own
   code. Preserve manual changes and inspect rebuild plans before replacing existing files.

## The loop

Run these ten commands in order in a new folder. Stop on a nonzero exit and read its diagnostic.
Build/view need no CAD tool; fill, full check, fabrication export and plot views need KiCad.
The educational direct router draws straight lines without checking clearances.

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

`init` creates a catalog-only header/resistor/LED starter. Edit its script; `build` writes the board,
schematic, rules and local libraries. Parts without positions are staged beside the board. Rebuilds
preserve supported editor changes; `design-script` explains the limits and precedence.

`place` positions staged parts. The starter is placed, so this changes nothing here. Before scripting copper:
`fenolite pads blink/build D1 --origin 100mm,100mm --json` returns script-frame positions, layers and nets.

Production routing uses an external router or scripted copper. `route` keeps copper and connects open
islands; `--rip` removes selected copper. Freerouting needs Java and its jar, installed by
`fenolite fetch freerouting --confirm`. Read `routing`.

`fill` refreshes zones after copper edits. `check` judges model, electrical rules, copper, native DRC
and assignment parity. `fenolite ready blink/build --json` gives a readiness summary before export.
A clean check does not prove the circuit's function: read `board-practice` before designing a real board.
`export` writes manufacturing files and a manifest; `render` writes review views.

## Responding to failures

- Missing copper: `kicad.drc.unconnected-items`; inspect where, route again, move parts or script copper.
  `fenolite net BOARD NAME --json` shows remaining islands. `route --require-complete` refuses an
  incomplete write. `netlist.assignment-differs` means a pad disagrees with the source netlist.
- A `check.report-limit` count in `drc.kicad.summary.limits` is a lower bound. Fix reported findings and
  check again; a truncated report cannot establish the total number of violations.
- `route.budget-exhausted`: completed work can be retained; rerun or increase the budget.
- `build` reports copper conflicts: inspect changed placement and stale fills, refill or move the part
  and rebuild. Never waive a conflict without understanding it.
- Exit 6: `fenolite doctor --json` shows external-tool discovery. Exit 1 or damaged recovery: follow
  `recovery` before writing again.
  The Altium verification kit (`fenolite kit`) is a run that a person performs in Altium Designer;
  commands can prepare/judge its files but cannot perform the manual acceptance.

Read files with `fenolite inspect`, `fenolite roundtrip`, `fenolite diff` and `fenolite fmt --check`.
Use `fenolite explain CODE` for diagnostics, `fenolite neighbors` and `fenolite region` for geometry,
`fenolite netlist` for connections, and `fenolite manifest` for exported-file hashes.
`fenolite skill install` copies the installed guide for an agent.

## Designing a good board

Read `board-practice` before placing parts; it links engineering practice pages.

## The pages

Read `design-script` before authoring and `recovery` for failures. The command index links every
argument. Practice pages explain engineering judgement; example numbers are not universal requirements.

<!-- pages:begin -->
- `altium`: Altium builds, blocks, native sync, evidence and the verification kit.
- `block-layouts`: Exact versioned layouts, mirrored block poses, and capturing a laid-out block under plan and confirm.
- `block-testing`: Ship a usage build, plain tests and a reviewed circuit/rules golden; stimulate ports and read typed verdicts.
- `board-assembly`: Designators and silkscreen, polarity and pin 1, test points and fiducials, footprints by IPC-7351, 3D bodies, and the board as the master of its library.
- `board-emc`: An immunity basis first, the mains entry in order, filter sides kept apart, the earth bond in copper, staged pin protection, gate buses and analog lines.
- `board-floorplan`: Mechanical constraints first, regions by domain and function, one-way power flow, loop parts first, decoupling at the pin, reference blocks, placement in code.
- `board-grounds`: Ground domains, one tie between two domains and where it goes, Kelvin sensing, return paths, proving a single tie, and the commands that show a net.
- `board-insulation`: Insulation domains, the inputs that set a distance, slots and grooves, copper under parts and on both faces, measuring with analyze, and what not to claim.
- `board-power`: Current loops and loop area, copper sized by a public method, pours as wide straight bands, necks, parallel vias, gate drive, and connectivity after cut-outs.
- `board-practice`: The order of work for a real board, what a check cannot see, whose numbers apply, and the practice pages that go with each step.
- `board-review`: The self-review checklist, what reviewers reject, how to answer review findings, and how decisions and open items are recorded.
- `board-routing`: Count the crossings of each barrier first, critical nets first, a clean octilinear style, sensitive nets, vias, and an external router's input.
- `board-schematic`: One master for every change, net classes on the wire, connectivity by pin sets, a clean drawing, ratings with their conditions, parts from references.
- `board-workflow`: Copies and versions, a SHA-256 before every write, files a person has open, references between files, parallel editors, and honest reports.
- `checks`: The stages of check, how to read an issue and explain it, evidence levels, keeping replies small, the netlist, parity and doctor.
- `commands`: The complete list: each public command, whether it writes, and every argument with its help.
- `commands-1`: Generated arguments; index: commands.
- `commands-2`: Generated arguments; index: commands.
- `commands-3`: Generated arguments; index: commands.
- `commands-4`: Generated arguments; index: commands.
- `commands-5`: Generated arguments; index: commands.
- `commands-6`: Generated arguments; index: commands.
- `datasheets`: Read a datasheet with your own tools, propose cited parameters, generate records and hand review to a person.
- `design-script`: Design scripts: modules, nets, parts, unit lengths, board frame and build cycle.
- `device-packs`: Use device items offline; seed CC0 data.
- `device-symbols`: Bind device pin tables to package-specific drawings.
- `dsl-reference`: The complete list: each name a design script imports from fenolite.dsl, with its signature.
- `equivalent-s`: Drawings and nets.
- `fabrication`: export, the bill of materials, the position table, the manifest and its states, render, and what is not produced.
- `files`: Inspect files Fenolite did not write, compare designs and undo writes.
- `footprints`: Footprint and Symbol from dimensions or pin tables, library records, items from fenolite-library, and what a person must check against the datasheet.
- `library-items`: Review licensed items, offline pins, device migrations and block package tests, indexing and upgrades.
- `library-review`: Check library records, compare revisions and prepare deterministic sheets for a person's review.
- `parts`: Symbols, footprints, pin maps, exact values, device imports, interfaces and blocks.
- `placement`: place() by coordinates or by reference, staged parts and the grid strategy, moving parts on the board, copying a block by its pads, pads and text fields.
- `recovery`: One tested recipe per exit code from 2 to 7 and for shorted copper, the table of every error code, and reading the guide itself.
- `routing`: Which router does what, route with --nets and --rip, what unrouted means, copper written in the script, zones and fill.
- `rules`: Net classes against minimums, rules with selectors, the stack-up, whose numbers apply, and analyze for current, clearance and creepage.
- `signal-topologies`: Ordered pad trees, explicit timing and loss inputs, protocol budgets and rule precedence.
- `starter-blocks`: Five reusable circuits with exact expectations and explicit electrical inputs.
- `supplier-lookup`: Per-user supplier credentials, source readiness and review-only identity proposals.
- `viewer`: Drawings, findings and reviewed actions.
<!-- pages:end -->

## Limits

Use direct routing for simple examples. Read capability, conversion and Altium limits and evidence.
Repository docs cover the CLI, DSL, release scope and formats. Review images and golden comparisons
show presentation stability, not electrical correctness.
