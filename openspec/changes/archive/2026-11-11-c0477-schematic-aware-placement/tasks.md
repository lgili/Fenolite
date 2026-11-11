# Implementation tasks

Proposed 2026-11-10. Every task is scoped to at most one design-day. Implement in order and
mark a task only after its proof runs successfully. Split a task before implementation if
its scope grows. The test paths below name deliverables. Phase 1 yields a useful scoped
placer before whole-board work. Optional solver experiments have an explicit keep/discard
decision. Follow [evaluation](evaluation.md) for benchmark controls and acceptance.

## 0. Scope, inputs and evidence

- [x] 0.1 Confirm target placement scopes, existing lock/copper/readback semantics, supported
  KiCad targets and route adapter capabilities. Record source facts, evidence hypotheses
  and stable subject IDs for the authored control fixtures.
  Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  2026-11-10: passed. Scope audit recorded in evaluation.md; topology evidence registered as UNKNOWN.
- [x] 0.2 Define versioned neutral input/result contracts and fixtures. Verify stable IDs,
  request validation, unknown data and legacy constrained request compatibility.
  Proof: `uv run pytest tests/unit/placement/test_optimization_contract.py -q`.
  2026-11-10: 7 passed. Initial request/result schemas are internal until CLI integration.

## 1. Schematic intent and scoped placement

- [x] 1.1 Build resolved instance/net/pin/pad incidences. Cover hierarchy, duplicate pad
  numbers, multi-unit parts, bus members, net ties and drawings rearranged without net edits.
  Proof: `uv run pytest tests/unit/placement/test_placement_topology.py -q`.
  2026-11-10: repeated-instance, duplicate-pad and mismatched/missing binding proofs passed.
- [x] 1.2 Add provenance, conflicts and precedence for declared, confirmed and suggested intent.
  Cover required unresolved bindings, a board-only explicit request and approval round trip.
  Proof: `uv run pytest tests/unit/placement/test_placement_intent.py -q`.
  2026-11-10: 2 passed. Suggestions remain inactive, conflicts and missing pad identities do not fall back.
- [x] 1.3 Implement decoupling and bulk suggestions, per-bank pad assignment, ambiguous shared
  rails and DNP handling. Test separated rails and declared shared coverage.
  Proof: `uv run pytest tests/unit/placement/test_placement_decoupling.py -q`.
  2026-11-10: 4 passed. Resolved supply/return matching and bounded coverage use explicit
  bank metadata and reviewed eligibility. Placement-dependent costs and routing remain later tasks.
- [x] 1.4 Implement oscillator, load-capacitor and series/protection chain suggestions from
  resolved terminals. Cover ambiguous direction, repeated sheets and clock module negatives.
  Proof: `uv run pytest tests/unit/placement/test_placement_clock_and_signal.py -q`.
  2026-11-10: 3 passed. Suggestions preserve exact terminals and expose ambiguous load or direction.
- [x] 1.5 Map confirmed hot loops, gate/return, bootstrap, Kelvin and isolation into placement
  objectives. Test overlapping groups, exact pad roles and unknown or invalid loop geometry.
  Proof: `uv run pytest tests/unit/placement/test_placement_power_intent.py -q`.
  2026-11-10: 3 passed and placement pyright passed. Duplicate references remain unresolved.
  Loop area is a planar proxy and isolation retains the explicit rule identity for checking.
- [x] 1.6 Resolve scope and immutable poses and detect attached copper, fill and protected
  regions. Verify inputs from both board and source precedence. Cover unsupported attachment.
  Proof: `uv run pytest tests/unit/placement/test_optimization_protection.py -q`.
  2026-11-10: 3 passed. Board/source locks and saved copper remain protected. Unprojectable
  or netless copper leaves attachment unchecked. Source-lock and protected-group IDs are adapter inputs.
- [x] 1.7.1 Generate bounded finite domains from conservative oriented envelopes, region intersections,
  allowed rotations and supplied anchors. Preserve the current pose when allowed. Test exhaustion
  and rotation coverage at small budgets.
  Proof: `uv run pytest tests/unit/placement/test_optimization_domains.py -q`.
  2026-11-10: 3 passed. Sampling interleaves orientations, bounds work, and keeps a legal
  input pose within the conservative bounds. Exact projection and legality follow in 1.7.2.
