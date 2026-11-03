# Bounded v0.7 closure queue — 2026-11-03

Current batch preparation: [closure-batches-20261103.md](closure-batches-20261103.md)
records the16first candidates,20additional candidates and c0250ordering
prerequisite. All37normal archives and97resulting living specifications were
rehearsed externally; this branch still has no actual archives from that batch.
The published985f59a1workflow has14required jobs, including the dependent
drawn-floor bridge. Later runtime b1e9349a failed fast14; its repairs culminate
in9ff58f57, whose independent fast15 passed22421cases with52skips and exit0
on a clean unchanged source ([receipt](fast15-receipt.json)). This closes its
local-fast result only; it supplies no CI985 verdict, Royal L7 pass or actual
archive. The failed fast14 receipt remains unchanged.

## Active order after maintainer reset —2026-11-03

The maintainer requested closure and organization before further geometry
experiments. This section is the current working order; later dated sections
retain historical evidence and do not enqueue new work ahead of it.

Current inventory at70db27e0:114open changes across the repository,9with all
checkboxes checked. These are NOT114CAC changes and NOT9archival approvals.
The original CAC c0246–c0279 contains34changes,679checked tasks and63unchecked;
3changes have all tasks checked. c0267/JLC is explicitly deferred, still open.
No completion percentage, native acceptance or archive is inferred from counts.

| Priority | Bounded work | Exit condition |
| --- | --- | --- |
| 1 | First closure batch: c0248 → c0259 → c0261 → c0178 → c0345 → c0358 → c0359 → c0363 | Reconcile each literal task with its receipt, required final-commit CI, normal delta application/validation, one DCO archive commit per completed spec. No forced incomplete archive. |
| 2 | Historical all-checked review: c0081, c0105, c0170, c0179, c0196 | Verify actual closing proofs and CI/source coverage; retain explicit later gates. Checkboxes alone are insufficient. These five were absent from the eight-item first batch. |
| 3 | Remaining CAC and older v0.7 acceptance in the tables below | Close existing proof tasks in order; use current receipts before scheduling reruns. Group missing CI, native tests, external release and maintainer reviews separately. |
| 4 | c0332/c0355 implementation failures | Resume one focused repair only after the closure inventory is reconciled; no further speculative geometry pilot takes priority over closure work. |

Local fast13 passed on2c054057:22366passed/52skipped. Through70db27e0 all later
changes are documentation/evidence only. It is not a final GitHub CI verdict.
No local full suite is scheduled. No push is authorized by this reset.

Archival rehearsal: the eight deltas were applied sequentially with normal
`openspec archive` in an EXTERNAL COPY, not this branch. No `--skip-specs` or
`--no-validate` was used. c0248/c0259/c0261/c0178 reported complete checklists;
c0345/c0358/c0359/c0363 warned about2/2/1/1unchecked tasks respectively.
The external rehearsal used `--yes` to inspect delta application; its force
warning is preserved and is NOT authority to archive those incomplete specs.
All12resulting living specs also pass strict validation; every rehearsed
change input is byte-identical to this branch. This branch still has zero new
actual archives. The remaining current-CI gate
also applies to the first four despite complete checklists. The rehearsal
receipt binds the source, outputs and validation, without claiming task/CI
completion: `closure-rehearsal.json`.

## Original audit and detailed gate evidence

This is an audit, not an archive or an exact-head CI success receipt. The audited
local tree is a6f6406f plus proof-placement ea626a56 and external-preparation
6b1531cd; none changes production code. Root owns the moving integration branch.
Current required jobs must be checked on its final published SHA. A checked
historical task does not erase a later explicit integration gate.

The delivery includes CAC and older acceptance required by v0.7. Product-1.0
freeze c0216–c0220, other agents' routing/enclosure work and explicitly deferred
c0267/JLC are not new requirements of this queue. The implemented model-format
transition still participates in ordinary regression checks. c0279 is a real
CAC library/catalog gate, not a product-1.0 release gate.

## First batch after required current CI

