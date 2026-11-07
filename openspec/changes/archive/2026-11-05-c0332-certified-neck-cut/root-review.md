# Root review of the actual semantic pilot

On clean signed e8552220, `pilot_neck_cut.py` exits 0 in 34.80 s. All 75 baseline
plans exactly reproduce the prior signed c8 map: 1172 files and ten strict
refusals. The semantic pilot also completes all 75 plans/1172 files and keeps
all refusals. Its only exact final neck cut has 8058 input edges and 20346
candidate pairs; all exact selection, projection, point-set/source-vertex,
contact/nesting and correct-order debris certificates pass. No run is interrupted.

Only `board_40parts@altium` changes: its PcbDoc becomes SHA-256
9e3cabd7ab7fb0e204fb23c521a63a2985997266f272352d690b3e9a2cd14a98.
The other changed file is `.fenolite/build.json`: a separate payload-level
comparison proves its sole difference is `files/board_40parts.PcbDoc`'s hash.
All other 1170 file hashes match. This new mathematical result was not selected
to match either platform's earlier golden.

`review_pilot.py` exits 0 in 38.30 s. It rebuilds the full affected baseline once
and candidate twice: all 15 hashes repeat. Three additional complete exact
source cases independently reorder operands/holes, reverse every ring, and
rotate every ring start. All yield the same canonical geometry hash 923aaa89…,
with fresh positive certificates. All five review operations pass; original
functions and staging hooks are restored, and the checkout remains clean.

The [aggregate receipt](../../../docs/evidence/neck-cut-reviewed-pilot.json)
binds complete maps, original observations, scripts, resources and review.
Raw diagnostic geometry/native bytes remain external. The original strict
local-sign experiment still fails; no receipt promotes it or claims a native
Altium/compiler/CI success.

## Decision

The measured behavior and narrow scope justify proceeding with tasks 1.1–1.3
of the separate production design. This approves implementing and testing the
private per-call exact pipeline, not shipping the scratch globals or promoting
its bytes directly. Port each layer with analytic controls, declared bounds
and meaningful negatives. Re-measure the integrated caller; any new failure or
extra affected file stops golden updates and requires renewed review.

Keep public APIs, dependencies, persisted models/schemas and preceding opening
operations unchanged. Local fast validation and exact-head CI/native acceptance
remain separate gates. No push, golden refresh, merge or archive is approved.

## Integrated source and specific byte expectation

On clean signed 71d2ac93, the actual integrated writer (no monkeypatch)
reproduces all 75 reviewed candidate plans and all 1172 file hashes. All ten
strict refusals are unchanged. Relative to the original complete baseline,
only the board_40parts Altium PcbDoc and its build-manifest hash change;
1170 other files remain byte-identical. The manifest equals the independently
reviewed pilot payload. See `docs/evidence/neck-cut-integrated-plans.json`.

Together with the actual runtime certificates and 72 geometry/49 copper
tests, this approves precisely one byte expectation update: the
`board_40parts@altium` PcbDoc pin from 7f49a78f to
9e3cabd7ab7fb0e204fb23c521a63a2985997266f272352d690b3e9a2cd14a98.
No table regeneration or other byte update is approved. Run focused byte
tests and the complete local fast gate next. CI, native acceptance, push,
merge and archival remain separate pending gates.

## Additional callers: one bounded proposal before enumeration

Clean signed 7a3fe984 captures six representative actual failures before the
old expensive repair. They have 8–53 implicated noninteger nodes, including
13 nodes across four loops in board6 and 45/53 across role-board loops.
The initial capture intentionally refuses six tests; it is not a pass.

A distinct external pilot first proposes omitting the complete implicated
noninteger set, capped at 256 nodes and one proposal per cut. It retains the
one shared projection, real caller policy and every current certificate;
it does not relax a tolerance or modify production. All six actual tests
pass in 190.56 s, including all nineteen repair calls and repeated writes.
The independent audit passes all nineteen records/seven unique complete
contexts: source corners, exact/integer loss eligibility, real net-area-first
policy, retained orientation, contacts/ray words, nesting and gap-free
continuous covers. Duplicate reuse requires exact complete geometry-payload
hashes. A missing-interval negative rejects. The seven unique continuous
witness sets are generated separately; no runtime-capture claim is made.
See `docs/evidence/neck-cut-bulk-repair-pilot.json`.

Approve porting this single bounded proposal ahead of the existing exhaustive
fallback. Add a private 256-node proposal cap; retain the sixteen-node
enumeration cap and global 4096-trial cap (count nearest plus proposal),
distance/work/deadline limits and all certification/refusal guards. A zero
enumeration-node limit still disables repair. Never repeat the all-node subset
in fallback. An uncertified proposal may only proceed to bounded exhaustive
fallback; no result is returned without the caller's full certificate.

Before promotion, require an authored seventeen-independent-hairline proof,
proposal-cap and existing integer/error-bound negatives, actual failed-caller
reruns, focused copper/bytes and full 75-plan comparison. Combined fast, CI,
native acceptance, push, merge and archival remain pending.

## Reviewed continuous certificate for cleanup

On clean aed720d9 the two remaining buck_shunt-bad tests are refused by the
stronger projected point-set fast gate. A strictly external counterfactual
uses the existing complete continuous certificate on that cleaned loop,
keeping every other guard unchanged: both actual tests pass in 57.66 s.
The independent audit checks all three actual calls (one identical complete
geometry context), 57 gap-free bidirectional intervals, eighteen protected
source vertices, all integer canonical nodes, policy/ownership, orientation,
contacts and parents. The old point-set gate stays false. The separately
generated witnesses do not claim runtime capture. Interval-gap and missing
integer-node negatives reject. All seven prior bulk contexts also satisfy
the stronger integer-node retention check. See the aggregate receipt.

Approve a scoped certificate fallback: retain the point-set fast certificate
when it succeeds. Otherwise require every integer canonical boundary node
to remain on the integer curve, then prove complete bidirectional continuous
error within the unchanged sqrt(2)/2 nm bound. Apply the integer-node guard
to explicit-omission continuous repairs as well. Charge boundary scans to
the existing shared winding-work/deadline budgets. Keep source turns,
zero-current collapse, topology, orientation and exact/integer loss guards.
No approximate fallback, new tolerance, output fixture or golden update.
Require authored 0.6-nm positive/0.9-nm negative cleanup controls and preserve
the long integer-spike negative, followed by actual caller/byte/full-plan
proofs and final clean-source fast/CI/native gates.
