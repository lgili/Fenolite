# External routing candidates (c0368)

Recorded 2026-11-03. Implementation is in the working tree on codex/router-next-specs,
after c0367 commit 640b114724781221a176782ce8c1d7b88f7fa61d. No push, CI run or native
external-router compatibility is claimed. Exact-head CI is required before closing.

## Local evidence and boundaries

H-G-EXTERNAL-SCOPE and H-G-EXTERNAL-BUDGET are INFERRED from authored fixtures,
including real Python subprocesses standing in for tools. Contract: 8 tests; delta and scoped
dispatch: 24; budget/strict adapter boundaries: 18; CLI: 10. The combined final focused routing,
CLI, guide and import-graph proof passed 179 tests (exit 0); the subsequently strengthened
descendant-start assertion passed all 18 budget tests (exit 0). Guide: 56 passed; capabilities: 11.
The default budget/plugin regressions passed 15 and 120 tests respectively. An earlier mixed
CLI regression had 65 passes and three failures against the old capabilities field set; the
updated fresh capabilities test passed. None of those failures is counted as a passing gate.

Full-board comparison resolves semantic net/component references and ignores external identity,
while retaining opaque state, stackup/rules, placement and copper multiplicity/locks. Only internal
modeled-copper slot declarations may appear with the first appended item. SES is a copper-only
projection: its placement, unknown nodes and all returned net names are checked before filtering.
No external board replaces an input. All additions pass physical layer/full-via-barrel tests and
the required component-connectivity/copper/role judges. Unsupported subjects and incomplete
output are refused whole. These checks are conservative and do not prove routing completeness.

Tool provenance fingerprints actual declared byte inputs and the job; external IDs and elapsed
time are not identity. Foreign tool behavior is not promised deterministic. Python/Java runtime
environments are not fully fingerprinted. Repeated proposal/decision regeneration may require
reviewing a different candidate; confirmation executes no external process and writes staged bytes.

POSIX timeout/cancellation and finished-parent descendants are tested with authored processes.
Windows taskkill invocation/failure is tested with a fake. Native Windows tree behavior remains
unconfirmed, including a background descendant after an already-finished parent. No sandbox or
electrical certification is claimed.

## Native and closing checks still open

H-K-EXTERNAL-CANDIDATES stays UNKNOWN. The native proof command exited 0 with **four skips**
because local KiCadRoutingTools and the Freerouting jar are absent. Skips are not a passing oracle.
Two/four-layer authored fixtures are wired into the existing router CI job with pinned
KiCadRoutingTools v0.22.1 and Freerouting 2.4.1 (existing pins/sources in
[the routing evidence](routing.md)). They require unchanged pre-accept inputs, exact tool versions,
reviewed acceptance, one fewer native open and no increased native DRC type. Tool installation
remains explicit in CI; candidate commands never download or import the tools.

The quick gate passed 15835 tests with 43 skips (exit 0) before the final candidate-limit
parity fix. That fix first reproduced a missing-control assertion, then passed 113 fresh
CLI/guide/workflow tests. The final complete quick gate also passed: make exit 0, 15835 passed, 43 skipped in
589.63 s. Exact-head full CI remains pending and is recorded as open in the change tasks. There
is no transferable CI result for these uncommitted changes. No merge or archive is authorized.

## Pinned KiCadRoutingTools refusal — 2026-11-04

CI runs 41936811685 and 41947475460 (pinned KiCadRoutingTools v0.22.1, KiCad 9 and 10) returned no
KiCadRoutingTools candidate: every proposal was refused `external-unsupported-output` with no tool error,
while Freerouting 2.4.1 passed. Reproduced locally with the same release (macOS arm64 core): the tool
writes `(start 106.000000 110.800000)`; the KiCad reader keeps a child it would not re-emit byte for byte
(`kicad.board.kept-opaque`) although the model holds the same value, and the candidate check treated any kept
child as opaque output. The check now accepts a kept child only when it re-spells the item's own
start/end/width (track) or at/size/drill (via) to the exact nanometre; any other child, a different value or a
fraction of a nanometre still refuses (`test_a_respelled_modelled_number_is_not_opaque_output`). Local
result on KiCad 10.0.6: `test_external_candidates.py` 2 passed (both KiCadRoutingTools layers), 2 skipped
(no Freerouting jar locally). Exact-head pinned CI remains the gate (`UNKNOWN` until then).

## Authored/source byte snapshot

Refreshed 2026-11-04 after the KiCadRoutingTools fix. The fixtures below are Fenolite-authored; no employer or third-party circuit/parser material is
used. The fake checkouts/JARs are authored by tests/_fakerouter.py and tests/_fakefreerouting.py.
No new vendor format fact is introduced; existing adapters and their registered sources are reused.

| File | SHA-256 |
|---|---|
| `src/fenolite/routing/external_candidates.py` | `f50b008818831b84533145dfdd87a036c5076e33cd015ec40c527839a5bf9e2e` |
| `src/fenolite/routing/external_delta.py` | `75dc3ee84729dbaf670bd5a4dcb1008b582c23237557bf82d6db93ee20e4a682` |
| `src/fenolite/routing/budget.py` | `b99bfcca2ab858b61a4f73dfe9727d039ff796efbbcb5cfc2ac4792bd4fead04` |
| `src/fenolite/cli/_external_candidates.py` | `fb54aba7849d9e05b9cc86ef5553b819e57e5a4d6da2f643fa688d7ed981668c` |
| `tests/unit/routing/test_external_candidate_contract.py` | `bf779f0f5e4512d4d2aec1f68685ae4a682058c3b1a4d8a96254f47525f96f1d` |
| `tests/unit/routing/test_external_candidates.py` | `eae189fcbec8aa03ad426193ab694a2e1e8b891e173dc76ce650634ab571a1f6` |
| `tests/unit/routing/test_external_candidate_budget.py` | `498df87bdf7fa9ece21bfa019bcdc65b874904be574820e209c8a360c6c66607` |
| `tests/unit/cli/test_route_propose_with.py` | `c266df0fc2086334b66df386c05542bc482f471110ced3c1a3fda9a8ec50b0d0` |
| `tests/kicad/routing/test_external_candidates.py` | `177d98bae2fdb4e7bfdc3d6992eae631094d948e11cbc6fe90586ad1a15c695d` |

## Exact-head CI — 2026-11-05

CI run 41968083051 (head 5f46b8d7) concluded success: H-K-EXTERNAL-CANDIDATES is KICAD-VERIFIED (9.0.x, 10.0.x); both pinned tools passed. Earlier statements that this row stays `UNKNOWN` until CI are superseded by this run. Native Altium and maintainer checks named above stay open.
