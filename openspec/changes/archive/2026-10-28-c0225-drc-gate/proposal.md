## Why

Task 12.2 of change c0175 ("Release checks", package 11), split into a change of its own on 2026-10-28.
Change c0209 (`openspec/changes/archive/2026-10-28-c0209-drc-trials/`) gave the library call
`fenolite.api.trial(board, edit, gate=True)`: it judges an edit by `kicad-cli` DRC against the unedited
board and drops the items that bring new findings. No command uses it: a router or a tidy that lays one bad
track still leaves the agent to find it with `check` and remove it by hand. `tidy --drc`, `silk --drc` and
`place --strategy reuse --drc` only refuse the whole write when a violation type grows.

## What Changes

- `fenolite route` and `fenolite tidy` take `--gate drc`. The command makes its edit as before, then judges
  it through `fenolite.api.trial(..., gate=True)`, writes the board without the items the trial dropped, and
  reports each dropped item with its DRC finding (`result.gate`, `gate.dropped`). `route` also takes
  `--kicad-cli PATH`. Without a `kicad-cli` the command exits 6 before it edits anything.
- One helper, `fenolite.cli._gate`, holds the option, the edit's item ids, the call of `trial` and the
  report, for every gated command.
- `fenolite.api.trial` takes `together`: groups of the edit's ids that the gate drops as one (a tidy edit's
  removed, replaced and added items).
- Two issue codes, `gate.dropped` and `gate.unnamed`, explained by `fenolite explain`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `kicad-oracle`: ADDED "DRC gate on writing commands", "DRC gate report" and "DRC gate units" (moved from
  c0175, where "DRC gate on writing commands" was one requirement).

c0175 no longer holds a delta of `kicad-oracle`.

## Non-goals

- `--gate drc` on `place --strategy reuse`, `fill`, `build` and `silk` (design, decision 1).
- Rewriting the `--drc` options of `tidy`, `silk` and `place --strategy reuse` on top of `trial`
  (design, decision 4).
- Gates other than `drc`.

## Evidence level required

`KICAD-VERIFIED` (`H-K-DRC-TRIAL`, `H-K-DRC-REPEAT`) for a gated write that leaves no new finding, as the
reply of `trial`. `tests/kicad/check/test_gate_cli.py` runs `route` and `tidy` with `--gate drc` against the
local `kicad-cli` 10; the 9.x half runs in the `kicad-9` job of CI.

## Impact

- `src/fenolite/cli/_gate.py` (new), `cli/cmd_route.py`, `cli/cmd_tidy.py`, `api/trials.py`,
  `cli/explain.py`, `cli/data/explain.toml`, the guide's `routing` page and the generated `commands.md`,
  `docs/cli-contract.md`, `CHANGELOG.md`, tests, and c0175's `proposal.md`, `design.md`, `tasks.md` and
  `specs/kicad-oracle/spec.md` (removed).