| Change | Evidence already available | Literal remaining gate |
| --- | --- | --- |
| c0248 device catalog | 20 checked tasks; historical producer 5657bde78ee5b0e8ecd12dded4183785d5b9ea63, CI40907010241, 13/13 jobs successful; current focused contracts196passed | Combined integration fast and required exact-head CI; later changes are not covered by that historical run. |
| c0259 library data format | 24 checked tasks; historical producer a61bd3901808c628fc1c318aa4e7448bd11ae67a, CI40987149835, 13/13 successful; focused55passed | Tasks' integration8d74a798/c0311 note explicitly leaves full gate and CI pending. |
| c0261 symbol generator | 18 checked tasks; historical producer c7e000393e573bfc395d42c58c29aeb7b6f0075c, CI40981144863, 13/13 successful; focused152passed/1empty-parameter skip | Explicit combined integration fast/CI note. The skip is not a native pass; inferred Altium coverage is not promoted by KiCad results. |
| c0178 viewer colours | Real maintainer approval1985faf8 of the source-bound native/viewer packet; external native theme and inputs retained | Required integration CI and normal archive validation. Human review is completed for this packet only. |
| c0345 custom field poses | Mirror authored matrix, exact values/poses, native9/10 and default75 maps; native tests now in oracle jobs | Tasks2.1/M3 include required current CI, not merely focused passes. |
| c0358 native custom values | LF/mirror positives and strict malformed/duplicate/reserved negatives; same native-placement correction | Tasks3.2/M3 require complete exact-final-commit CI. |
| c0359 native rule context | Bounded DRU/context preservation proofs, source-bound public replay; unjudged notices retained | Task3.2 requires full exact-final-integration CI. Library publication is independent. |
| c0363 native TAB values | Strict native-only TAB scope, native9/10 and unchanged75 maps; pure unit controls cannot invoke native CLI | Task3.2 requires complete exact-final-commit CI. |

No member of this batch is archived by this audit. Once eligible, inspect and
apply each OpenSpec delta normally, validate, and commit each archive with DCO.
For the original three, use c0248 then c0259 then c0261. Existing MODIFIED targets
are present in living specs. Do not use `--skip-specs`: c0251's later Connections
and pin designators delta must preserve BOTH c0248's device validation at call
and c0251's port-net behavior rather than overwrite either requirement.

## Original CAC tasks c0246–c0279

“Present” below means the named implementation/example/test exists in the audited
tree. It does not mean its native proof or the final CI has passed. Unchecked
native/evidence tasks require reconciliation with actual receipts before ticking.

| Changes | Remaining task IDs and action | Classification |
| --- | --- | --- |
| c0246 | 4.2/4.4 source-bound evidence and exact CI | Proof/CI |
| c0247 | 3.1 example already contains unused_no_connect and series; prove unchanged bytes; 4.2/4.4 evidence/CI | Proof reconciliation/CI, not demonstrated missing helper code |
| c0249 | 5.5 | Fast/exact CI |
| c0250 | 7.2 native edit-merge oracle file present; 8.1/8.2/8.4 evidence, CI, validation/archive | Native receipt reconciliation/CI |
| c0251–c0257 | 0251.6.2,0252.6.2,0253.6.6,0254.7.4,0255.7.4,0256.6.1,0257.6.1 | Fast/exact CI |
| c0258 | 5.2 native topology-lowering test present; 7.1 | Native evidence/CI |
| c0260 | 5.4 generated-model native test present; 7.5 | Native evidence/CI |
| c0262 | 5.2 shipped library-check/review CI artifact; 5.6 | Exact CI/artifact |
| c0263 | 6.4 | Fast/exact CI |
| c0264 | 4.4 library_import example present, reconcile native-build proof; 5.5 | Proof/CI |
| c0265 | 4.5 | Fast/exact CI |
| c0266 | 4.1 external source/check/review jobs; 4.2 reviewed seeded release and zero-error release audit via c0279; 5.6 core CI | External library/release plus CI |
| c0267 | Explicitly deferred by maintainer | Excluded, still pending and unarchived |
| c0268 | 5.2 | Exact CI |
| c0269 | 4.1 native block graph both majors; 6.2 | Native evidence/CI |
| c0270 | 4.2 usage-board test present and shipped blocks-test CI; 6.1 | Native/CI artifact |
| c0271 | 5.1 layouts example and native test present; 6.1/6.2 CI/evidence | Proof reconciliation/CI |
| c0272 | 2.2 five starter usage-board proofs on9/10; 4.1 | Native evidence/CI |
| c0273 | 4.3 external block jobs; 5.3 core CI | External library plus CI |
| c0274 | 7.5 | Fast/exact CI |
| c0275 | 4.3 source-bound corpus measurement, counts and evidence; 5.5 | Census artifact/CI; preserve failures |
| c0276 | 7.1 native resolver; 7.2 corpus; 9.2 CI | Aggregate6.2 now complete: maintainer accepted the current24 report and all14 visual inspections with the recorded drawing limits; EXAMPLE38pins/33groups, FULL40/32 and REPEAT8/5 in both forms, Info-only compiles, complete exports/save-reopen. The report digest and approval are bound in native-visual-proof.json. Prior6.5/6.6 and retrospective FULL chronology remain separately recorded. Formal-kit label stays INFERRED; writers remain experimental and census/current CI gates remain open. |
| c0277 | 5.5 | Fast/exact CI |
| c0278 | 6.1 native upgrade/refill; 6.2 roundtrip test and accepted ledger present; 8.2 | Native/census evidence and CI; existing GUI sensor proof does not settle every case |
| c0279 | 3.2 first library PR/workflow CI; 3.3 first library release and core table; 4.4 replay/proof/bench/gallery workflow results; 4.5 first-board integration proof; 5.6 core CI | Real library/publication and CI gates. External OpenAir4.5a preparation is complete; preparation does not close publication. |