- [x] 1.7.2 Project poses through the backend, preserve pad identities and check exact geometry.
  Reuse hard checkers for polygons, enclosed cut-outs, drills and mechanical limits. Cover
  asymmetric pads, protected overhang, footprint-owned copper and missing checkers.
  Proof: `uv run pytest tests/unit/placement/test_optimization_pose_projection.py -q`.
  2026-11-10: 3 passed. Same-side pose keeps local copper and pad IDs on KiCad readback.
  Enclosed cut-outs and unqualified overhangs are rejected. Missing verifiers stay explicit.
- [x] 1.8 Implement bounded beam search and propagation. Prove the early-choice trap, order
  invariance, exhaustion, cancellation, complete vs partial outcomes and stable ranking ties.
  Proof: `uv run pytest tests/unit/placement/test_optimization_search.py -q`.
  2026-11-10: 4 passed. Forward checks spend the same work budget as evaluations.
  The shortlist excludes partial and unchecked states. The search does not prove global feasibility.
- [x] 1.9 Add local translations, rotations, swaps and bounded neighborhood reassignment.
  Compare with a tiny exhaustive pose domain and test fixed-neighbor preservation.
  Proof: `uv run pytest tests/unit/placement/test_optimization_refine.py -q`.
  2026-11-10: 2 passed. Joint swaps match an exhaustive small control and leave fixed
  neighbors untouched. The incumbent is rechecked and preserved when the budget ends.
- [x] 1.10 Expose the opt-in read-only CLI proposal and scoped metrics. Verify canonical result,
  stable units, no accidental write and compatibility with existing place modes.
  Proof: `uv run pytest tests/unit/cli/test_place_optimization_proposal.py -q`.
  2026-11-10: passed. The authored KiCad fixture yields repeatable poses and keeps its
  locked connector. Impossible required distance produces no candidate. Exploration stages
  no writes. Combined placement, CLI contract, schema and guide regression: 495 passed.
- [x] 1.11 Add exact candidate review and staged-byte confirmation with checked readback.
  Test forged result data, stale inputs, rollback, source rebuild and preserved topology.
  Proof: `uv run pytest tests/unit/cli/test_place_optimization_plan.py -q`.
  2026-11-10: 7 passed. Review stages exact moves with checked readback. Tests cover stale
  rules during and after review, forged poses, rollback, rebuild and Altium format export.
- [x] 1.11.1 Support read-only Altium proposals and converted-copy application.
  Proof: `uv run pytest tests/unit/cli/test_place_optimization_altium.py -q`.
  2026-11-10: 3 passed. Both native inputs produce proposals, and the authored board survives
  conversion, reviewed placement and Altium export without changes to the original files.
- [x] 1.11.2 Qualify opening the exported board in Altium Designer. Record version, native
  positions, save/reopen and DRC observations. Direct native source edits remain gated
  separately by the existing Part J phase B evidence.
  2026-11-11: Altium Designer 24.5.2.23 opened, saved and reopened the authored
  exported blink board. All three poses survived exactly. The position and DRC
  results and the input, saved board and report digests are in evaluation.md.

- [x] 1.12 Exercise declared high-speed, RF and enclosure constraints as board and request
  fixtures. Cover a mirrored connector, differential escape width, per-layer antenna
  restrictions, connector access and a tall body. Report unsupported fixture inputs.
  Proof: `uv run pytest tests/unit/placement/test_optimization_assembly_and_pairs.py tests/unit/cli/test_place_optimization_escape.py -q`.
  2026-11-10: connector face, antenna keepout and enclosure/access cases pass.
  The paired lane preserves the full width and gap in the capacity estimate. The
  unsupported coupled escape is refused rather than routed as one leg.

## 2. Routability scoring and electrical proof

- [x] 2.1 Build directional layer capacity from conservative geometry and per-net demand.
  Proof: `uv run pytest tests/unit/placement/test_placement_routability.py tests/unit/cli/test_place_optimization_escape.py -q`.
  2026-11-10: rectangular-board adapter derives per-layer cuts, obstacles and per-net demand
  from candidate geometry and rules. A full cut blocks a known wide net and an indivisible pair
  fails a fragmented cut. Unknown layer tables, dimensions and unsupported geometry are explicit.
  - [x] 2.1.1 Implement the cut accounting for supplied geometry and demand.
    Proof: `uv run pytest tests/unit/placement/test_placement_routability.py -q`.
    2026-11-10: 2 passed, including an indivisible pair, disjoint free intervals,
    zero capacity, unknown layers and unknown widths.
