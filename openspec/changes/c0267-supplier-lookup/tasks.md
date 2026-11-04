## Maintainer deferral — 2026-11-02

The maintainer explicitly authorized skipping this change if JLC remained
blocked: "qualquer coisa se ficar travado com a jlc pula essa spec, vou deixar
ela mais para frente dai". The remaining c0267/JLC work is deferred from the
overnight CAC delivery. Approved access and the public documentation landing
page were supplied, but no complete reviewed HTTP contract/terms proof was
established. Existing unchecked tasks remain unchecked; this is a deferral,
not completion or authorization to register a guessed plugin.

## 0. Entry check

- [x] 0.1 Read `openspec list`, the living specs this change touches (`cli-contract`, `package-layering`) and c0254 (archived or open) and c0263. Write under this task, with the date and the base commit:
  - c0254's final names for `pick.propose.Supplier`, the proposal row format, `--allow-offsite` and `--limit`;
  - whether c0263's `decode` is available, and its result type;
  - which open change holds a delta of "Allowed import edges" (regenerate the MODIFIED block from the living text if one was archived);
  - the next free `S-` numbers and the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0267-supplier-lookup --strict`.

  Entry 2026-11-01, base 8d74a798: c0254 is implemented/open. `pick.propose.Supplier.propose`
  takes a PartQuery and returns complete Mapping[str,str] rows; the rich hook will remain optional.
  `--allow-offsite` exists and `--limit` is the common paging flag. c0263 is implemented/open:
  `pick.grammar.decode.decode(mpn, families)` returns DecodeResult with Decoded candidates.
  Active c0254/c0256/c0268/c0279 deltas extend the living Allowed import edges; the supplier row is
  added without removing those packages. Reserved source ids are S-1100..1119; FEN-6005 is free in src.
  Recommended decisions are accepted 2026-11-01. Public terms/readiness remains gated on evidence.

- [x] 0.2 Register the public sources per supplier (API documentation, terms of use, rate limits, attribution rules), re-reading each terms page, and write `docs/formats/suppliers/{digikey,mouser,nexar,farnell}.md` with every endpoint, parameter, response key, limit, cache rule and attribution, each with its source and label (`UNVERIFIED` for anything read second-hand). Proof: `uv run pytest tests/unit/test_provenance.py -q`.

  Passed 2026-11-04 on base 468d8a61: every terms page was reread. DigiKey S-1221/S-1102 and Farnell
  S-1109/S-1108 are readable and unchanged in substance; Octopart/Nexar S-1107 now serves its APIs section
  body (SHA-256 dfa4bfa1…), closing the missing-body gap without granting cache or identity-storage rights.
  Mouser S-1222/S-1103 blocked every read (automation-denial page SHA-256 35b75bad…, browser 403); the gate
  was not bypassed, so its facts rest on the SHA-bound 2026-11-01 body and their currency is UNVERIFIED.
  The four pages record each reread with labels; no policy, readiness, cache or level changed.
  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/suppliers -q`, 127 passed.

## 1. Package and shared machinery

- [x] 1.1 Add `src/fenolite/suppliers/`, its row in the import-graph test, the extra `suppliers = ["keyring>=25"]` and the entry points in `pyproject.toml`, and the extras invariant test (scenarios "Plugins without the extra", "Suppliers stay behind the entry points"). Proof: `uv run pytest tests/unit/test_import_graph.py tests/unit/test_pyproject_invariants.py tests/unit/suppliers/test_registry.py -q`.
- [x] 1.2 `policy.py`, `credentials.py` (`Secret`, variables, keyring), `FEN-6005` in `cli/errors.py` (scenario "A secret never leaks"). Proof: `uv run pytest tests/unit/suppliers/test_credentials.py tests/unit/cli/test_errors.py -q`.
- [x] 1.3 `http.py` (`Transport`, `UrllibTransport`, size cap, host list, redaction), `ratelimit.py`, `cache.py`, `FakeTransport` in `tests/unit/suppliers/conftest.py` (scenarios "A repeated 429", "Nothing outlives the run"). Proof: `uv run pytest tests/unit/suppliers/test_http.py tests/unit/suppliers/test_cache.py -q`.
- [x] 1.4 `rows.py`: proposal rows with the `persist` fields, provenance, attribution and c0263 decode (scenarios "Offers are shown, not written", "A decoded and an unknown MPN", "Attribution travels with the row", "No request on confirm"). Proof: `uv run pytest tests/unit/suppliers/test_rows.py -q`.

