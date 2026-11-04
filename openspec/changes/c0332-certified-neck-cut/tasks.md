## Disconnected — maintainer decision, 2026-11-04

Lote 12 (`cac/lote-12` 367e44b0, CI 41800749394) failed only the native KiCad 10 job
(and drawn-floor, which requires it): 28 failures, all from this change's exact
final neck cut. Pour row 03 took 86.6 s against the unchanged 60 s limit. The
others were proposal-node, enumeration-node, input-edge, deadline and nonsimple
refusals, on Altium rows 01, 04 and 05, on rta3 sets 02 and 03, on KiCad demos
01, 02, 07, 10, 11, 13, 16 and 17, and in DIFAT. The maintainer chose to
disconnect the exact cut and keep this change open: `_Geometry` calls the floating
`_without_debris(self.minus(...))` again, and `_certified_neck_cut` and its
modules and tests stay unchanged and unused. The Mac/Linux difference this change
addresses comes back for one file only: `board_40parts.PcbDoc` has its measured
macOS digest (c0323) in `tests/unit/test_build_bytes.py`. No budget, certificate
or other baseline changes. Reconnecting needs a redesign that passes every
caller above within the existing limits. Tasks 2.2 to 2.16 stay open for it.

## 0. Plan and external pilot

- [x] 0.1 Verify the free ID, read contracts and root-review the scoped design; strictly validate before coding. Proof: `npx -y @fission-ai/openspec validate c0332-certified-neck-cut --strict`; `git diff --check`.
  2026-11-02 on e807cc74: src/OpenSpec/local refs/all commit subjects contain
  no c0332. Root reviewed the living protocol, active c0215, actual c0328
  failure and independent contract/policy receipts. Strict validation and
  whitespace proof pass before new pilot code. Only the external pilot may
  proceed; no production approval is inferred from this checked planning task.
- [x] 0.2 Recapture all 75 baseline plans, compare all 1172 files and ten refusals, then measure the external semantic final-neck-cut pilot with exact certificates and bounded resources. Proof: `.venv/bin/python "$FENOLITE_NECK_CUT_SCRATCH/pilot_neck_cut.py"`; complete source-bound receipt, including failures.
  Clean signed e8552220, exit 0: all baseline maps match; all candidate plans
  complete, one certified 8058-edge cut, zero refusals and 1170 unchanged files.
- [x] 0.3 Review every changed file/failure and deterministic affected-case repeats before production. Proof: signed root review of the actual pilot receipt; passing a partial plan is insufficient.
  `review_pilot.py`, exit 0 on the same clean source: all 15 affected hashes
  repeat twice, the build manifest changes only its PcbDoc hash, and complete
  source order/direction/start variants agree. See `root-review.md` and the
  source-bound `docs/evidence/neck-cut-reviewed-pilot.json`. Production tasks
  may now proceed; integration, byte updates and complete gates remain open.

## 1. Conditional implementation

- [x] 1.1 After 0.3 approves, port private exact indexing/noding/selection with portable per-call budgets and analytic signed controls. Proof: focused exact-arrangement tests, ruff and pyright on touched modules.
  Index/noding portion now passes 18 focused tests and matches 269 frozen
  exhaustive bounded graphs, including all source directions/provenance.
  The full indexed 8058-edge graph also matches: 7889 nodes, 10334 fragments,
  20346 candidates and 16018 intersecting pairs. Ruff/format and module pyright
  pass; graph selection/face port is still required, so leave 1.1 open.
  See `docs/evidence/ported-exact-noding.json`; no caller uses this module yet.
  Clean signed 690e635c completes `make check-fast`: 20117 passed, 50 skipped,
  one existing Mac board-40 byte failure, make exit 2. Full source types,
  lint/format/generated pages and private-gated residue pass. The separate
  focused failure diagnostic captures the same old 01fdc848 PcbDoc against
  golden 7f49a78f, with 188 observed operations and zero observer errors.
  This does not pass the fast gate or finish the face/selection port.
  Exact logs/hashes and next external draft findings are in `validation.md`.
  Completed against base 69518b2a plus exact candidate hashes: the actual face
  port passes 38 focused tests, all 84 analytic/independent finite-winding
  controls and exact equality of all 441 cached source loops. Halfedge, face,
  shared winding-work and deadline refusals are tested, including corrupted
  dual currents and sixteen concurrent independent calls. Ruff/format and
  touched-source pyright pass. See `docs/evidence/ported-exact-faces.json`.
  Projection and caller integration remain open; final combined fast validation
  belongs to 2.1 and is not inferred from these focused proofs.
