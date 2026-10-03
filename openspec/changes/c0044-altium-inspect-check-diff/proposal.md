## Why

c0039 to c0043 let Fenolite read Altium files into records and into the neutral model. Nothing yet
tells a user or an agent whether a reading can be trusted, what a file holds, or what changed between
two files. `fenolite inspect` and `fenolite check` accept only KiCad input, `fenolite diff` does not
exist, and the round-trip levels RT0 to RT2 are defined for KiCad boards only.

## What Changes

- **Round-trip levels for Altium files.**
  - RT-A0: a container copy keeps every storage and every stream, byte for byte.
  - RT-A1: reading a file and encoding what was read gives equal records in every stream.
  - RT-A2: model → Altium → model is equal on what the writers write.
- **`fenolite check` on Altium input** (a document, a project file or a project folder), read-only
  and without any external tool. Stages: `model.validate`, `erc.lite`,
  `netlist.assignment_compare` (the schematic against the PCB document of the same project, and the
  built model against both), `roundtrip.rta0`, `roundtrip.rta1` and `roundtrip.rta2`.
- **`fenolite inspect` on Altium files**: kind, header version, counts, opaque content and model
  findings, in the result shape of the KiCad summary.
- **`fenolite diff A B`, added in general.** The model view compares any two inputs that a registered
  backend reads, or two `.fenolite/` folders. The records view compares two Altium files stream by
  stream and is Altium-only. No active change adds `diff`; v0.2a then only adds schematic kinds.
- **Corpus.** RT-A0 and RT-A1 run on every public Altium row and on Fenolite's own samples. RT-A2
  runs on Fenolite's own builds only: one deviation from the roadmap row (see Non-goals).

## Capabilities

### New Capabilities

- `altium-verification`: the three levels, the Altium check stages, the Altium summary, the records
  view and the corpus runs.

### Modified Capabilities

- `verification-loop`: MODIFIED "Check command input" (living text) and "ERC lite stage" (text of
  c0036); ADDED "Document check pipeline", "Document check issue codes" and "Model difference
  report".
- `cli-contract`: ADDED "Diff command"; MODIFIED "Inspect command" (text of c0039).
- `backend-protocol`: ADDED "Document sets and container round trips".
- `corpus-policy`: ADDED "Round-trip use on Altium rows".

## Non-goals

- No equivalence levels and no `equivalent` command: c0045. `diff` lists every exact difference;
  `equivalent` gives a verdict per level.
- No Altium DRC and no rule check: v0.4.
- No writer from an imported model. RT-A2 on a file that Altium saved needs one and waits for v0.4.
- No DIFAT sectors in `write_compound`: a file past the writer's limit is reported as not judged.
- No tree diff of KiCad files, and no `roundtrip`, `fmt` or `explain` command: v0.2a.
- No change to the KiCad stages, to their issue codes or to `run_checks`.
- No new format fact: the readers own them.

## Evidence level required

- RT-A0 and RT-A1 on public files: `CORPUS-VERIFIED`, with every unjudged file counted by reason.
- RT-A2 and the built pairs of the comparison: `INFERRED` (Fenolite's writers read by Fenolite's
  readers; `H-A-VER-RTA2`). The Altium build stays experimental.
- Schematic against PCB on public projects: the lowest of the two readings (c0043's
  `H-A-IMP-NETLIST`).
- `erc.lite` on Altium input: `INFERRED` (`H-A-VER-ERC`, with `H-K-CHECK-ERC`).
- `diff`: the lowest level of its two inputs. Its matching rules are Fenolite's own, checked by unit
  tests.
- No `ORACLE-VERIFIED` and no `ALTIUM-VERIFIED` claim: `kicad-cli pcb import` is c0045's triangle.

## Impact

- New: `src/fenolite/backends/altium/{docset,roundtrip}.py`,
  `src/fenolite/checks/{documents,containers,rta2,diff}.py`, `src/fenolite/cli/cmd_diff.py`,
  `docs/evidence/altium-roundtrip.md`.
- Changed: `backends/base.py`, c0043's `AltiumBackend`, `checks/codes.py`, `checks/erc_lite.py`,
  `cli/cmd_check.py`, `cli/cmd_inspect.py`, `tests/corpus/manifest.toml`, `docs/cli-contract.md`,
  `docs/altium.md`, `docs/roadmap.md`.
- Depends on c0039 to c0043 and on c0036. Archive order: c0036, c0039 to c0043, then c0044. c0029
  is independent.
- Size: 12.5 design-days.
