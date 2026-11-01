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

- [ ] 0.2 Register the public sources per supplier (API documentation, terms of use, rate limits, attribution rules), re-reading each terms page, and write `docs/formats/suppliers/{digikey,mouser,nexar,farnell}.md` with every endpoint, parameter, response key, limit, cache rule and attribution, each with its source and label (`UNVERIFIED` for anything read second-hand). Proof: `uv run pytest tests/unit/test_provenance.py -q`.

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

- [ ] 2.1 `digikey.py` with its authored fake responses and sidecars (scenario "Only the query leaves"). Proof: `uv run pytest tests/unit/suppliers/test_digikey.py -q`.
- [ ] 2.2 `mouser.py` with its fake responses (the key redacted from every URL in messages). Proof: `uv run pytest tests/unit/suppliers/test_mouser.py -q`.
- [ ] 2.3 `nexar.py` with its fake responses. Proof: `uv run pytest tests/unit/suppliers/test_nexar.py -q`.
- [ ] 2.4 `farnell.py` with its fake responses and cache `none`. Proof: `uv run pytest tests/unit/suppliers/test_farnell.py -q`.
- [x] 2.5 Policies against their pages; fixtures authored and offline (scenarios "Policies agree with their pages", "Fixtures are authored and offline"). Proof: `uv run pytest tests/unit/suppliers -q`.

## 3. Command integration

- [x] 3.1 `result.suppliers` in `capabilities`, `supplier.*` codes in `explain.toml`, the build-path isolation test (scenarios "Suppliers listed offline", "Rejected credentials", "A build stays offline", "Every supplier code is explained"). Proof: `uv run pytest tests/unit/cli/test_capabilities_cmd.py tests/unit/cli/test_pick_cmd.py tests/unit/cli/test_explain_cmd.py tests/unit/suppliers/test_isolation.py -q`.

## 4. Docs and guide

- [x] 4.1 `docs/suppliers.md` (setup per source with the user's own account, what is sent, cached and written, attribution, no shared keys), `docs/cli-contract.md` (`FEN-6005`, `result.suppliers`) and `docs/picking.md` ("Supplier proposals"). Proof: `uv run pytest tests/consistency -q`.
- [x] 4.2 Agent guide: a focused `supplier-lookup` page with tested proposal flags and `FEN-6005`/`supplier.*` lines, linked from `parts` and `recovery` because both are at their budgets; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 5. JLC (gated)

- [ ] 5.1 Only after the maintainer, with approved access, has recorded the JLC API documentation and terms in `docs/formats/suppliers/jlc.md`: `jlc.py`, its policy and fake responses, and its entry point. Until then this task stays open and the plugin is not registered. Proof: `uv run pytest tests/unit/suppliers/test_jlc.py tests/unit/suppliers/test_policy.py -q`.

## 6. Closing

- [x] 6.1 Residue: every fixture and sidecar carries its authored line, no real MPN or key is in the tree, no absolute path. Proof: `.venv/bin/python tools/residue/scan.py`.
- [x] 6.2 Evidence: `H-G-SUPPLIER-OFFLINE` in `docs/hypotheses.md` with its measurement; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 6.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev` (the guard of v0.6 keeps `[Unreleased]` empty until then). Proof: `.venv/bin/python -m pytest tests/unit/test_release_record*.py tests/unit/test_release_tool.py -k changelog -q`.
- [ ] 6.4 Run `make check-fast`, publish the batch to its working branch, and read the required CI jobs on the exact commit. Proof: `make check-fast`; the required jobs green on the pushed head.

Source review 2026-11-01: 0.2 remains open because primary DigiKey terms were inaccessible,
Mouser terms returned 403, Nexar API-terms body was unavailable and Farnell's readable partner
terms do not establish durable identity-row rights. Shared machinery proceeds with authored test
policies; production policies stay unavailable. Source-specific readiness tasks remain open.

Delivery proof 2026-11-01: the final `uv run pytest` group with the suppliers extra installed passes
197 supplier/CLI/plan-replay/import/extras tests. Consistency: 662 pass, 41 expected mutating skips.
Guide: 117 pass, 19 require KiCad 10 and are skipped on this installation. Provenance, hypotheses,
release and authored-data checks: 54 pass; focused changelog selection: 7 pass. Ruff, pyright,
schema/guide/evidence freshness, residue and strict OpenSpec checks pass. No live supplier request,
account, key or product data was used.

Tasks 2.1–2.4 remain open: DigiKey/Nexar response mappings are unavailable; Mouser/Farnell documented
mappings and authored fixtures pass offline, but source-specific readiness is unproven. Current policies
remain unavailable with no persistence or cache. Task 5.1 remains closed to implementation pending
approved JLC sources. Task 6.4 is open: the maintainer serializes full gates, publication and exact-head CI;
focused local proofs do not substitute for them.