- [x] 1.2 Certify projection, source corners, topology, point-set cleanup and whole-face ownership; prove thin-piece and zero-current negatives. Proof: focused realization controls with planted failures.
  Against base ab9d17e6 plus exact candidate hashes, 55 focused geometry tests
  pass, including the real integer Boolean whose protected corner collapses,
  wrong half-even ties, new contacts, hole reassignment, a rounded bow tie,
  a long zero-current spike and exact/integer debris eligibility. The actual
  unchanged caller policy is applied between projection and certification.
  Two frozen independent auditors certify all 84 controls and the complete
  current source pipeline: 5822 nodes, 3601 protected vertices, 17 reported
  local sign changes and 430 eligible losses, with unchanged geometry hash.
  The fresh 269-graph/source noding comparison also passes after extending
  indexing to result boundaries. Ruff/format and touched-source pyright pass.
  See `docs/evidence/ported-exact-realization.json`. No caller/golden change
  or retroactive pass of the earlier strict sign experiment is claimed.
- [x] 1.3 Integrate only the final neck cut, retain safe FEN-3005 refusal and review all complete byte-plan changes before any specific golden update. Proof: focused pour/byte tests and full plan maps.
  The initial caller candidate has 2 failed/14 passed in its focused group:
  two existing engine cases have large projected holes with proper crossings.
  The actual inputs/exceptions are captured; promotion and golden updates stop.
  See `integration-refusals.md` for the bounded scratch-only lattice-feasibility
  diagnostic before considering an explicit revised realization design.
  The lattice search does not establish a solution. A distinct continuous
  shortcut proof then passes both actual cases, independently verified with
  planted interval-gap, integer-omission and endpoint-only failures. Root
  approves only the bounded, fully certified repair in the amended design/spec;
  its actual private port and focused caller/full-file proofs remain pending.
  The actual typed caller/repair port now passes all 72 geometry and 49
  pour/copper tests. The four actual formerly failing source contexts are
  independently reverified, including every runtime repair interval and the
  two qualified discarded inversions. Source hashes and scope are in
  `docs/evidence/neck-cut-actual-runtime.json`. Full 75-plan comparison and the
  explicit one-file byte review remain prerequisites to checking this item.

## 2. Combined validation

- [x] 2.1 Run local make check-fast and focused tests on the final combined signed source; record exact failures without bypasses. Proof: complete local logs and source SHA.
- [ ] 2.2 Only with explicit push authorization, require exact-head CI and required native acceptance before merge/archive. Proof: exact commit/job/native receipts; interrupted or partial jobs do not pass.

Integrated proof — 2026-11-02: clean signed 71d2ac93 reproduces all 75
reviewed candidate plans/1172 files, preserving ten refusals and 1170 baseline
file hashes. Root review approves only the one board_40parts Altium PcbDoc
expectation. After that specific update, all 76 byte tests pass in 18.62 s.
Actual runtime geometry/copper controls remain 72/49 passed. Task 1.3 is
satisfied; the final combined fast gate and CI/native gates remain open.

Broader integrated gate — 2026-11-02: reopen 1.3. The 75-plan and focused
byte proofs passed, but the broader fast attempt on 8e42f61d observes 18 failed,
20145 passed and 50 skipped before an intentional interruption after 1931 s.
One diagnostic misses the newly integrated exact operation; seventeen other
failures include genuine projected self-crossings and repair node/deadline
limits on board6, role examples and the authored PCB kits. Preserve all
certificates and limits; repair these callers before promotion. First extend
the same-run observer to include the actual final cut, retaining strict
assertions and exactly-once/restoration behavior. Then capture the additional
geometry outside the repository and review bounded repair improvements.
Task 2.1 remains open; no interrupted run passes.

Additional-caller review: six intentional diagnostic refusals are captured
on clean 7a3fe984. The distinct bounded single-proposal pilot then passes
all six actual tests/nineteen repairs. Independent complete-policy/source/
topology/continuous audits pass all nineteen records, deduplicating seven
identical complete contexts by hash, and reject an interval gap. Root approves
only the scoped port described in root-review/design; task 1.3 remains open
until actual implementation and broader caller/file proofs pass.