- [x] 1.5 Regenerate `uv.lock` and prove installation of the optional `suppliers` extra in the worktree's
  own environment. Proof: `uv lock --offline --check`; `uv sync --offline --extra dev --extra geo --extra suppliers`.
  Passed 2026-11-01: the lock resolves 83 packages; offline sync checks the own environment's 27
  packages with keyring 25.7.0 and its optional transitives. Core dependencies remain empty.

## 2. Plugins

- [x] 2.1 `digikey.py` with its authored fake responses and sidecars (scenario "Only the query leaves"). Proof: `uv run pytest tests/unit/suppliers/test_digikey.py -q`.
- [x] 2.2 `mouser.py` with its fake responses (the key redacted from every URL in messages). Proof: `uv run pytest tests/unit/suppliers/test_mouser.py -q`.
- [x] 2.3 `nexar.py` with its fake responses. Proof: `uv run pytest tests/unit/suppliers/test_nexar.py -q`.
- [x] 2.4 `farnell.py` with its fake responses and cache `none`. Proof: `uv run pytest tests/unit/suppliers/test_farnell.py -q`.
- [x] 2.5 Policies against their pages; fixtures authored and offline (scenarios "Policies agree with their pages", "Fixtures are authored and offline"). Proof: `uv run pytest tests/unit/suppliers -q`.

## 3. Command integration

- [x] 3.1 `result.suppliers` in `capabilities`, `supplier.*` codes in `explain.toml`, the build-path isolation test (scenarios "Suppliers listed offline", "Rejected credentials", "A build stays offline", "Every supplier code is explained"). Proof: `uv run pytest tests/unit/cli/test_capabilities_cmd.py tests/unit/cli/test_pick_cmd.py tests/unit/cli/test_explain_cmd.py tests/unit/suppliers/test_isolation.py -q`.

## 4. Docs and guide

