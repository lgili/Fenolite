# Quantization contract audit — before another realization

Reviewed source: clean ea7d3df4. The failed full-reference program and rejected
candidate stay immutable; this audit does not make their local-turn-sign gate
pass. Raw authored geometry/programs stay external.

## Normative obligations read

- Living `geometry-boolean-backends`, "Boolean protocol": nonzero signed input,
  integer normal-form output, and vertices within sqrt(2)/2 nm of the exact
  result. It does not state preservation of every local curvature sign.
- Living `geometry-kernel`, "Exact segment classification and intersection":
  `round_point` rounds each coordinate half to even.
- Living `geometry-kernel`, "Polygons with holes and a normal form": outer/hole orientation,
  collinear removal and exact integer/Fraction predicates. This whole-ring
  orientation requirement differs from each local vertex's turn sign.
- Living "Stdlib fallback limited to convex intersection" explicitly permits
  convexity within 1 nm after prescribed rounding; it is not an exact local
  curvature-sign invariant.
- Active c0215 keeps signed nonzero Boolean operations and the union's original
  boundary-vertex guarantee. c0328 additionally protects its five source
  corners, retained topology and whole-face debris eligibility. None of these
  findings authorizes dropping an original protected vertex or its nonzero turn.

The full experimental plan strengthened this to every original local turn's
sign. Its source refusal is valid under that extra condition. Before changing
rounding, prove separately whether the actual quantization obligations hold.
Do not increase the living sqrt(2)/2 nm bound or introduce another grid.

## Independent proof proposed

External `audit_quantization_contract.py`:

1. Reproduce the strict sign refusal on a new authored nine-edge integer Boolean
   input. Retain exact signed faces, a rational node that rounds onto a fixed
   original vertex and the changed local turn. The old verifier must still fail.
2. Independently verify unique half-even projection per canonical exact node:
   each axis error is at most 1/2 nm and squared Euclidean error at most 1/2 nm.
   Keep integer source points exact. Check every retained nonzero source turn
   remains a nonzero vertex, with local signs reported separately.
3. Prove duplicate/collinear cleanup preserves the exact geometric point set
   of each retained projected polyline. Use primitive integer line keys and
   merged closed intervals; do not merely compare areas or signed currents.
   This transfers the linear edge interpolation error bound to the final
   boundary in both directions, without sampling or tolerance acceptance.
4. Retain whole-ring orientation, simple rings, hole parentage, contact points
   and cyclic incident-ray order, and all existing whole-face loss certificates.
   A dropped long backtracking spike cannot pass by having zero signed area.
5. Validate planted over-bound displacement, missing protected source vertex,
   and geometric cleanup loss. Run the same certificate over all 84 closed-ring
   controls and the complete cached source geometry with exact artifact hashes.

Proof command:

```sh
.venv/bin/python "$FENOLITE_QUANTIZATION_SCRATCH/audit_quantization_contract.py"
```

The lemma is exact: paired points at equal edge parameter differ by a convex
combination of endpoint error vectors, bounded by sqrt(2)/2. Equal projected
and cleaned polyline point sets preserve this bidirectional boundary bound.
It applies only to retained loops; every removed whole face still requires its
separate existing-policy certificate. Resource limits remain those of the full
plan; no exhaustive source Fraction cross product may run.

Audit success may establish a different, contract-appropriate certificate. It
cannot rewrite the old failed sign experiment as passed, close production/CI
gates, change fixtures/tolerances or choose a platform golden. Root review and
an explicit separate implementation design remain mandatory before production.

## Actual independent certificate — 2026-11-02

Clean signed 7da6157d runs the separately authored audit, exit 0. Its
[source-bound report](../../../docs/evidence/quantization-contract-audit.json)
retains all program/input/contract/runtime hashes. All 84 earlier positive
controls still pass the unchanged strict program, and the separate audit
checks normal form, same-scale subdivision and translated-back invariance.
The new nine-edge integer Boolean witness has analytically derived exact
intersections and area. Its strict local-sign test refuses, while the actual
half-even, nonzero-vertex, whole-ring and quantization obligations hold.

The complete cached source preserves all 3601 original nonzero boundary
vertices. It has exact equality of each retained projected and normalized
polyline point set, with unchanged simple-ring/contact/nesting certificates.
Maximum axis error is 1474/3029 nm; maximum squared Euclidean error is
4345352/9174841 nm², below 1/2. All 430 removed whole faces are independently
rechecked against exact/integer area and parent provenance. The retained loops'
continuous bidirectional boundary bound follows from the proved interpolation
lemma, not a finite raster or sampled distance test.

