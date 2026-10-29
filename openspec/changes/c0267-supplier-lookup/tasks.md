## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`cli-contract`, `package-layering`) and c0254 (archived or open) and c0263. Write under this task, with the date and the base commit:
  - c0254's final names for `pick.propose.Supplier`, the proposal row format, `--allow-offsite` and `--limit`;
  - whether c0263's `decode` is available, and its result type;
  - which open change holds a delta of "Allowed import edges" (regenerate the MODIFIED block from the living text if one was archived);
  - the next free `S-` numbers and the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0267-supplier-lookup --strict`.
- [ ] 0.2 Register the public sources per supplier (API documentation, terms of use, rate limits, attribution rules), re-reading each terms page, and write `docs/formats/suppliers/{digikey,mouser,nexar,farnell}.md` with every endpoint, parameter, response key, limit, cache rule and attribution, each with its source and label (`UNVERIFIED` for anything read second-hand). Proof: `uv run pytest tests/unit/test_provenance.py -q`.

## 1. Package and shared machinery

- [ ] 1.1 Add `src/fenolite/suppliers/`, its row in the import-graph test, the extra `suppliers = ["keyring>=25"]` and the entry points in `pyproject.toml`, and the extras invariant test (scenarios "Plugins without the extra", "Suppliers stay behind the entry points"). Proof: `uv run pytest tests/unit/test_import_graph.py tests/unit/test_pyproject_invariants.py tests/unit/suppliers/test_registry.py -q`.
- [ ] 1.2 `policy.py`, `credentials.py` (`Secret`, variables, keyring), `FEN-6004` in `cli/errors.py` (scenario "A secret never leaks"). Proof: `uv run pytest tests/unit/suppliers/test_credentials.py tests/unit/cli/test_errors.py -q`.
- [ ] 1.3 `http.py` (`Transport`, `UrllibTransport`, size cap, host list, redaction), `ratelimit.py`, `cache.py`, `FakeTransport` in `tests/unit/suppliers/conftest.py` (scenarios "A repeated 429", "Nothing outlives the run"). Proof: `uv run pytest tests/unit/suppliers/test_http.py tests/unit/suppliers/test_cache.py -q`.
- [ ] 1.4 `rows.py`: proposal rows with the `persist` fields, provenance, attribution and c0263 decode (scenarios "Offers are shown, not written", "A decoded and an unknown MPN", "Attribution travels with the row", "No request on confirm"). Proof: `uv run pytest tests/unit/suppliers/test_rows.py -q`.

## 2. Plugins

- [ ] 2.1 `digikey.py` with its authored fake responses and sidecars (scenario "Only the query leaves"). Proof: `uv run pytest tests/unit/suppliers/test_digikey.py -q`.
- [ ] 2.2 `mouser.py` with its fake responses (the key redacted from every URL in messages). Proof: `uv run pytest tests/unit/suppliers/test_mouser.py -q`.
- [ ] 2.3 `nexar.py` with its fake responses. Proof: `uv run pytest tests/unit/suppliers/test_nexar.py -q`.
- [ ] 2.4 `farnell.py` with its fake responses and cache `none`. Proof: `uv run pytest tests/unit/suppliers/test_farnell.py -q`.
- [ ] 2.5 Policies against their pages; fixtures authored and offline (scenarios "Policies agree with their pages", "Fixtures are authored and offline"). Proof: `uv run pytest tests/unit/suppliers -q`.

## 3. Command integration

- [ ] 3.1 `result.suppliers` in `capabilities`, `supplier.*` codes in `explain.toml`, the build-path isolation test (scenarios "Suppliers listed offline", "Rejected credentials", "A build stays offline", "Every supplier code is explained"). Proof: `uv run pytest tests/unit/cli/test_capabilities_cmd.py tests/unit/cli/test_pick_cmd.py -k supplier tests/unit/cli/test_explain_cmd.py tests/unit/suppliers/test_isolation.py -q`.

## 4. Docs and guide

- [ ] 4.1 `docs/suppliers.md` (setup per source with the user's own account, what is sent, cached and written, attribution, no shared keys), `docs/cli-contract.md` (`FEN-6004`, `result.suppliers`) and `docs/picking.md` ("Supplier proposals"). Proof: `uv run pytest tests/consistency -q`.
- [ ] 4.2 Agent guide: a tested line for `--supplier` proposals on `parts`, and for `FEN-6004` and the `supplier.*` codes on `recovery`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 5. JLC (gated)

- [ ] 5.1 Only after the maintainer, with approved access, has recorded the JLC API documentation and terms in `docs/formats/suppliers/jlc.md`: `jlc.py`, its policy and fake responses, and its entry point. Until then this task stays open and the plugin is not registered. Proof: `uv run pytest tests/unit/suppliers/test_jlc.py tests/unit/suppliers/test_policy.py -q`.

## 6. Closing

- [ ] 6.1 Residue: every fixture and sidecar carries its authored line, no real MPN or key is in the tree, no absolute path. Proof: `make residue`.
- [ ] 6.2 Evidence: `H-G-SUPPLIER-OFFLINE` in `docs/hypotheses.md` with its measurement; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev` (the guard of v0.6 keeps `[Unreleased]` empty until then). Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 6.4 Run `make check-fast`, publish the batch to its working branch, and read the required CI jobs on the exact commit. Proof: `make check-fast`; the required jobs green on the pushed head.