- [x] 2.2 Add exact pad escape probes and fixed scope/budgets through the existing router.
  Report unsupported checks and equal-scope comparison. Test blocked exits and cancellation.
  Proof: `uv run pytest tests/unit/cli/test_place_optimization_escape.py -q`.
  2026-11-10: 4 passed. Exact reviewed same-net pad IDs, blocked exit, cancellation,
  shared provisional occupancy, exhausted work and confirmation without routed copper.
  Coupled nets, via-based escape and unsupported geometry are refused explicitly. The
  same file also contains the two board-derived capacity proofs for task 2.1.
- [x] 2.3 Check critical returns and group coexistence with provisional shared occupancy.
  Verify a failed coupled probe cannot become a successful isolated route, and that probes
  never modify source board, fill or decision bytes.
  Proof: `uv run pytest tests/unit/cli/test_place_optimization_probes.py -q`.
  2026-11-10: 2 passed. Both exact gate-loop legs must coexist. A blocked return clears
  the provisional success of the drive and the input board stays identical. The ordinary
  and coupled controls are in 2.2. Plane and differential routing remain unsupported.
- [x] 2.4 Feed probe blockers into bounded refinement. Compare distance-only, electrical,
  capacity and feedback variants on the planted shorter-but-blocked case.
  Proof: `uv run pytest tests/unit/cli/test_place_optimization_feedback.py -q`.
  2026-11-10: 1 passed. Distance-only, electrical and capacity controls precede a feedback
  run under the same declared budget. The feedback recovers a longer checked pose when
  the shortest pose of the electrical and capacity controls hits the routing limit.
- [x] 2.5 Check the authored local benchmarks with the pinned native oracle targets and
  record a baseline for larger boards. Exercise locked connectors, bypass return and
  a switching stage with quiet sense. Run the native proof in CI.
  Proof: `uv run pytest tests/kicad/place/test_optimization_local_oracle.py -q`.
  2026-11-10: 2 passed on local KiCad 10.0.6. The bypass and gate-loop/sense fixtures
  retain their connector and existing copper, route both required nets and pass native
  check. The blink before/after control reports identical findings. The pinned CI matrix
  remains open. The larger-board baseline is recorded in 3.4.
  2026-11-11: The bypass and gate-loop/sense cases passed in both pinned KiCad 9 and 10
  oracle jobs in GitHub Actions run 43014842233.

## 3. Block floorplanning and scale

- [x] 3.1 Compose declared rigid and flexible blocks with exact reuse bindings, net domains
  and anchor constraints. Verify a stale block, shared component and external port.
  Proof: `uv run pytest tests/unit/placement/test_optimization_blocks.py -q`.
  2026-11-10: 2 passed. Exact reuse digest, pad and port validation, anchor poses,
  and distinct rigid and flexible domains are available through the Python API.
- [x] 3.2 Add coarse region planning from hierarchy and a multilevel hypergraph alternative.
  Test repeated channels, directed ports, feedback condensation and broad power hyperedges.
  Proof: `uv run pytest tests/unit/placement/test_optimization_floorplan.py -q`.
  2026-11-10: 3 passed. Direction uses declared ports, feedback stays together when it
  fits, and coarsening keeps repeated channels separate under the broad supply edge.
- [x] 3.3 Expand region alternatives with the scoped solver and refine contested boundaries.
  Verify no overflow becomes an omitted component and no group crosses a declared barrier.
  Proof: `uv run pytest tests/unit/placement/test_optimization_full_board.py -q`.
  2026-11-10: 2 passed. Local expansion checks full extents, retries adjacent regions
  within budget, and reports blocked and overflowing groups without omitting members.
- [x] 3.4 Evaluate two- and four-layer scale fixtures up to the target size and record
  baseline, holdout, failure cases and selected limits. Run native probes and DRC in CI.
  Proof: `uv run pytest tests/kicad/place/test_optimization_scale.py -q`.
  2026-11-10: 2 passed locally with KiCad 10.0.6. Each authored 150-part case takes
  150 placement evaluations, routes 75 connections and passes native DRC. These
  pre-seeded block cases provide a baseline. The pinned CI matrix remains open.
  2026-11-11: The two-layer baseline and four-layer holdout both passed in the
  pinned KiCad 9 and 10 oracle jobs. Each placed 150 parts and routed 75 connections.
  The block-origin scope, full-region refusal and wider-scale limits are in evaluation.md.
