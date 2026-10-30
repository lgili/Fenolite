## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`cli-contract`, `design-dsl`, `corpus-policy`, `ip-hygiene`, `public-presentation`) and the changes it builds on (c0249, c0259, c0262, c0266, c0268, c0273; c0275 to c0278 for phase B). Write under this task, with the date and the base commit:
  - c0249's `LockSection` protocol and the order of lock sections so far (`refs`, `picks`, `pins`, `blocks`, `library`);
  - the `FEN-` codes taken by then; confirm `FEN-6004`, `FEN-6006`, `FEN-4003` and `FEN-3008` are free or renumber them in every file of this change, c0266 and c0273 before task 2.4;
  - which `library` verbs other changes reserve (c0260 `generate`, c0261 `symbol`, c0262 `check`/`review`, c0264 `import`, c0265 `propose`, c0266 `seed`), so the dispatch table is final;
  - the host's per-release asset limit and the GitHub Pages rules, registered as sources;
  - the SPDX list entries of every allow-listed id and the normalised licence-text digests, registered as sources;
  - the next free `S-` numbers and hypothesis ids (`H-G-LIBRARY-GET`, `H-G-LIBRARY-REPLAY`).

  Proof: `openspec validate c0279-fenolite-library --strict`; `make check-fast`.
- [ ] 0.2 Write `docs/adr/0008-getting-library-items.md`, add a dated line under ADR-0007's decision 1 pointing to it, and add the dated `fenolite-library` line to ADR-0003. Proof: `uv run pytest tests/unit/test_adrs.py tests/unit/test_legal_docs.py -q`.
- [ ] 0.3 Add the AGENTS.md sentence under "Hard rules" and its test (scenarios "Sentence present", "Sentence removed"). Proof: `uv run pytest tests/unit/test_legal_docs.py -k fenolite_library -q`.

## 1. Phase A: schemas, licences and audit

- [ ] 1.1 `src/fenolite/library/items.py` and `provenance.py`: `fenolite.library-item.v0` and `fenolite.provenance.v0` readers, canonical JSON writers, id and family rules; add `library` to the layering table. Author `tests/data/library/demo/`, each file with the authored-for-Fenolite line in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/unit/library/test_items.py tests/unit/library/test_provenance.py tests/unit/test_import_graph.py -q`.
- [ ] 1.2 `src/fenolite/library/licences.py` and `cli/data/library-licences.toml`: the allow-list, deny reasons, families, reciprocal flags, obligations and normalised text digests. Proof: `uv run pytest tests/unit/library/test_licences.py -q`.
- [ ] 1.3 `fenolite library audit` with every `library.*` audit code and `--base` version rules (scenarios "Item in the wrong family", "One id in two families", "Unlisted file", "Block items execute", "Converted item without a commit", "Provenance and manifest disagree", "Allowed id accepted", "Non-commercial licence refused", "Platform-restricted origin refused", "Notice without modification line", "README without the use statement"). Proof: `uv run pytest tests/unit/library/test_audit.py -q`.

## 2. Phase A: releases and `get`

- [ ] 2.1 `fenolite library release`: index, shards, board archives, `SHA256SUMS`, byte-reproducible recipe (scenario "Release is reproducible"). Proof: `uv run pytest tests/unit/library/test_release.py -q`.
- [ ] 2.2 `src/fenolite/library/get.py` and `cli/cmd_get.py`: plan, closure, copy targets, `ATTRIBUTION.md`, `--from`, client licence check, licence acceptance (scenarios "Plan a device with its closure", "Confirmed copy keeps the licence files", "Share-alike item needs acceptance", "Accepted by name", "Release with a denied item", "Conflicting dependency"). Proof: `uv run pytest tests/unit/cli/test_get.py -q`.
- [ ] 2.3 Cache, trust chain, network rules, `--offline`, `--refresh`, `cli/data/library.toml` (scenarios "Dry run makes no request", "Tampered archive", "Search the cached index", "Nothing cached"). Register `H-G-LIBRARY-GET`. Proof: `uv run pytest tests/unit/cli/test_get_cache.py tests/unit/test_hypotheses_register.py -q`; `uv run pytest tests/consistency -q`.
- [ ] 2.4 The lock section `library`, the build check, updates, removals, `--locked`, `--status`, `--list`, `--search`, and the codes `FEN-6004`, `FEN-6006`, `FEN-4003`, `FEN-3008` (scenarios "Pin written by get", "Build leaves the section alone", "Fresh clone without library folder", "Local edit protected", "Restore after a fresh clone", "Codes explained"). Proof: `uv run pytest tests/unit/cli/test_get_lock.py tests/unit/cli/test_exitcodes.py tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 2.5 `capabilities` entries for `get` and the `library` verbs (scenario "Verbs listed"). Proof: `uv run pytest tests/unit/cli/test_capabilities.py -q`.