c0248/c0259/c0261 are covered by the first table. This audit has not unchecked,
checked or silently waived any task in the rows above.

## Remaining integration and repair queue

| Group | Changes | What actually remains |
| --- | --- | --- |
| Integration-only or focused-proof reconciliation | c0281,c0282,c0300–c0305,c0311,c0315–c0318,c0320–c0322,c0324,c0329–c0331,c0335,c0336,c0339,c0341–c0344,c0346,c0349,c0350,c0354,c0356 | Literal focused/generator/static receipts where still unchecked, then combined fast and exact CI. Viewer jobs and native9/10 must remain included where required. |
| Explicit receipt/capture dependencies | c0323,c0326,c0327,c0334,c0337,c0340,c0347,c0348,c0351–c0353,c0357 | Bind actual failure capture, contextual/public replays, final model/default75 maps, census bridge artifacts and settings/presentation proofs to their actual sources; then required CI. Some receipts already exist: reconcile before declaring code absent or ticking. |
| Geometry implementation/proof blocker | c0332 | Approved exact scalability/selective repair ports and actual public03/05 callers are root/geometry-owner work. Historical32 native CI cascades remain failed until actual reproof. No budget increase, waiver or refreshed geometry baseline is authorized by this ledger. |
| Royal physical identity blocker | c0355 | Literal authored controls, complete correspondence, approved preparation/runtime and fresh strict Royal proof remain. Two L7 failures are real; external diagnostics are not production acceptance. |
| Diagnostic not an extra product feature | c0328 | Preserve bounded/full prototype failures and review records. Determine the literal relationship to approved c0332 implementation; do not relabel an unfinished experiment as passing or grow the release scope. |
| External library gates | c0333,c0338,c0279 | Authoritative integration, core/library exact-source CI, audit/reviews/release remain separate. Human approval of four seeded items does not publish them. |
| Global gate | c0319 | Local fast2.2 passed on clean source2c054057 (22366passed/52skipped); revalidate later runtime changes. Exact published required CI2.3 remains open; cleanup never replaces it. |

The routing c0280 and separate enclosure branches are outside this closure
assignment; their owners retain their own exact-integration gates. No unrelated
branch or unique work may be deleted as part of this inventory.

## Older v0.7 acceptance that is not merely a CI checkbox

| Changes | Material remaining gate |
| --- | --- |
| c0092 | Actual acceptance_v03 schematic compile/export and three-document save/reopen complete on24.5.2.23: all8pins/3groups/names exact, Info-only, raw exports byte-identical. Native PCB census/new-copy save-close-reopen also complete (S-1304), with complete raw census byte-identical; S-1305 records one native DRC with all14findings (9unrouted/5antennae), not DRC-clean; full rule-category inventory/detailed physical kit and per-kind graduation/current CI remain. |
| c0160,c0166,c0168 | Literal PartT/full native inventory/S3–S5 acceptance. New S5 receipt615c2814 must be checked against its complete criteria, not generalized to other slots. |
| c0172 | Actual Draftsman F0/FP/F1–F8 gate decisions and conditionally required writer work. |
| c0173 | Q1–Q12 native panels and gated embedded-array implementation; not only stale CI. |
| c0175,c0241 | Authored house-library requirement selected by user; c0241 integrity/edit/commit/schematic runtime and J1–J22 remain real dependencies, not an invented overnight completion. |
| c0177,c0180,c0181,c0186 | Four source-bound visual maintainer reviews remain; choosing authored examples was not approval. Draftsman preparation needs real F0.5. |
| c0215 | Separate Altium native K6 acceptance plus final CI. The KiCad pour fragmentation proof was repaired test-only in a6f6406f, with17 actual native10/control passes; no M3/runtime/baseline relaxation. |