Planted over-bound displacement, protected-source-vertex deletion, whole-ring
orientation inversion and a zero-area but geometrically long cleanup spike
all refuse. The sign-changing source output remains identical to the earlier
rejected output, and its seventeen local sign changes remain recorded. This
audit does not retroactively pass that stricter experiment or approve production.

Root conclusion: increasing the grid/error allowance to preserve every local
curvature sign would violate the existing precision contract and is not the
next correction. A separate implementation design may use a certified exact
boundary/half-even pipeline with these actual obligations, while retaining
the original corner, signed-selection, topology and whole-face protections.

Metadata validation passes 53 hypothesis/register/evidence checks (27.66 s),
strict OpenSpec and whitespace checks; the generated matrix is current.

Before choosing an implementation scope, observe the original guarded operator's
own Fenolite caller stack and its declared integer `tol`/`width` parameters.
An external `capture_operator_context.py` may retain the original output and
its separately computed existing-policy output, compare mandatory source
vertices, and verify all 188 old Mac trace operations still match. Capture
only repository-relative Fenolite function/line names and those two integers,
never arbitrary frame locals or unrelated projects. This is diagnostic only.

## Policy-order review before any production design

The frozen reference removes small holes before testing a piece's net area.
The actual `_without_debris` tests net piece area first. These operations do
not commute: an authored area-9 outer square with an area-1 hole at `tol=3`
has net area 8 and must disappear, rather than become an area-9 solid square.
Keep the frozen reference and its earlier receipts immutable; its controls
did not establish this generic ordering obligation.

Before production, a separate external `audit_debris_policy.py` must:

1. Reconstruct every projected source loop before any removal, require simple
   noncollapsed loops and prove collapsed loops have identically zero signed
   line currents. Zero shoelace area alone is insufficient (a bow tie is a
   planted negative control).
2. Group all noncollapsed holes with their original parent, normalize, and
   apply the unchanged runtime `_without_debris` once. Require exact equality
   with the supplied source candidate, including normal form and ordering.
3. Prove the thin-piece control above drops the whole piece with its hole;
   reject the frozen reference's hole-first result. A whole-piece certificate
   owns its children and uses net area before any hole removal.
4. Retain source/input/script hashes, all checked counts, both control results,
   exact net areas and the caller-context receipt. This is an audit only;
   failure cannot authorize a replacement policy or a larger error bound.

Proof: `.venv/bin/python "$FENOLITE_QUANTIZATION_SCRATCH/audit_debris_policy.py"`.
Run on a clean signed source. No production code, fixtures or prior receipts
may change. Record any additional source topology failure explicitly.

### Actual policy audit

On clean signed f4351129, the separate command exits 0 in 0.823 s.
The [aggregate receipt](../../../docs/evidence/boolean-debris-policy-audit.json)
binds every program/input and the unchanged runtime. All 414 noncollapsed
source loops are simple and retain orientation; all 27 collapsed loops have
identically zero signed line currents before and after cleanup. Reconstructing
the original grouping gives one normalized piece with 413 holes. Applying
the unchanged piece-before-hole policy gives exactly the earlier one-piece,
ten-hole candidate (SHA-256 923aaa891d6ade45f20cae028ca7fb7894cf6780cc6459bc9b72e494e3e8af17).
All 430 whole-face losses are certified with original parent ownership.

The area-8 thin-piece control disappears with its hole. The immutable frozen
reference instead returns an area-9 solid square; the independent certificate
rejects that result. A zero-shoelace-area bow tie is also rejected as a fake
collapse because its signed interval currents are nonzero. This closes the
generic policy-order gap in the audit, not in production or the old prototype.

The original source trace identifies `_Geometry.open`'s final neck-removal
difference, with width 127000 and tolerance 3175 nm. All 188 archived operations
still match. Of 3601 mandatory source vertices, 447 are absent from the original
postpolicy vertex list and restored with nonzero turns in the exact candidate;
the earlier five witnesses were a subset. Raw positions/caller diagnostics stay
external. A production design should scope a certified difference to this
semantic final-cut operation, with no fixture/hash/platform special case.