- [x] 3.5 Benchmark a seeded annealing or analytical seed against the measured baseline at
  comparable effort. Record the keep/discard decision and supported scope. No production
  strategy is added if this comparison does not justify one.
  Proof: `uv run pytest tests/unit/placement/test_optimization_solver_comparison.py -q`.
  2026-11-10: 2 passed. Annealing and beam search both reached exhaustive optima at
  234 evaluations. No production annealer was added on this six-part evidence.

## 4. Viewer and usage

- [x] 4.1 Show read-only proposal overlays, exact pad links, before/after objectives,
  scope and layer congestion. Prove static output is inspectable and has no write action.
  Proof: `uv run pytest tests/unit/view/test_placement_optimization_scene.py -q`.
  2026-11-10: 1 passed. Static export displays moves, exact pad links and before/after
  distances, scope, per-layer overflow and probe facts. The stale-digest control hides
  overlays. The pinned interaction proof remains in 4.3.
- [x] 4.2 Add served reviewed decisions and refinement from explicit scope. Test updated
  anchors, stale decisions and explicit plan confirmation.
  Proof: `uv run pytest tests/unit/cli/test_place_optimization_view_actions.py -q`.
  2026-11-10: passed with the real served action runner. An external anchor edit
  invalidates a staged plan, refinement uses the new board and current scope, and
  the selected updated pose writes only after explicit confirmation.
- [x] 4.3 Verify keyboard inspection, cross-probing and comparison in the pinned viewer job.
  Review references and differences there. Rebuild the committed viewer assets.
  Proof: `make viewer-check && uv run pytest tests/visual/test_placement_optimization.py -q`.
  2026-11-10: the assets reproduce locally. The Playwright 1.63.0 test opens an
  alternative by keyboard and locates its exact pads and net in the standalone
  page. The CI screenshot and reference review remain open.
  2026-11-11: The committed viewer bundle reproduced and the exact keyboard and
  pad/net cross-probe case passed in the pinned viewer job (126 visual cases selected).
  The authored capture shows both alternatives and the selected R1-2/D1-2 return
  measurement on LED_A. The new case uses interaction assertions, and the pinned
  suite also verifies the existing image references.
- [x] 4.4 Update placement and CLI docs and teach the public surface in the agent guide.
  Include an authored worked example and describe incomplete or unsupported results.
  Proof: `uv run python tools/gen_agent_guide.py && uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-11-10: the guide, CLI contract and worked blink instructions cover proposals,
  candidate confirmation, converted Altium export, scoped probes and the viewer.
  The Python block/region API and the served request binding are also documented.

## Closing

- [x] 5.1 Run focused proofs, local quick checks and residue scan. Verify the required full CI
  jobs on the commit proposed for merge, including native and viewer proofs. Record skips
  as missing evidence.
  Proof: `make check-fast && git diff --check` plus the required CI jobs.
  The placement schema proof runs with the locked development extra. It must collect and
  pass in a fresh CI environment with `uv sync --locked --extra dev --extra geo`.
  The static viewer proof reads UTF-8 HTML explicitly and passes with a Windows cp1252
  default for file reads.
  2026-11-11: Local check-fast passed 25,080 cases with 77 declared skips. The
  required exact-commit CI and coverage audit passed in GitHub Actions run 43014842233.
  Native CAD and viewer receipts record their specific executed cases.
- [x] 5.2 Record benchmark artifacts, tool versions, scope and observed evidence labels.
  Publish failed and unattempted cases with the successful cases.
  Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  2026-11-11: The evidence matrix check passed. The exact tested commit reproduces
  the bytes of the Altium save/reopen input. Scope, failures, unattempted cases and
  observed evidence are recorded in evaluation.md and the pinned job receipts.
- [x] 5.3 Update CHANGELOG for delivered behavior and validate the final spec and diff. Verify
  any final edits on the corresponding CI commit before archive.
  Proof: `openspec validate c0477-schematic-aware-placement --strict && git diff --check`.
  2026-11-11: Strict validation and diff checks passed. GitHub Actions run 43014842233
  verified a4ff6f02b8d672d4f8cc67ef7c56ee47be5757c2 with the delivered changelog and
  all executable changes. The subsequent archive updates OpenSpec and the changelog.
