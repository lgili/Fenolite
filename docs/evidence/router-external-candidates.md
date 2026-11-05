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

## Authored/source byte snapshot

The fixtures below are Fenolite-authored; no employer or third-party circuit/parser material is
used. The fake checkouts/JARs are authored by tests/_fakerouter.py and tests/_fakefreerouting.py.
No new vendor format fact is introduced; existing adapters and their registered sources are reused.

| File | SHA-256 |
|---|---|
| `src/fenolite/routing/external_candidates.py` | `bcfcd5c0ff6d1c033f0206795812ba8eb6722837c4503a6f38cd7f5ff610826c` |
| `src/fenolite/routing/external_delta.py` | `f5ddcfbbdf8ebf836e5492ca8abd00050f24d9029b75cfa637a46eaa071a270f` |
| `src/fenolite/routing/budget.py` | `b99bfcca2ab858b61a4f73dfe9727d039ff796efbbcb5cfc2ac4792bd4fead04` |
| `src/fenolite/cli/_external_candidates.py` | `91c6ac2e15f5b39f035f06a0654f97d4ad2457c5e76d3b85a6f5cc2a63292a0a` |
| `tests/unit/routing/test_external_candidate_contract.py` | `f466b69b9a4cc02c11696165bcf60432ce98b11b1b6a1bfd0ef19f991e1e7f6d` |
| `tests/unit/routing/test_external_candidates.py` | `eae189fcbec8aa03ad426193ab694a2e1e8b891e173dc76ce650634ab571a1f6` |
| `tests/unit/routing/test_external_candidate_budget.py` | `498df87bdf7fa9ece21bfa019bcdc65b874904be574820e209c8a360c6c66607` |
| `tests/unit/cli/test_route_propose_with.py` | `41ce3b613e6a02c9ac0283ffafc9898dc6cfe390f368dd040fd1e2d01a2a66f6` |
| `tests/kicad/routing/test_external_candidates.py` | `56747e357f7e364fc20650fdfe3cc29717af1fa2c25e7845a43ea4b10e4a7d2a` |
