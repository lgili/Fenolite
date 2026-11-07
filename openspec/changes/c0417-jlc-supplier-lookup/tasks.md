# c0417 tasks

**Blocked:** no task after 0.1 starts until the maintainer has supplied the approved JLC API documentation
and terms. Source: c0267 design, "Found on 2026-11-04" (maintainer decision cutting JLC from c0267).

## 0. Maintainer's documents and sources

- [ ] 0.1 **Maintainer:** supply the approved JLC API documentation and terms (base URL, authentication,
  endpoints, parameters, response keys, rate limits, cache and storage rights, attribution) and the
  approved API access. No agent may infer, probe or copy them. Proof: the maintainer records where the
  documents are and that they are approved.
- [ ] 0.2 Register each document in `docs/evidence/sources.md` (ids from the coordinator's range) and write
  `docs/formats/suppliers/jlc.md` with every fact, its source and an evidence label, after the shape of the
  four public pages. Record in `design.md` anything the c0267 machinery lacks for this API. Proof:
  `uv run pytest tests/unit/suppliers/test_policy.py -q` still passes (no plugin yet).

## 1. Plugin

- [ ] 1.1 `src/fenolite/suppliers/jlc.py` on the c0267 machinery, with its `SourcePolicy` equal to the page,
  credentials `FENOLITE_JLC_<NAME>` and keyring service `fenolite.suppliers.jlc`. Proof:
  `uv run pytest tests/unit/suppliers/test_policy.py tests/unit/suppliers/test_credentials.py -q`.
- [ ] 1.2 Authored fake responses under `tests/fixtures/suppliers/jlc/` with sidecars (fictional parts,
  `example.invalid` links) and `tests/unit/suppliers/test_jlc.py`, socket patched. Proof:
  `uv run pytest tests/unit/suppliers -q`.
- [ ] 1.3 Entry point `jlc = "fenolite.suppliers.jlc:Jlc"` in `pyproject.toml`; `test_registry.py` loads
  five plugins. Proof: `uv run pytest tests/unit/suppliers/test_registry.py -q`.

## 2. Docs

- [ ] 2.1 The four supplier pages and `src/fenolite/agent/skill/references/supplier-lookup.md` name JLC's gate
  instead of "JLC remains unregistered"; `uv run python tools/gen_agent_guide.py`. Proof:
  `uv run pytest tests/unit/agent -q`.
- [ ] 2.2 `CHANGELOG.md` under `## [Unreleased]`; residue scan clean (`tools/residue/scan.py`).

## 3. Closure

- [ ] 3.1 Root-owned: `ci-complete` on the exact commit, then archive. If the maintainer withdraws JLC, the
  change is closed unimplemented with the reason recorded here.
