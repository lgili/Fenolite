## Context

Base: `8d74a798`, 2026-11-01. Read AGENTS.md, the batch working agreement,
the living geometry-kernel and copper-check specs, c0281's tolerance decision,
and the existing bottom-placement implementation before implementation.

## Decisions

### Exact arc cores — Decided 2026-11-01

Extend the existing thick shape with an optional three-point arc core. Its stored points
remain integer nanometres; circumcentres and squared radii are derived Fractions only.
Enumerate endpoint, circle/line intersection, circle/circle intersection and interior
stationary closest pairs. Decide radical signs by guarded exact squaring, including
equality, rather than bounded precision or a shrinking polygonisation tolerance.
Concentric arcs are covered by endpoint radial projections. Straight arcs remain segments.
Filled-ring containment uses an authored arc endpoint after boundary distances are checked.
Use true outward-rounded arc boxes for broad-phase queries. The old arc_tol argument
remains accepted and reported for compatibility; it does not affect clearance verdicts.

### Bounded engineering analyses — Decided 2026-11-01

Keep analysis.copper's polyline representation and its explicit arc_tol + 1 band.
Surface, pour and section consumers traverse those polyline cores directly. Exact
clearance checking does not make their bounded calculations exact. Compare the
builders through corresponding arc definitions, widths and polygonisations in the
shared-shape regression; require the check to retain its exact core independently.
The non-arc shapes continue to match exactly. This preserves the analysis API while
avoiding an unsafe reinterpretation of three stored arc points as a polyline.

### One clearance rule — Decided 2026-11-01

Exact shapes remove the reason for separate narrow/wide zone comparisons. Use the
resolved governing value minus the injected tolerance for every copper pair. Edge
clearance stays strict, as before. Floor positive reported gaps exactly to integer nm;
round witness coordinates half to even. No new FEN code is needed.

### Chamfer mirror — Decided 2026-11-01

The existing footprint mirror negates local Y, then makes angles absolute and flips
layers. Swap top_left with bottom_left and top_right with bottom_right in pad chamfer
tokens. Preserve chamfer ratio and all unrelated atoms. Apply the same involution when
deriving a library footprint from a bottom instance. Corner mapping is an INFERRED
geometric consequence of the existing verified mirror, not a new KiCad parity claim.
Feature-specific flip evidence joins builds only for definitions with bottom chamfers;
previously supported shapes retain their existing verified flip evidence.
Do not alter the Transform API or c0271's block pose convention.

## Evidence and risks

All math and tests are authored for Fenolite. Existing registered public format facts
cover three-point arcs, chamfer corner spellings and the bottom mirror; no third-party
parser material is read or transcribed. Near-boundary KiCad arc behaviour can differ
from ideal geometry: add oracle rows and leave 9/10 CI proof open until actually run.
Exact radical calculations cost more per candidate than segment tests; preserve indexed
line/ring candidate queries and avoid polygonising arc cores during checking.

### Integration with copper graphics (2026-11-01)

c0277 adds copper graphics. Its arc graphics must use the same exact circular core as routed arcs;
polygonising the graphic can miss a violation just below the tolerance at a point between samples.
An authored 3:4 radial bench compares the two item forms at equality, the 500 nm boundary and below it,
over three polygonisation settings. Keep one chamfer mirror, preserving source atom order and opaque
namesakes outside pads; applying both branches' mirrors would undo the transformation. These are
integration proofs, with no additional oracle or evidence promotion.

## Local measurements — 2026-11-01

The available local oracle is `kicad-cli` 9.0.2 (S-1010). The focused tolerance and
chamfer oracle command passed eight tests. On every rule/class/floor arc row it is
clean at c+1000, c and c-1 nm; it reports clearance at c-500, c-501 and c-2000 nm.
The exact ideal check with the injected tolerance is clean at c-500. This one
boundary difference is explicit; no old polygonisation band remains in its decision.
The chamfer oracle reports zero library mismatches at four authored rotations and
four mismatches for the wrong-corner control. Evidence remains inferred pending
the required exact-commit KiCad 9/10 CI jobs.
