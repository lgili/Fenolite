## Why

c0013 runs KiCad's DRC on a project copy, proves with a canary that custom rules loaded, and counts the report; it judges nothing. v0.1 needs more (plan item 0013, part 2): located findings, a net-assignment check against KiCad's IPC-D-356 export (S-0019, S-0020), RT2 over the corpus, and two located negative tests. The report's `type` has no enumeration and its items carry only uuids (S-0055, S-0056), so codes and REF-PIN locations need proofs. The `kicad-9` job fetches no corpus, which blocks RT2 on 9.0. Four format measurements that c0005 to c0009 deferred land here.

## What Changes

- `checks/drc_json.py` (new): one issue per violation, `kicad.drc.<type>` with `_` replaced by `-` (issue codes forbid underscores), KiCad's severity, the raw type in `result`, and `where` as REF-PIN through pad uuids.
- `checks/assignment_compare.py` (new), stage `netlist.assignment_compare`: the model, the re-read pads and IPC-D-356 compared as partitions of REF-PIN elements, with `min_pins=1`; uncovered pads are reported as coverage.
- `backends/base.py`: `NetlistOracle`, `RoundTripOracle`, `PadNetList`, `NetlistOutcome`, `Rt2Outcome`. `backends/kicad/padnets.py` (new) moves c0009's record-to-pad matcher into `src`; `KicadOracle` gains `netlist` and `rt2`.
- `checks/rt2.py` (new), opt-in stage `roundtrip.rt2`: on 10.0 both sides are normalised with `pcb upgrade` (not `third-party-pcb-02`), item uuids are masked, and DRC runs twice on the original so unstable violations are excluded and counted.
- Negative tests on 9.0.9 and 10.0.6: a reassigned pad net (assignment compare) and a track bridging two nets (`shorting_items`), each located. c0018's overlapping-rules bench, canary included, is the permanent positive control.
- Corpus: RT0, RT1 and RT2 on the 21 readable non-heavy demos and the upgraded third-party copies (10.0.6), and on rows tagged `rt2-9` (9.0.9). The `kicad-9` job caches and fetches only those rows.
- Measurements, never gates: observed token paths against the inventory, `test_byte_identity_kicad10`, a 5 MiB read-and-write benchmark, and Edge.Cuts chaining for c0005's snapping question.
- Docs and evidence pages; sources S-0090 and S-0091; hypotheses `H-K-DRC-TYPES`, `H-K-DRC-UUID`, `H-K-DRC-MEASURED`, `H-K-PRO-SEV`, `H-K-NET-IPC`, `H-K-RT2-STABLE`, `H-K-TOK-CENSUS`, `H-G-EDGE-EXACT`.

Budget: 8.75 days against the roadmap's 6.75; the measurements are the first cut (design, "Budget").

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `verification-loop`: findings, assignment compare, RT2 stage, codes, negative tests; MODIFIED "Check command input" and "DRC stage and the rules canary" (c0013's texts copied).
- `backend-protocol`: netlist and round-trip oracles.
- `kicad-oracle`: netlist oracle, RT2 oracle, DRC facts per major, corpus round trips; MODIFIED "Check canary injection" (its first sentence, after c0013's two-run fallback).
- `ci-baseline`: MODIFIED "KiCad 9.0 oracle job" (full text copied).
- `corpus-policy`: rows tagged `rt2-9`.
- `kicad-token-inventory`, `kicad-sexpr`, `kicad-file-backend`: the four measurements.

## Non-goals

- Zone fill (c0015), routing (c0016), placement and outline assembly (c0022), exports (c0024), the second example board (c0025), layout preservation (c0019).
- `--schematic-parity`, `sch export netlist` and `sch erc` (v0.2a).
- Changing the printer to KiCad 10's layout; the exhaustive 8.0 vocabulary (v0.5a).
- Measured-distance analysis: `H-K-DRC-MEASURED` is registered and stays pending (v0.3).
- New FEN codes, model or schema changes, an ADR; `rule_severities` as model data (from c0010) goes to v0.2b's full rules.

## Evidence level required

- Type names, severities, item uuids, negative tests, positive control and IPC-D-356 matching: `KICAD-VERIFIED` on 9.0.9 and 10.0.6 (`H-K-DRC-TYPES`, `H-K-PRO-SEV`, `H-K-DRC-UUID`, `H-K-NET-IPC`).
- RT2: `KICAD-VERIFIED` on 10.0.6 (24 boards) and 9.0.9 (5 boards) once `H-K-RT2-STABLE` settles.
- `netlist.assignment_compare`: the lowest of the reader's `INFERRED` (`H-K-PCB-READ`) and the export's level.
- Token census and Edge.Cuts chaining: `CORPUS-VERIFIED` when both origins give 0; byte identity and throughput are recorded only.

## Impact

- The modules above, plus `checks/{drc,stages,codes}.py`, `cmd_check.py`, `ci.yml`, the corpus manifest and tests.
- Registers: `sources.md`, `hypotheses.md`, `PROVENANCE.md`, `LEGAL-ANNEX.md`, probe files.
- No runtime dependency.
- Depends on c0013, which archives first, and through it on c0009 to c0011, c0017 and c0018.