c0195's personal MCP experiment is explicitly optional, not a new mandatory
release requirement. Earlier all-checked historical specs still need their own
literal archival review; checkbox totals alone are insufficient.

## Source-bound gate receipts and preserved failures

- Complete fast11 passed ONLY on
  `1a12e70f846f1a7c8f6bb2c6c03df253b8b2b075`:22072passed/52skipped,
  clean unchanged HEAD, log SHA256
  `62126a61553d6bb036318ec8198deb4881ea29a57a165739ecdd72969a116cbb`.
  Later approval/winding/area/pour/placement deltas have separate focused proofs;
  this receipt does not claim fast or GitHub CI success for their union.
- Native property placement proof ea626a56: native9.0.9 collects8 and executes
  4passed/4explicit unsupported-writer10 skips; native10.0.6 executes8passed.
  Pure unit controls100passed with native subprocess invocation forbidden.
- Eleven failed/cancelled runs were removed only after logs and all71 nonexpired
  artifacts (197572934bytes) were SHA/ZIP-CRC verified. IDs:
  41637238612,41635272102,41633688434,41633264793,41631213107,41629258032,
  41627685622,41627546110,41626923688,41621900799,41611925152.
  Archive-receipt SHA256
  `4661624b43422bc474dc311d31adddba322b4f43bd04921592eeb61eb689f21d`;
  artifact receipt
  `0f3c2625b7a0e6c9e07e452a7a12bec32c5644ed195f1633b9ab56bb8bec8df7`;
  deletion receipt
  `d9a1bf8560dc10a364046a394acc97c9827656f75bf5f2b10e96caf72a26523c`.
  Removing a failed run is housekeeping, never a green source verdict.
- OpenAir PREP4.5a is completed separately in6b1531cd: the original1355-file
  external review packet is unchanged,267candidate files verified,6author inputs,
  all9levels equal/0accepts/27notices,262-file readonly replay and233 external
  nominal3D references. No model asset was included or judged. The old647-pin
  receipt proves a mismatch (155native versus156PCB groups), not equality.
  Authoritative library, release and global4.5 gates remain open.

There is no spec-filtered substitute for the required CI: the normal CI workflow
has no per-spec dispatch, and nightly diagnostics explicitly are not a merge
gate. Publish the repaired accumulated CAC candidate, inspect every required job
on that exact SHA, then archive only specs whose other literal gates are also
complete. Keep c0319 open until its own integration proof is observed.

## Current diagnostic replay — root follow-up

The later isolated source97a52ce4 replay was deliberately interrupted after actual failures;
its receipt reports19failed/6passed/2heavy-skipped in369.51s, exit2. One selected probe
remained unfinished. This is neither a complete replay nor a green current integration.
Public03, ECC83 and the repaired native pour/CM5 paths passed in the measured subset;
remaining resource and realization refusals require their own focused repairs. Preserve
the log SHA256 e7d85b66b247727ef93ea21be4b4657c5d976495bfd3180a6b4053e182d947fe.
The three delegated agents later stopped on a platform usage limit; this inventory remains
a local checkpoint, not an assertion that background work or CI is running.


## Scoped geometry follow-ups — 2026-11-03

Size-directed self join5bbe19c7 retains all139739 closed candidate pairs for
native07 within796979 original comparison charges.628 geometry controls pass;
the native caller still fails later at implicated proposal-node repair.
The subsequent connected-component current proof has635 combined controls,
8 final focused current controls and111 unchanged default byte/example guards.
The public01 area phase now passes, while its full original caller still fails
at implicated enumeration-node repair. These are two source-bound stage repairs,
not green native callers or a replacement for c0332.2.16/current CI. Fast12 is
running only on source5bbe19c7 and does not cover the later runtime delta.


Fast12 completed on5bbe19c7:1failed/22350passed/52skipped, clean unchanged head,
exit2. The only failure names missing current continuation c0215.6.4a in the
v0.6 ledger. Task2.11 adds its exact ID and dated tracking without changing any
checker; all three full release-record modules112passed12.81s. The original
failed receipt remains fast12-receipt.json. No fast/CI success or archive follows
from this focused correction; later area runtime and final batch still need
combined validation.