Actual scoped port: 75 geometry tests pass; source lint/format/types pass.
The expanded actual caller/byte/observer group is 181 passed / two failed.
Both failures are buck_shunt-bad cleanup point-set refusals; retain their
strict assertions and investigate with exact continuous/source-corner
certificates. All 75 complete plans/1172 hashes reproduce the reviewed map.
Task 1.3 and final fast/CI/native gates remain open.

Final actual integration proof: clean signed d348705f completes all75plans/
1172files, exactly matching the reviewed integrated map and ten refusals.
All183expanded caller/copper/byte/observer tests and77geometry tests pass
with original assertions. The specifically reviewed single golden update
remains the only one. Task1.3 is satisfied; 2.1/2.2 remain separate pending
clean-source fast and exact CI/native acceptance gates.

Final clean checkpoint fast proof: signed e26589420db604771f0a884b962a0546a2283e43
passes `make check-fast PYTEST_MAX_WORKERS=4`:20182passed/50skipped/0failed.
Source stayed clean and unchanged; command exit0. Full lint, generated guide,
format, types and private residue gate passed. See
`docs/evidence/neck-cut-final-fast.json` for log/driver digests. Later
accumulated CAC changes retain their own combined gates; task2.2 remains open.

Actual native save/reopen — 2026-11-03: current signed74caa591 regenerates
all15board_40parts plan files exactly equal to the earlier reviewed native input.
Altium24.5.2.23 opens an isolated source clone, saves a separate binary document,
closes it and reopens the saved copy. All573enumerated object kinds and region
hole counts10/0/0 match. Both complete typed region storages retain every outline,
hole and closing vertex exactly, including4646hole vertices per storage; both
reads have zero findings. The original and clone source hashes remain unchanged.
`docs/evidence/neck-cut-native-save.json` records version, hashes, SDK stages and
the distinction between three native region objects and two records per byte
storage. No DRC, repour, metadata-wide equality or other-version claim is made.
Task2.2 remains open for exact-head CI and any remaining explicit native gates.


- [ ] 2.3 Audit exact native10 CI41627546110 geometry callers on the current integration source, reproduce a focused input-edge/repair-budget refusal with public manifested corpus inputs, and preserve bounded external operand/counter/source receipts before proposing a repair. Do not raise budgets, skip callers, change assertions, fall back or weaken any certificate. Final integration and exact-head CI remain independent gates.


Task2.3 partial current-source audit: on5b0853b7, actual public corpus05 reproduces the input-edge refusal in0.77s; exact operand inventory is4329subject+5826clip=10155edges against the unchanged10000cap, with no zero/collinear or bbox-disjoint clip reduction. Actual ECC83 triangle04 reproduces enumeration refusal in6.09s:8061edges,423loops,51nearest conflicts and52implicated nodes across13loops. Observing the unchanged existing proposal confirms its52omissions fail `uncovered continuous interval endpoint` before the fallback16node cap refuses; it is not a valid candidate blocked only by count. Source-bound external operands/drivers and complete counters are pinned in ci-geometry-refusal-proof.json. No runtime/budget/threshold/assertion/certificate or CAD change. Task2.3 stays OPEN for remaining deadline/caller audit and a reviewed solution; no combined/full CI pass is claimed.


- [ ] 2.4 Prepare concrete exact scalability/selective-repair invariants and authored RED controls for coordinator review; prototype only externally on captured public operands with original global work/distance/deadline limits and complete final certificates. Do not change runtime or reinterpret/reset the10000input cap without explicit policy review. Preserve failed prototypes and keep caller/CI closure separate.


- [x] 2.5 Port the explicitly coordinator-approved derived100,000input-edge policy only; retain every other limit and all certificates. Prove sparse above10k/default cap/custom cap/dense explosion/refusal boundaries, focused geometry/pour neighbors and measured external counters. Do not claim05or final CI passes by this policy change alone.
- [ ] 2.6 Port the separately approved exact rational refinement proposal with necessary-only endpoint pruning and original GLOBAL final certificate; preserve all original exact nodes/currents, source integers, canonical half-even and one Budget. Prove the authored RED/positive/impossible and independent malformed/contact/parentage/shared/source/continuous/resource/permutation controls before actual public callers. No cache, baseline change, special fixture dispatch or fullfast.

