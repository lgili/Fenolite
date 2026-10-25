## Why

The skill folder of the agent guide must stay under 150 000 bytes (requirement "Page budgets and writing
rules"). On branch `c0184-visual-diff` it held 148 731 bytes. The viewer changes c0179 to c0182 had to shorten
`fenolite view` help texts and a line of `references/files.md` to fit, and c0184 dropped the default "string"
type from the generated argument lines. The next changes (c0186, c0188, c0189) add `fenolite view` flags and
guide lines, which AGENTS.md requires ("Teach what you add"), and they would not fit.

The generated page `references/commands.md` was the largest file (34 056 bytes), and it said most things
twice: each section's usage line listed every optional flag with its placeholder (5.4 KB of the page), and the
argument lines below listed the same flags again.

## What Changes

- **Short usage lines.** A section's usage line shows the command, `[OPTIONS]` when it has optional flags, and
  the required options and the positionals: `fenolite build [OPTIONS] --out DIR DESIGN.py`.
- **The placeholder on the argument line.** An option's line names the value it takes as the usage line did:
  `--kinds K,K`, `--copper-thickness [LAYER=]LENGTH`, `--target {altium,kicad}`. A choice placeholder
  replaces the "one of `a`, `b`" fact.
- **No repeated facts.** `boolean` (a flag without a value is a switch), `required` and `optional` (the usage
  line shows them) leave the argument lines; the head of the page says so once.
- The budget stays at 150 000 bytes.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `agent-guide`: requirement "Generated guide pages" says the form of the page `commands`.

## Non-goals

- Raising the folder budget. With this change the folder holds 144 108 bytes, 5 892 under the budget.
- Rewriting written pages or help texts.

## Evidence level required

- None: the page is generated from the argparse parsers of the commands, which stay the source of truth.

## Impact

- **Changed:** `tools/gen_agent_guide.py`, `src/fenolite/agent/skill/references/commands.md` (generated),
  `tests/unit/agent/test_pages.py`, `openspec/specs/agent-guide/spec.md` when archived.
- **Unchanged:** `fenolite capabilities --command NAME --json` still gives the full usage line.
- **Size:** under a design-day.