Fast13 completes local task2.2 on clean unchanged2c054057:
22366passed/52skipped, exit0; log SHA256
3e74d627e77139979c42ba6ca13e53344a23b8416aff252e747e34d56286abfe.
The exact receipt is fast13-receipt.json. Later c0092 native observations through
c5e34749 are docs/evidence only and have their separate focused proofs. No
current GitHub CI, geometry-caller, native full-kit, archive or publication
success is inferred; any later runtime candidate needs fresh combined proof.


## Additional requested CI cleanup —2026-11-03

Two later runs on codex/ci-layers-and-coverage were terminal:41681471834
failed on f97ebebeb799b3a02504b8f79a23aadacdf3cae8;41681205419 was cancelled
on3ce918fd640571aa7c18a113e3b4e4f5f11e38f5. Both complete log ZIPs and all17
nonexpired artifacts were preserved before deletion, with every archived file
SHA256 and ZIP CRC reverified. Both DELETEs returned success and subsequent
individual GETs returned404. A complete297-run post-query has zero failed,
cancelled or live runs. Receipt:docs/evidence/cac-ci-cleanup-additional-20261103.json.
Together with the prior11,13requested run records have been removed. No push,
required-current-CI success, native acceptance or archive is inferred.


## Parallel closure audit —2026-11-03

The three new delegated agents started successfully; the earlier quota-stopped
workers are not treated as active. Their bounded review found47unchecked tasks
in the assigned original-CAC subset:44require exact-head CI or its explicit
dependency,3are the deferred c0267. Zero new unchecked task was waived.
Current complete example-byte proof76passed10.79s and evidence/provenance
proof46passed64.47s support the corrected stale proof paths in c0246/c0247;
the tested guard/table and every pending checkbox remain unchanged.

The five historical all-checked specs have current focused proof298passed32.64s.
The official MCP2.3.0 client proof additionally passes3tests4.73s in an ephemeral
environment without dependency/lock edits. The initial missing-SDK skip/exit5
is retained separately, not reported passed. Historical CI readbacks confirm
c0081 run40427514426(12successful jobs),c0105 run37772583226(11) and c0170
run38930004103(11). c0196's old run40261423201 is unavailable(404), not green.
None supplies final-current-integration CI.

Additional structural order: c0195 must apply before c0196 because the latter
MODIFIED delta targets mcp-server, which c0195 creates. Normal external rehearsal
of c0196 alone prints Aborted although the CLI exits0; no movement occurred.
Applying c0195 then c0196 succeeds with actual movements. c0195's optional
personal-session task is not a new functional prerequisite; its own CI/closing
gates still apply. Never classify archive success from exit0 alone. The first
eight rehearsal was checked independently by actual postconditions:8moves,
0active directories,49identical inputs,0Aborted logs and12valid living specs.


## Maintainer-authorized CAC CI batch —2026-11-03

The maintainer explicitly requested publishing an available batch of about ten
CI-only specs. The first eight plus c0249/c0251 meet that classification; their
required jobs are not claimed green yet. Published ONLY core codex/cac-next
from b5f6c84a to985f59a1d01a612b2eac0219243199896c24075a, fast-forward.
Selected-ancestry private audit passes7079blob/path pairs/0hits, private gateON;
all73new nonmerge commits carry the maintainer's DCO. Production code remains
byte-identical to complete-fast13 source2c054057; the intervening22paths are
docs/OpenSpec/evidence/CHANGELOG only.

Workflow ci run41708879698 was observed in_progress on EXACT985f59a1:
https://github.com/lgili/Fenolite/actions/runs/41708879698
No workflow filtering, job cancellation, green verdict, archival or dev/tag/
library publication is inferred. Keep2.3 and actual archive gates open until
the required jobs finish successfully on that SHA. Later local documentation
and library8b38b30 are outside this published core candidate.


2026-11-03 scope correction: CI41708879698 is terminal FAILURE (12jobs success; native10 has
27geometry failures and drawn-floor propagates that failure after passing its own qualification).
The maintainer clarified geometry was already outside this closure batch. The old37plan's global
14-job requirement is not a blanket block on specs whose own required jobs/proofs passed.
Assess those proofs and explicit dependencies individually; do not close c0332 or infer missing
native comparisons. Local working-branch scope restoration is recorded by task2.13 and
ci-41708879698-terminal.json. No new push or CI run accompanies the correction.
