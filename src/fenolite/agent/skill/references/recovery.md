---
topic: recovery
title: Recovery: what to do for each exit code
summary: One tested recipe per exit code from 2 to 7 and for shorted copper, the table of every error code, and reading the guide itself.
---

# Recovery: what to do for each exit code

Read the exit code first. On a code that is not 0, stderr holds one error object: `code`, `message`,
`hint`, `retryable`, `where`. Stdout still holds the envelope, with `issues`, when the command got that
far. Each recipe below is a sequence that the test suite runs: the comment after a command is the exit
code it gives and, after `has`, a code that the error object or an issue carries.

`fenolite explain CODE --json` gives the meaning and the fix of any code on this page.

## Exit 4, `FEN-4001`: a write without a flag

A writing command does nothing until it is told `--dry-run` or `--confirm`. Look at the plan, then
confirm.

```fenolite-recipe starter
fenolite build blink/design.py --out blink/build --json  # exit 4, has FEN-4001
fenolite build blink/design.py --out blink/build --dry-run --json  # exit 0
fenolite build blink/design.py --out blink/build --confirm --json  # exit 0
```

## Exit 2, `FEN-2001`: a wrong command line

The message names the argument and nothing ran. Ask for the command's arguments as data, then write
the line again; do not guess a flag.

```fenolite-recipe starter
fenolite build blink/design.py --out blink/build --confirn --json  # exit 2, has FEN-2001
fenolite capabilities --command build --no-tools --json  # exit 0
fenolite build blink/design.py --out blink/build --confirm --json  # exit 0
```

## Exit 3, `FEN-3001`: an unknown lib id

The build names every lib id that nothing resolves, in `issues`. Find the right id in the catalog, fix
the script, build again. Here `broken/design.py` names a footprint that does not exist:

```text
broken:  r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0630", value="330")
fixed:   r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
```

```fenolite-recipe bad-lib-id
fenolite build broken/design.py --out broken/build --confirm --json  # exit 3, has FEN-3001
fenolite catalog list --query 0603 --json  # exit 0
fenolite build fixed/design.py --out fixed/build --confirm --json  # exit 0
```

## Exit 3, `FEN-3004`: the script raises

Any error of the script stops the build, and `where` of the error object ends with `line:N`, the line
of the script that failed. The message is the script's own. Here a length has lost its unit:

```text
broken:  d1.place(15, mm(6), rot=180)
fixed:   d1.place(mm(15), mm(6), rot=180)
```

```fenolite-recipe script-error
fenolite build broken/design.py --out broken/build --confirm --json  # exit 3, has FEN-3004
fenolite build fixed/design.py --out fixed/build --confirm --json  # exit 0
```

## Exit 5, `copper.short`: two tracks cross

`copper.short` says that copper of two nets touches; the message gives the nets, the layer and the
point. Here the placement makes two straight tracks of the `direct` router cross. Move the parts, route
again with `--rip` to remove the old copper, and check again.

```fenolite-recipe crossed
fenolite build blink/design.py --out blink/build --confirm --json  # exit 0
fenolite route blink/build --router direct --confirm --json  # exit 0
fenolite check blink/build --stages model.validate,copper.clearance --json  # exit 5, has copper.short
fenolite explain copper.short --json  # exit 0
fenolite place blink/build --move R1=15mm,14mm --move D1=15mm,6mm,180 --confirm --json  # exit 0
fenolite route blink/build --router direct --rip --confirm --json  # exit 0
fenolite check blink/build --stages model.validate,copper.clearance --json  # exit 0
```

## Exit 5 in general

Exit 5 means the command worked and found problems: read `issues`. The same order holds for every
finding: read the code, ask `explain`, change one thing, check again. `copper.clearance` is repaired as
`copper.short` is. A finding between two tracks that a router drew is repaired by `route --rip` for
those nets, or by more room between the parts; one that names script copper is repaired in the script.

## Exit 6, `FEN-6001`: a tool is not installed

The hint names the tool. Choose another way that needs none, or tell the user what to install. Here the
Freerouting jar is missing and the built-in router closes the board:

```fenolite-recipe starter
fenolite build blink/design.py --out blink/build --confirm --json  # exit 0
fenolite route blink/build --router freerouting --confirm --json  # exit 6, has FEN-6001
fenolite route blink/build --router direct --confirm --json  # exit 0
```

## Without a tool

`fenolite doctor --json` says which tools are found and where they are looked for. Without
`kicad-cli`, `check --stages model.validate,copper.clearance` still judges the copper, and `fill`,
`export`, `render` and the stages of KiCad's own checks wait for the tool. Install nothing on the
user's machine without being asked.

