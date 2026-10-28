## Why

Task 9.4 of change c0175 ("Assembly marks", package 8), `fenolite testpoints --place`. `fenolite testpoints`
(c0118) reports which nets a probe reaches from a side, but closing the gaps is manual: for each uncovered net
the designer looks for room near its copper, adds a test point and draws its track, then hopes the fixture's
pitch and the clearances hold. Change c0212 left the task out, because the probes add parts and copper that the
design script lacks, so a rebuild might drop them, and because the search needs the clearance of every new pad
and track against every net, with a bench of its own.

## What Changes

- **Placement.** `fenolite testpoints PATH --place --side top|bottom [--grid LENGTH] [--reach LENGTH] [--size
  LENGTH] [--min-pitch LENGTH] [--nets GLOB]... [--drc] [--kicad-cli PATH]` adds one probe for each eligible net
  that the side does not reach: the test point of `design.test_point`, on a grid site within reach of the net's
  copper, joined by one straight track, nearest site first, each site kept clear of other copper, holes, the
  edge, courtyards, silkscreen and forbidding rule areas. The board is written under the mutation protocol.
- **Check.** Fenolite's copper check judges the board before and after; a probe it names is not written
  (`testpoint.check-failed`). `--drc` runs `kicad-cli` DRC on the board before and after, and refuses the write
  when a type grows (`testpoint.drc-new`).
- **Rebuild.** The probes are board-only footprints (no `fenolite.path`) and their tracks are board copper, so a
  rebuild of the design script keeps both (`docs/lens.md`, "Board-only footprints"); `sync` needs no change.
- **Report.** `result.place` holds the coverage before and after, the probes, the nets without a site and the
  DRC counts; the rest of the reply describes the board as it would be written.
- Four codes `testpoint.no-site`, `testpoint.check-failed`, `testpoint.drc-new`, `testpoint.board-only`; one
  hypothesis `H-K-TP-PLACE`; `silk.board.silkscreen_ink`, the silkscreen of a side as shapes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assembly-test-features`: ADDED "Test-point placement" (moved from c0175 and narrowed), "Probe sites",
  "Placed test points checked", "Placed test points kept by a rebuild" and "Test-point placement codes".

c0175 no longer holds a delta of `assembly-test-features`.

## Non-goals

- **Carrying probes into the design script** (`sync`): a board-only footprint is already kept by a rebuild, and
  writing `design.test_point()` calls would need the script's net variables. The info `testpoint.board-only`
  says how to move them into the script by hand.
- **Probes on vias or on existing copper without a track**, through-hole probes, and probes shaped otherwise
  than a round surface pad: the probe is the default `design.test_point` (round, surface).
- **Part bodies** other than courtyards: the courtyard stands for the body, as in c0212.
- **Refilling zones**: a fill of another net is an obstacle as stored; a probe inside it is not tried.
- **Altium boards**: `--place` writes KiCad boards only.

## Evidence level required

`INFERRED` without `--drc` (`H-K-TP-PLACE`); `KICAD-VERIFIED` with `--drc` and no new DRC type. The oracle
benches run with `kicad-cli` 10.0.7 locally and in the jobs `kicad-9` and `kicad-10`.

## Impact

- New: `src/fenolite/exports/testpoint_place.py`, `tests/_tpbench.py`,
  `tests/unit/exports/test_testpoint_place.py`, `tests/kicad/assembly/test_testpoint_place_oracle.py`. No test
  data file is added: the benches are written in the tests.
- Changed: `src/fenolite/cli/cmd_testpoints.py`, `src/fenolite/exports/codes.py`, `src/fenolite/silk/board.py`
  (`silkscreen_ink`), `cli/data/explain.toml`, `docs/cli-contract.md`, `docs/assembly.md`,
  `docs/formats/kicad/drc.md`, `docs/hypotheses.md`, the guide page `board-assembly` and the generated
  `commands`, `CHANGELOG.md`, `openspec/README.md`, and c0175's `tasks.md` and its `assembly-test-features`
  delta (removed).
