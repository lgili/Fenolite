# Full indexed realization: source candidate refused

Actual maintainer-host experiment, 2026-11-02, on clean signed fc933419.
The [machine-readable report](boolean-full-reference.json) binds source,
programs, operands, candidates, controls and failed certificates. Raw authored
geometry and programs stay in `fenolite-cac-full-reference-20261102` externally.
No production source, schema, dependency, tolerance, golden or native file changes.

## Bounded proof and reviewed source run

The new independent exact reference passes 84 closed-ring controls before
source mode. They compare known exact areas, direct finite-displacement and
symbolic/propagated winding, signed cancellation, self-crossings, contacts,
sub-grid collapse, same-scale exact subdivision, order/direction/start and
translated-back outputs. Planted wrong winding, unqualified retained loss and
both local/global accumulated-area budget failures are detected. One projection
per canonical rational node is checked, including shared contact vertices.

The initial 72-case implementation and first source failure remain archived.
Pre-source review strengthened incomplete checks; the resource audit separately
bounds local coordinates/predicates at 256 bits and accumulated areas at 4096
bits. The first implementation did not enforce the aggregate-area bound and
therefore supplies no complete resource-proof pass. The final program enforces
all declared limits; improving these guards does not change its geometry or
the rejected candidate hash.

Actual final commands:

```sh
.venv/bin/python "$FENOLITE_FULL_SCRATCH/prove_full_reference.py" --controls
# exit 0: all 84 controls and declared negative checks pass
.venv/bin/python "$FENOLITE_FULL_SCRATCH/prove_full_reference.py" --source
# exit 1: retained original turn signs invert
.venv/bin/python "$FENOLITE_FULL_SCRATCH/verify_refutation.py"
# exit 0 verifies the refusal and its evidence; source acceptance stays false
```

## Full result

Only the previously proved 20346 candidates enter exact full noding; no full
quadratic Fraction enumeration occurs. The graph preserves signed operand
currents and source-edge provenance. All component Euler identities, opposite
halfedge coverage, face-area sums and winding consistency pass.

| Measurement | Actual |
| --- | ---: |
| Original input edges | 8058 |
| Exact nodes | 7889 |
| Exact subedges | 10334 |
| Intersecting candidate pairs | 16018 |
| Connected arrangement components | 107 |
| Face cycles | 2659 |
| Exact selected boundary loops | 441 (28 positive, 413 negative) |
| Canonical boundary nodes projected once | 5822 |
| Half-tied canonical nodes | 0 |
| Whole collapsed pieces certified | 27 |
| Whole debris holes certified | 403 |
| Retained original turns with inverted signs | 17 |
| Affected retained rings | 8 |
| Missing coordinates among those original vertices | 0 |

The final diagnostic runs in 2.697 s with peak memory 67289088 bytes and 908502
seed-segment visits. Maximum observed coordinate/local/area rational sizes are
54/83/500 bits; every declared numeric, graph, time and memory cap is respected.

The rejected post-policy candidate has one polygon, ten holes and 4680 vertices;
its canonical polygon SHA-256 is
`923aaa891d6ade45f20cae028ca7fb7894cf6780cc6459bc9b72e494e3e8af17`.
This is neither a native file nor a replacement golden. It is explicitly
rejected despite passing simple-ring, nesting and contact checks.

Each of the 430 removed whole faces has both exact and integer area below the
existing 3175² nm² floor. Those certificates cannot justify altering a turn on
one of the eight retained rings: even the smallest affected ring has area at
least 909383 times that floor. The independent audit confirms the exact negative
and final integer positive turn from the actual rejected ring neighborhoods;
the source coordinates themselves remain present.

## Consequence and remaining gates

The fixed canonical half-even realization does not satisfy the declared
full-source retained-turn-sign obligation. No half ties exist among its 5822
nodes, so a different tie-breaking rule cannot rescue this particular fixed
projection. A fresh realization hypothesis requires a separately declared
experiment and review; removing the failed check, selecting a platform result
or silently accepting the inversion is not a correction.

The historical bounded c0328 results remain scoped to their original inputs.
Their unavailable legacy programs were not rerun under a new identity. The new
refutation auditor's exit 0 proves a failed obligation, not a successful source
realization or a complete CAC/CI gate. c0328 tasks 2.2/2.3 remain open, and the
Mac byte guard remains failing. No publication or production change is approved.
