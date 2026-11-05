# c0402: deterministic work budget for the exact neck cut

## Why

c0332 bounds each exact neck cut of an Altium pour with one per-operation `Budget`. Its storage and work caps
count, but two of its bounds are wall time: `total_seconds=240` and `stage_seconds=120`, read at every
`Budget.check`, raise the same `ResourceLimit` (`GeometryError`, `FEN-3005`) as a real geometry refusal.
So the outcome of a conversion depends on how busy the machine is.

Evidence: dev CI run 41976474801, attempt 1, on e2c3a996, job `kicad-10` shard 1.
`tests/kicad/convert/test_triangle_large.py::test_difat` (`vme-wren`) raised
`ResourceLimit("exact geometry deadline exceeded during assembly")` from `_exact_snap._rings` through
`pour._certified_neck_cut` → `exact_difference`, while a 1990 s demo-06 import shared the runner. The probe
test redid the same conversion on the same worker and passed, and the rerun was green: same input, different
outcome. A write can fail on a slow machine.

## What

- Every `Budget.check` charges counted work units (one per call, or the iterations it stands for in loops
  that check every 256 or 1024 steps; `visit(n)` charges `n`). Two new caps, `Limits.work` per operation and
  `Limits.stage_work` per stage, refuse with `ResourceLimit` when used up: the same on every machine.
- The caps are sized from the work counted on every captured exact cut of the 27 c0332 cases, `vme-wren`'s
  131 cuts included, with a margin (design.md, "Sizing").
- Wall time stays only as a safety net, raised far above the caps' measured time (1200 s per operation,
  600 s per stage). It raises the new `ExactDeadline` (`FEN-1005`, exit 1, retryable), which is not a
  `GeometryError`, so no caller turns it into another result: the command stops and writes nothing.
- c0332's intent is kept: one bound per exact operation, every storage and work cap unchanged, no floating
  fallback.

## Impact

- `src/fenolite/geometry/boolean/_exact_noding.py` (`Budget`, `Limits`, `ExactDeadline`), the unit charges in
  `_exact_faces.py`, `_exact_snap.py`; the CLI registry (`FEN-1005`), `explain.toml`, `docs/cli-contract.md`,
  `docs/cli-surface.json`, the agent guide's error table.
- Tests that advanced a fake clock past 240 s now expect `ExactDeadline` past the safety net.
- No output byte, digest, evidence level or acceptance threshold changes: a cut that passed before passes
  with the same polygons.