## 3. Phase A: the repository

- [ ] 3.1 Create `lgili/fenolite-library`: `README.md` (licence and use statements), `LICENSE` (CC0-1.0 for its own files), `library.toml`, `licences.toml` (equal to the shipped copy), `sources.toml`, `CONTRIBUTING.md` (DCO, what may enter, licence lists), `CODEOWNERS`, the empty kind folders. Proof: `fenolite library audit . --json` exits 0 in that repository.
- [ ] 3.2 Its `check.yml` (audit, records, blocks, renders) and `release.yml`; a test in Fenolite keeps the shipped licence list equal to the library's at each release. Proof: the first pull request of the library green; `uv run pytest tests/unit/library/test_licences.py -k shipped_copy -q`.
- [ ] 3.3 First release `v1.0.0` with c0266's and c0273's first items, and its row in `cli/data/library.toml`. Proof: `uv run pytest tests/unit/cli/test_get_cache.py -k table -q`.
- [ ] 3.4 Corpus alignment: the manifest rule for `library:` rows and the residue rule for committed items (scenarios "Share-alike library row marked embeddable", "Vendored item committed"). Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue -q`.

## 4. Phase B: boards, replay, proof and gallery (after c0275 to c0278)

- [ ] 4.1 `fenolite library replay` with the tool allow-list and the authored upstream fixture `tests/data/library/upstream/blink/` (scenarios "Replay reproduces an authored conversion", "Unknown tool refused"). Register `H-G-LIBRARY-REPLAY`. Proof: `uv run pytest tests/unit/library/test_replay.py tests/unit/test_hypotheses_register.py -q`.
- [ ] 4.2 The proof gate over c0278's report and the benchmark table (scenarios "Accepted difference passes", "New difference fails", "Benchmark table"). Proof: `uv run pytest tests/unit/library/test_proof_gate.py tests/unit/library/test_bench_table.py -q`.
- [ ] 4.3 `fenolite library gallery` (scenarios "Card attribution", "Restricted marks hidden") and the `public-presentation` check (scenario "Image without attribution"). Proof: `uv run pytest tests/unit/library/test_gallery.py tests/unit/test_public_presentation.py -k library -q`.
- [ ] 4.4 In the library: `replay` and `proof` jobs in `check.yml`, `bench.yml`, `gallery.yml` with Pages; Fenolite's optional scheduled job `library-bench`. Proof: the library's workflows green on their first runs; `uv run pytest tests/unit/test_ci_workflow.py -q`.
- [ ] 4.5 First boards (research section 4.6): the KiCad demos with a usable licence (not the non-commercial one), each converted, replayed and proved, with accepted differences recorded and reviewed. Proof: the library's `check.yml` green on the pull request that adds them.

## 5. Closing

- [ ] 5.1 Docs: `docs/library-repo.md` (repository, kinds, families, provenance, licences, CI, releases, gallery, `get`, cache, lock, use statement), `get` and the `library` verbs and the four codes in `docs/cli-contract.md`, links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`; `uv run pytest tests/consistency -q`.
- [ ] 5.2 Agent guide (AGENTS.md rule 6): tested lines for `fenolite get`, `fenolite get --locked`, `fenolite get --search`, the `library` verbs and the four codes, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.3 Example `examples/library-get/`: a design using one authored demo device got from a local release folder, with its lock, offline. Proof: `uv run pytest tests/unit/test_examples.py -k library_get -q`.
- [ ] 5.4 Run `uv run pytest tests/residue -q` and update evidence labels of the new behaviours. Proof: `uv run pytest tests/residue tests/unit/test_inferred_hypotheses.py -q`.
- [ ] 5.5 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.6 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit, KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