## Exit 7, `FEN-7001`: the target cannot hold it

Nothing was written, because writing would lose something that `issues` names. Here a creepage rule is
built for KiCad 9, which does not check such rules. `--allow-lossy` accepts the loss and names what it
dropped; a target that holds the rule loses nothing.

```fenolite-recipe lossy
fenolite build blink/design.py --out blink/k9 --kicad-version 9 --confirm --json  # exit 7, has FEN-7001
fenolite explain rules.kind-unchecked --json  # exit 0
fenolite build blink/design.py --out blink/k9 --kicad-version 9 --allow-lossy --confirm --json  # exit 0, has rules.dropped-for-target
fenolite build blink/design.py --out blink/k10 --kicad-version 10 --confirm --json  # exit 0
```

## Exit 7 in general

Pass `--allow-lossy` only when the user accepts what is lost, and report it. `FEN-7001` is also the
answer of a build over a library table or a library file that someone edited: `--discard-layout`
replaces those files and keeps backups.

## Findings of KiCad's own checks

Issues whose code starts with `kicad.drc.` or `kicad.erc.` come from KiCad's design-rule check and
electrical rules check, and carry KiCad's message. `fenolite check blink/build --json` lists them; with
`--format concise` there is one per code, with its count. The commonest:

- `kicad.drc.unconnected-items`: copper is missing between the two items of `where`. Route again.
- `kicad.drc.clearance` and `kicad.drc.shorting-items`: as `copper.clearance` and `copper.short` above.
- `kicad.erc.pin-not-connected`: a pin is on no net. Connect it, or mark it with `no_connect`.

## Every error code

| code | exit | what happened | what to do |
|---|---|---|---|
| `FEN-1001` | 1 | a bug in Fenolite | stop and report the error object with the command line; do not retry |
| `FEN-1002` | 1 | a write failed; every file of the command was put back | fix the cause the message names (a full disk, a read-only folder) and run the same command again |
| `FEN-1003` | 1 | the command was stopped by a signal; nothing was written | run the same command again: `route` goes on with the router runs that finished |
| `FEN-2001` | 2 | an invalid command line | recipe above |
| `FEN-2002` | 2 | `--fields` names a key the result does not have | run with `--json` alone and read the keys |
| `FEN-2003` | 2 | `--dry-run` and `--confirm` together | use one |
| `FEN-2004` | 2 | `--timestamp` is not ISO 8601 | write it as `2026-01-01T00:00:00Z` |
| `FEN-3001` | 3 | an input is missing, or a lib id is unknown | recipe above |
| `FEN-3002` | 3 | the file is of a newer format than this version reads | upgrade Fenolite |
| `FEN-3003` | 3 | the file is of an older format than is read | re-save it in KiCad 9 or newer |
| `FEN-3004` | 3 | a malformed input, or a script that raises | recipe above |
| `FEN-3005` | 3 | geometry of the input cannot be represented | the message names the geometry and the points |
| `FEN-3006` | 3 | a fetched file does not match its pinned size or SHA-256 | fetch again, or name a good copy with `--from` |
| `FEN-4001` | 4 | a write without `--dry-run` or `--confirm` | recipe above |
| `FEN-4002` | 4 | the plan named by `--plan` cannot be written as reviewed: a target, an input or the command line changed, or no plan has that id | nothing was written; run the command with `--dry-run` again, read the new plan and confirm it with its `plan_id` |
| `FEN-5001` | 5 | findings of severity `error` | read `issues`; recipe above |
| `FEN-6001` | 6 | an external tool is not found | recipe above |
| `FEN-6002` | 6 | the tool's version is not supported | `fenolite doctor --json` names the versions that are |
| `FEN-6003` | 6 | a download failed | retry later, or install a copy with `fetch --from` |
| `FEN-7001` | 7 | the write would lose information | recipe above |
| `FEN-7002` | 7 | the target version is older than the input | choose a target at least as new as the input |
| `FEN-7003` | 7 | the input is a KiCad 8 file, which is read and never written | re-save it in KiCad 9 or newer first |

## The guide itself

```fenolite-cmd
fenolite guide --text
fenolite guide recovery --text
fenolite guide commands --json
fenolite skill show --json
fenolite skill install --dir .agent/skills --dry-run --json
fenolite skill install --agent claude-code --agents-md --confirm --json
```

`guide` prints the pages of the installed version: without a topic, the list. `skill install` copies
them into a folder that an agent reads skills from, and `--agents-md` adds a pointer to the `AGENTS.md`
of the project. The copy names the version it came from in the last line of its `SKILL.md`; when that
differs from the installed version, read `fenolite guide`.

Read next: `checks`, `routing`, `design-script`.