Coordinator production review2026-11-03 explicitly approves A/B in separate focused iterations after the recorded REDs. A is an explicit private input-domain expansion; B is proposal generation only. Newpoint/trial/storage/distance/deadline caps remain shared and unchanged; actual05cleanup mathematical divergence still returns for review. No additional routine approval is required within this exact scope. Exact-head CI remains pending.


Task2.5 focused policy proof: sparse/default derived-cap controls reproduce2reds and the dense guard passes first. After the approved source-domain expansion,84geometry/pour controls pass9.70s plus the independent custom2edge boundary control passes0.19s; source pyright0 and lint/format pass. The caller overflow test moves explicitly to25,001four-edge rectangles so it still checks refusal ABOVE the reviewed100,000ceiling; no assertion/certificate is removed. The external10155edge pilot uses one Budget and63.3MB observed peak but still refuses repair; it is NOT a05pass. Negative100001input and250kpair overflow guards refuse before intersection arithmetic. Receipt input-policy-proof.json; B2.6 and exact-head CI remain open.


Task2.6 implementation checkpoint (remaining requested callers still open): the positive original notch reproduces a real nonsimple RED, then15authored controls pass, including malformed subdivisions/policy/source/shared projection/parentage, a planted uncertified proposal, resource/deadline guards and14ring/source permutations.100geometry/pour controls pass4.29s,67architecture controls3.58s, selected source pyright0 and all159complete example/generated-byte guards20.82s with ZERO baseline changes. Actual native10.0.6 ECC83 triangle04 passes8.97s with its original assertions. The original full certificate, distance prover and omission producer source files stay BYTE-UNCHANGED. Endpoint/midpoint predicates only build/prune proposals; final global continuous/source/contact/parentage/debris certification is unchanged. No cache or interval-unit reinterpretation is used.

Actual03/05focused pours still fail:03at unchanged index-comparison budget,05at the existing fallback after non-omitted cleanup. Neither is called fixed, and no count/budget/expectation is adjusted. Exact-refinement-proof.json retains separate observations and the mathematical correction of the initial false notch-impossibility hypothesis. Task2.6/2.3and exact-head CI remain OPEN until the remaining requested cases and scoped follow-up review are resolved.

- [ ] 2.7 Review the newly exposed03index-comparison exhaustion and05non-omitted cleanup separately using exact public captures and authored controls. Improve work/proposal generation while preserving the remaining counters and full certificate; no cap increase or cleanup waiver without explicit technical review.


- [x] 2.8 Preserve the original candidate fallback when a refinement attempt raises GeometryError before yielding or during proposal preparation. Propagate ResourceLimit unchanged. Establish independent authored first-refusal/next-certified-success and resource-propagation RED controls before the focused fix; the original global certificate is unchanged.


Task2.8 proof: the independent before-yield refusal control reproduces1RED while ResourceLimit propagation already passes. After guarding the entire refinement attempt, the next original candidate is still judged by the real unchanged global certificate and returns successfully. The separate ResourceLimit control still aborts rather than swallowing exhaustion. Complete focused geometry/pour/refinement controls:102passed; selected source pyright0 and static checks pass. No certificate, bound, fallback qualification or resource policy changes. Receipt refinement-fallback-proof.json; final CI remains open.


- [x] 2.9 Review and implement an exact closed-box tree self join only after independent completeness/uniqueness and resource REDs: every unordered source-ID pair has one leaf-domain owner, every node/leaf predicate is charged to the same1Mcounter, all source/storage/pair/deadline caps remain. Compare full actual03pair tuples/permutations with the explicitly NON-GATE separate finite old reference; actual caller and remaining later refusals stay separate.


Task2.9 proof: the original3000edge false1Dfamily test reproduces oneRED. After the reviewed private selfjoin,111geometry/index/pour controls pass4.57s including Hypothesis small-set completeness, exact closed degenerate/endpoint cases, callback exhaustion, tree/storage/stack/custom work guards and all previous certificates.226example/generated-byte/architecture guards pass23.43s, with ZERO baseline updates; selected source pyright0. Actual product03table has104021unique pairs and942026node/leaf visits; its COMPLETE sorted tuple equals the explicitly NON-GATE old reference under finite2050481comparisons. Captured public reversals/shuffle/rotation preserve every rebased pair under1M. Actual03pour advances through indexing, then refuses at its unchanged global winding-visit cap19.75s; it is NOT a caller pass. Receipt tree-selfjoin-proof.json; all other gates remain open.