- [x] 4.1 `docs/suppliers.md` (setup per source with the user's own account, what is sent, cached and written, attribution, no shared keys), `docs/cli-contract.md` (`FEN-6005`, `result.suppliers`) and `docs/picking.md` ("Supplier proposals"). Proof: `uv run pytest tests/consistency -q`.
- [x] 4.2 Agent guide: a focused `supplier-lookup` page with tested proposal flags and `FEN-6005`/`supplier.*` lines, linked from `parts` and `recovery` because both are at their budgets; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 5. JLC (cut on 2026-11-04)

- [x] 5.1 Cut from this change by the maintainer on 2026-11-04: JLC needs the maintainer's own approved API access. Record the cut in design.md ("Found on 2026-11-04") and propose the JLC plugin as a follow-up change; register no JLC plugin, policy, fixture or entry point here. Proof: design section recorded; `uv run pytest tests/unit/suppliers -q` passes with no `jlc` entry point or module (127 passed with the provenance tests, 2026-11-04).
  The former task text ("`jlc.py`, its policy and fake responses, and its entry point, after the maintainer records the JLC documentation and terms") moves unchanged to the follow-up change.

## 6. Closing

- [x] 6.1 Residue: every fixture and sidecar carries its authored line, no real MPN or key is in the tree, no absolute path. Proof: `.venv/bin/python tools/residue/scan.py`.
- [x] 6.2 Evidence: `H-G-SUPPLIER-OFFLINE` in `docs/hypotheses.md` with its measurement; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 6.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev` (the guard of v0.6 keeps `[Unreleased]` empty until then). Proof: `.venv/bin/python -m pytest tests/unit/test_release_record*.py tests/unit/test_release_tool.py -k changelog -q`.
- [ ] 6.4 Run `make check-fast`, publish the batch to its working branch, and read the required CI jobs on the exact commit. Proof: `make check-fast`; the required jobs green on the pushed head.

Initial framework review 2026-11-01: 0.2 remained open because primary DigiKey terms were inaccessible,
Mouser terms returned 403, Nexar API-terms body was unavailable and Farnell's readable partner
terms do not establish durable identity-row rights. Shared machinery proceeds with authored test
policies; production policies stay unavailable. Source-specific readiness tasks remain open.

Initial framework delivery proof 2026-11-01: the final `uv run pytest` group with the suppliers extra installed passes
197 supplier/CLI/plan-replay/import/extras tests. Consistency: 662 pass, 41 expected mutating skips.
Guide: 117 pass, 19 require KiCad 10 and are skipped on this installation. Provenance, hypotheses,
release and authored-data checks: 54 pass; focused changelog selection: 7 pass. Ruff, pyright,
schema/guide/evidence freshness, residue and strict OpenSpec checks pass. No live supplier request,
account, key or product data was used.

At that framework checkpoint, tasks 2.1–2.4 remained open: DigiKey/Nexar mappings were unavailable; Mouser/Farnell documented
mappings and authored fixtures pass offline, but source-specific readiness was unproven. Current policies
remain unavailable with no persistence or cache. Task 5.1 remains closed to implementation pending
approved JLC sources. Task 6.4 is open: the maintainer serializes full gates, publication and exact-head CI;
focused local proofs do not substitute for them.

## Public-source continuation audit — 2026-11-01

Base 17706a46 in an isolated supplier worktree. S-1220..S-1227 were checked for collisions across source
registers and active designs before use. The DigiKey keyword Swagger and primary API agreement are
now readable: section 5.1(e) restricts creating/updating an information database, so durable identity
permission remains unestablished. Mouser's exact primary API terms URL still returns403. Nexar's
public API accordion body remains unavailable; current primary add-on documentation excludes any
assumption of specs/datasheet/ECAD entitlement. Farnell's primary 4(A) storage restriction and 5 source
attribution/link obligations were reread. All four production policies remain unavailable with no
cache or persistence. Task 0.2 remains open for missing primary terms/rights completeness; task 5.1
remains open because approved JLC API documentation/terms have not been supplied. No JLC registration,
API key, live request, billing or source-data permission is assumed.

## Authored protocol proofs — 2026-11-01

Tasks 2.1–2.4 are implementation proofs under explicit fictional test permissions, not production
readiness. Their individual required commands pass with sockets forbidden:

- 2.1 `tests/unit/suppliers/test_digikey.py`: 15 passed. Primary-documented token/keyword requests,
  local query/result bounds, malformed token/container refusal, rejected credentials and received-token
  redaction are covered. New token and keyword fixtures/sidecars are authored CC0 and registered.
- 2.2 `tests/unit/suppliers/test_mouser.py`: 11 passed. Documented source errors cannot turn partial
  rows into success; optional attribute/price arrays are validated, absence and local bounds retained.
- 2.3 `tests/unit/suppliers/test_nexar.py`: 18 passed. Supply-scope token and basic JSON GraphQL,
  escaped query text, no assumed add-ons, partial/error refusal, documented auth error codes, selected
  container validation and received-token redaction are covered. A Retry-After warning survives a later
  GraphQL error; partial data never clears it. New fixtures are authored CC0 only.
- 2.4 `tests/unit/suppliers/test_farnell.py`: 16 passed. The documented keyword mapping keeps cache
  disabled, distinguishes absent fields from malformed arrays/offers, and applies its local limit.

The source/provenance/policy audit group passes 10 tests, but does not close 0.2: missing primary terms
bodies and unestablished durable identity rights remain real dependencies. All policies still have
ready=false, persist=[] and cache=none, checked before credentials or transport. JLC 5.1 remains gated
and unregistered. Full fast, publication and exact-head CI 6.4 remain owned by the coordinating branch.
No live supplier request, real credential, billing, product answer or provider implementation was used.

## Primary terms body follow-up — 2026-11-01

The approved plain public fetch of S-1222 returned HTTP 200 and 128331 bytes; the local SHA-256 matches
`e59c7416f2e979658091c098b838cebccd9844f56eb7ac644a02082466073b7f`. This is actual Mouser Search API
Terms of Service (last modified 2013-03-11), with the complete numbered sections, not only a challenge.
Sections 2/4/5/6/7 establish application-specific approval, a content-storage prohibition, conspicuous
source credit/preserved links, account-assigned call limits and deletion after termination. No new
numeric limit or permission to persist identity drafts is established. Source/policy notes now record
these primary facts; the first framework/adapter proofs above retain their original review context.

This resolves the Mouser primary-body portion of 0.2 only. The Nexar plain fetch returned 403; its error
body is not terms evidence. Task 0.2 stays open for the missing Nexar API terms body and unestablished
permitted identity scope. All four production policies remain unavailable, with no cache or persistence,
and no runtime mapping or public result shape changed. Tasks 5.1/6.4 remain open for their prior reasons.

The follow-up source/policy/registry/Mouser/capabilities group passes 25 tests. It checks the recorded
terms against policy data and retains every production gate. Lint, format, public residue, generated
guide/schema/evidence checks and strict OpenSpec pass. The 231 adapter/CLI tests on 33f878e3 remain
the functional checkpoint; no mapping or shared HTTP algorithm changed in this evidence-only follow-up.