- [x] 2.10 Review and prove an exact closed-Yinterval seed-winding filter for disconnected components, with all endpoint ties/formal infinitesimal semantics intact, IDs/multiplicity preserved, query+segment work charged to the same global visit Budget and no higher limit. Any separate old full reference beyond10M must be explicitly NON-GATE and finite. Do not port before review or claim03success before its complete actual caller passes.


Task2.10 scoped proof: original fullscan RED exceeds the same5000cap. The honestly charged endpoint-median prototype also needs5059and is NOT a pass; the separately reviewed averaged Fraction median completes in4947and cap4946refuses.273focused geometry/pour controls pass6.19s, including144independent formal infinitesimal cases, exact duplicate/zero-spanner/endpoint selection, shared work/deadline/storage/bit refusals and unchanged affordable fullscan routing. Selected source pyright0;203example/index controls pass5.66s with zero baseline changes. The product capture compares every379candidate-ID set with brute and every winding vector with the previous COMPLETE NON-GATE reference hash. Construction466859+query/segments yields514167GLOBAL visits; no cap/reset. Actual03pour advances winding and FAILS the unchanged4096bit aggregate area guard in6.31s. This task closes only the reviewed index proof; tasks2.3/2.6/2.7and exact-head CI remain OPEN. Receipt closed-y-winding-proof.json.

- [x] 2.11 Preserve the original global scalar area certificate first; only a specifically too-wide global sum may use complete signed component identities and an exact outward dyadic enclosure proving global nonnegativity. Keep4096bit local/product/sum, original ownership/area/certificates, shared storage/work/deadline and nested negative contributions. Establish independent RED/cross-component mismatch/negative/ambiguous/bit/resource controls before port, then actual03caller without claiming later refusals passed.


Task2.11 scoped proof: independent pairwise-coprime authored terms reproduce the original global4096bit RED while each local value fits. The existing scalar proof remains first; only its too-wide GLOBAL sum returnsNone.286geometry/pour tests pass7.23s;50area/resource/example tests pass5.83s including negative nested contributions, local mismatch despite equal global sums, ambiguous-positive refusal, negative refusal, scalar exactzero, closed ownership and separate local/product/sum/work/storage/deadline refusals. Selected source pyright0 and static checks pass. External379component identities are EXACT with369negative contributions retained and2155peak local bits; outward floor/ceil enclosure proves the GLOBAL sign. The actual03caller advances area and FAILS20.91s at the unchanged256refinement proposal-node limit. Neither03nor05nor final CI is called passed. Receipt component-area-proof.json;2.3/2.6/2.7remain OPEN.

- [x] 2.12 Add exact target-vertex projection parameters as proposed capsule breaks before the original dyadic fallback. Keep the same Cover/original complete verifier, convex same-owner endpoint proof and all shared interval/distance/bit/storage/deadline limits. Establish authored cap5oldRED/newPASS and malformed/gap/resource/old-fallback controls before focused port; no whole03claim until the consolidated production path passes.


Task2.12 proof: independent exact bend reproduces1RED at cap5. The projected-vertex producer uses5intervals under that SAME cap; original dyadic producer needs7and remains available when a proposal refuses.292geometry/pour tests pass5.79s, including planted false proposed witnesses rejected by the ORIGINAL complete verifier, ResourceLimit propagation and the zero-depth refusal retained before ANY split. Selected pyright0/static checks pass. No capacity, acceptance threshold, full verifier or caller assertion changes. Consolidated EXTERNAL03pilot passes but C/B/Aports are not yet present, so no production03/CIpass is claimed. Receipt projected-capsule-proof.json.

- [x] 2.13 Add the explicitly reviewed IdentityRun exact-subchain encoder beside legacy capsule Cover intervals. Verify every original source/target directed edge endpoint/ID/multiplicity cyclically, with complete gap/overlap-free bidirectional coverage, same global work/storage/bit/deadline and16384nonidentity intervals. Prove authored oldcap16RED/newsamecap, legacyCover and planted1nm/omission/duplicate/reverse-owner/invalid/resource negatives before port. No captured/whole03production claim until B/Aalso pass.


Task2.13 proof: authored102edge wavy chain reproduces oldcap16RED; the NEW explicit identity encoder passes under that same capsule cap.311geometry/pour controls pass5.87s before one additional duplicate-occurrence control; final20identity controls pass0.59s,35example guards pass4.29s with ZERO baseline changes, and actual native10ECC83 triangle04passes8.19s with original assertions. Legacy4Interval Cover is explicitly verified before planted gaps/falseowners; identity edit1nm/omission/duplicates/reversal/unknown/type/cyclic/multiplicity/resource/deadline negatives refuse. Ambiguous duplicate edges use capsules and retain every original ID. New matching/storage/verification/distance work is charged to the shared Budget; no cached proof or cap change. Selected pyright0 and static checks pass. This closes only encoder C;03production still awaits B/Aand complete original caller. Receipt identity-run-proof.json.

- [x] 2.14 Keep exact whole-piece scalar area first; for an actually RETAINED noncollapsed piece whose projected net meets the debris floor, prove only a too-wide GLOBAL exact sum's nonnegative predicate with exact outward bounds. Every local term/product/sum remains4096; ambiguous/negative refuses. Any whole-piece Loss still requires its original exact Fraction and refuses if unavailable. Prove authored scalarRED/retainedsign/negative/ambiguous/exactLoss/resource controls before focused port.


Task2.14 proof: independent coprime terms reproduce original4096bit scalar refusal.321geometry/pour controls pass10.18s; final24area neighbor controls pass0.16s after exposing the shared helper within the PRIVATE exact module (selected pyright0). An actually retained eligible piece may prove only its sign; every whole Loss still requires its original exact Fraction. Negative/ambiguous sign, local/product/sum bits, work/storage/deadline refuse; scalarzero and13/21exact loss-value controls remain equal. No model/report/area placeholder, limit or source/certificate removal. Aport and actual03production caller remain pending, so no production03/CIpass is claimed. Receipt retained-piece-sign-proof.json.

- [x] 2.15 Select the pressure-estimated bounded exact half-even cell producer only when26positions×necessary targets of the FIRST affected owner exceeds remaining proposal slots; otherwise preserve the original producer. Consume shared initial probes once, one canonical TrialState per solve, no counter/reset or ResourceLimit catch. Prove authored samecap2RED/fullcertificate, pressure boundary/legacy notch/ECC83/default bytes, half-even/ties/permutations/source/malformed/resources and actual03+04original callers before closure.05remains separate.


Task2.15 focused production proof: independent analytic notch gives oldcap2RED→new complete GLOBAL certificate under SAME cap2.90cell/refinement controls pass0.45s, including64ties/parity/rotation/reversal cases and exact pressure boundary26→cell/27→old.411geometry/pour/refinement controls pass6.09s plus the separate new-cell ResourceLimit propagation control passes6.54s.194complete build-byte/example guards pass25.67s with ZERO baseline changes. ACTUAL unpatched original public Altium03pour census passes24.13s; ACTUAL KiCad10.0.6 ECC83 triangle04passes8.88s with every original assertion. Selected pyright0/static checks pass. One typed TrialState keeps all canonical trial points/omissions/loops; initial necessary probes are consumed once in original owner order, and selector is only a LOCAL FIRST-affected-owner estimate, never a global bound. No cap/precision/certificate/caller assertion changes.05cleanup and exact-head CI remain OPEN; neither is claimed passed. Receipt direct-cell-proof.json.

- [ ] 2.16 Reconcile and repair the remaining original native regression families without changing budgets, original caller assertions, source geometry or accepted-difference baselines. Begin with source-bound captures and independent authored REDs; keep whole-policy/source/contact/continuous/loss certificates mandatory. Reprove all selected callers, explicitly including heavy cases and the interrupted probe, then exact integration CI.

Task2.16 starting evidence: frozen97a52ce4 replay deliberately interrupted with exit2 after19failed/6passed/2heavy-skipped in369.51s; one selected probe unfinished. The19 terminal failures partition into4proposal-node,3index-comparison,4input-edge,4arithmetic-bit,1enumeration-node and3nonsimple-projection refusals. Public03, triangle03/04/09, CM5 import and the exact native pour proof pass in this subset. This does NOT complete2.16 or the broader gate. Receipt native-regression-frontier.json binds all selectors and log/receipt hashes; the original six explicitly excluded selectors still need their separate proof.

- [x] 2.17 Reduce conservative self-join traversal work by splitting the larger closed bounding box when both distinct nodes have children, with deterministic area/perimeter ties. Preserve every overlapping leaf pair exactly once, all diagonal/leaf predicate charges, stack reservation, source edges and existing limits. Start with independent authored disjoint stripe families under the same custom1000-comparison cap; prove exhaustive closed/degenerate/contact pair equality, resource boundaries and the original native07 index stage, retaining any later native refusal explicitly. Other native families and final integration CI remain independent.


Task2.17 proof: independent400-stripe RED fails at the unchanged1000 comparison
cap; the new traversal passes. Closed grid/degenerate/contact brute-force,
random/Hypothesis pair equality and every existing resource-boundary control
pass; combined geometry/neck-cut628passed14.16s. Original native07 capture has
65620source edges. Production's complete139739 closed candidate pairs exactly
equal the independent per-item search reference; external traversal count796979
fits the original1000000 cap (old path exceeds it). Peak42 stack entries and all
storage/candidate/deadline limits remain unchanged. Actual unpatched native07
now passes indexing and fails later with the existing implicated proposal-node
refusal,15.80s. This is scoped index repair, NOT a native caller/CI pass or task2.16
completion. See size-directed-index-proof.json; no byte/source/caller baseline
or original certificate was changed.

- [x] 2.18 Certify an oversized selected-component area identity by exact oriented line-current equality, only after the existing global and component scalar attempts exceed4096bits. Keep bounded exact ring/face areas, signed ownership and all original certificates. Prove equality of every component's complete directed boundary, including collinear subdivisions; prove the global sign with outward32dyadic bounds without inventing an area value. Charge shared work/coordinate/storage/bit/deadline limits. Begin with an independent valid connected rational mesh RED, then location/selection/ownership/resource negatives and source-bound public01 reproof. A later refusal never becomes a native pass.


Task2.18 proof: valid one-component4141-face authored mesh RED fails with the
original arithmetic bound, then passes with exact directed-current equality.
Same-area relocation onto other real mesh points, missing selected face,
reversed current and global work/endpoint-storage exhaustion refuse. Cyclic
starts/order and rational diagonal/axis collinear subdivisions pass. Combined
geometry/neck-cut635passed20.71s; final expanded focused current controls8passed
0.92s. Complete default byte/example guards111passed24.31s, zero baseline edits.
Ruff/format and selected pyright0 diagnostics pass. The scoped production area
phase also passes the unchanged public capture, with original limits. Actual
unmodified public01 caller now reaches a later implicated enumeration-node
refusal,16.73s; this is NOT a caller pass or task2.16/CI completion. Individual
4096bit areas, source/ownership/policy/contact/continuous certificates and exact
whole-loss areas remain mandatory. See component-current-area-proof.json.


- [x] 2.19 Classify a frame cycle with an oversized bounded-term area sum by an exact sign proof, without fabricating a scalar area. Keep scalar-first behavior, the strict area2 API and every Loss requirement; prove component face cancellation with complete directed currents when a bounded scalar is unavailable. Retain conservation/Euler/unique exterior and all coordinate/work/storage/deadline limits. Begin with an independent connected rational fan RED, prove translated/rotated/order variants and unresolved/zero/resource refusals, then replay the source-bound native13 frame and original caller. Later refusals and final integration CI remain separate.


Task2.19 proof: independent connected100-triangle fan RED becomes101 valid
faces with one exterior, including rotation/translation/reversed input order.
Strict area2 still refuses its oversized exterior scalar; only orientation is
certified. Unresolved zero walk, coordinate/work/point/deadline limits refuse.
Combined geometry/neck controls664passed12.46s; complete byte/example guards
111passed14.25s, no baseline edits. Ruff/format and selected pyright0 pass.
Actual unmodified native13 now passes frame construction and fails later at
implicated proposal-node budget,7.97s. This is NOT a caller/CI pass or2.16
completion. Scalar/loss areas, conservation/Euler/unique exterior and all caps
remain mandatory. See frame-area-sign-proof.json.
