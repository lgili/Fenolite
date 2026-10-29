## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`fenolite-component-catalog`, `cli-contract`, `repo-layout`) and the changes it builds on (c0249, c0259, c0262; c0260, c0261, c0254). Write under this task, with the date and the base commit:
  - c0249's `LockSection` protocol and whether a new section can be registered without changing its reader;
  - c0259's record module and tree rules, and c0262's command and job names used by the pack CI;
  - which open change holds a delta of "Build resolves built-in definitions" or "Zero runtime dependencies in the core" (c0195 holds one of the latter; regenerate the MODIFIED blocks from the living text, and add `devices` to whatever list is living);
  - which other library changes reserve `library` verbs (c0262 `check`/`review`, c0264 `import`, c0265 `propose`), so the verb list of design decision 8 is final;
  - the maintainer's answers to the open questions of `design.md` (repository name and namespace first);
  - the next free `S-` numbers (the data repository's releases, the LibrePCB format documentation and the LibrePCB library).

  Proof: `openspec validate c0266-device-packs --strict`; `make check-fast`.
- [ ] 0.2 Write `docs/adr/0008-fetching-device-packs.md` and add a dated line under ADR-0007's decision 1 pointing to it; register the sources. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit -k adr -q`.

## 1. Packs in the core

- [ ] 1.1 Move `tree_hash` to `src/fenolite/core/treehash.py`, re-exported from `backends/kicad/libcache.py`. Proof: `uv run pytest tests/unit/backends/kicad -k libcache tests/unit/core -q`.
- [ ] 1.2 `src/fenolite/catalog/packs.py`: `read_pack`, the manifest and `sources.toml` checks, `find_packs` over paths, the extra and the cache (scenarios "A pack is read", "Reserved namespace", "Unregistered pack source", "Cached pack without stamp is ignored", "Extra found without import"). Author `tests/data/packs/demo/`, each file with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/catalog/test_packs.py -q`.
- [ ] 1.3 Lazy pack lookup in the runner (`cli/_script.py`), precedence, `library.pack-conflict`, `library.overrides-pack`, `library.pack-incompatible`, and the origin `pack` in the build (scenarios "Project wins over the pack", "Two packs, one id", "Unused pack changes nothing", "Pack needs a newer core", "Pack definition resolved offline"). Proof: `uv run pytest tests/unit/cli/test_build_packs.py tests/unit/lens -k pack -q`.
- [ ] 1.4 The `library` lock section through c0249's `LockSection`, `library.pack-locked`, `library.pack-released`, `library.pack-missing` with `FEN-6004`, `library.pack-tree-differs`, `--frozen` (scenarios "First use pins the pack", "Newer pack does not move a lock", "Locked pack not installed", "Frozen build refuses a first pin", "Code registered and explained"). Proof: `uv run pytest tests/unit/cli/test_build_packs.py -k lock tests/unit/cli/test_exitcodes.py tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 1.5 Offline guard (scenario "Build with packs and no network"). Register `H-G-DEVICE-PACKS`. Proof: `uv run pytest tests/unit/cli/test_build_packs.py -k offline -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 2. Commands

- [ ] 2.1 Verbs in `cli/cmd_library.py` with the board-path form unchanged, and `capabilities` entries (scenarios "Board path form unchanged", "Verbs are listed"). Proof: `uv run pytest tests/unit/cli/test_library_cmd.py tests/unit/cli/test_capabilities.py -q`.
- [ ] 2.2 `library fetch`: `cli/data/packs.toml`, the plan, the deferred write, archive and tree checks, safe extraction, stamp, `--pin`, `--locked`, `--sha256` (scenarios "Dry run makes no request", "Install from a file and pin", "Tampered archive", "Unsafe member refused"). Proof: `uv run pytest tests/unit/cli/test_library_fetch.py -q`; `uv run pytest tests/consistency -q`.
- [ ] 2.3 `library packs` and the short lists in `capabilities` and `doctor` (scenario "Verify finds an edit"). Proof: `uv run pytest tests/unit/cli/test_library_packs.py tests/unit/cli/test_doctor.py -q`.
- [ ] 2.4 Extra `devices` in `pyproject.toml` and the invariant test (scenario "The devices extra is pinned data"). Proof: `uv run pytest tests/unit/test_pyproject_invariants.py -q`.

## 3. LibrePCB seed

- [ ] 3.1 `docs/formats/librepcb/library.md` from public LibrePCB documentation only (elements, files, units, axes, rotations, signal roles), each fact with source and evidence label; no parser code read. Proof: `uv run pytest tests/unit/test_provenance.py -q`.
- [ ] 3.2 `src/fenolite/backends/librepcb/`: its tokenizer and element reader written from that page; authored fixtures under `tests/data/librepcb/demo/`. Proof: `uv run pytest tests/unit/backends/librepcb -q`; `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 3.3 `library seed`: licence gate, commit check, mapping to records, ids, skips, plan and confirm, no overwrite of reviewed records (scenarios "Seed records carry their origin", "Not a CC0 library", "Commit mismatch", "Same bytes twice", "Custom pad outline skipped", "Reviewed record kept"). Proof: `uv run pytest tests/unit/cli/test_library_seed.py -q`.

## 4. The data repository

- [ ] 4.1 Create `fenolite-devices` (after the maintainer's answer to open question 1): `LICENSE` (CC0 legal code), `pack.toml`, `sources.toml`, `VERSIONS.toml`, `README.md` (stating the seed risk), `CONTRIBUTING.md` (DCO, what may enter), `CODEOWNERS`. Proof: `fenolite library check . --all --json` exits 0 in that repository.
- [ ] 4.2 Its `check.yml` (records, regenerate, versions, origin, renders with visual diff, double pack build) and `release.yml` (archive, `SHA256SUMS`, `index.json`, data-only wheel); the recipe is mirrored in Fenolite's test (scenario "Archive is reproducible"). Proof: `uv run pytest tests/unit/catalog/test_pack_archive.py -q`; the first pull request of the data repository green.
- [ ] 4.3 First release `v1.0.0`, its row in `packs.toml` with size, digests and source, and the exact pin of the extra. Proof: `uv run pytest tests/unit/cli/test_library_fetch.py -k table -q`.
- [ ] 4.4 Main-repository CI job `packs`: `fenolite library fetch --locked examples/packs/design.py --confirm`, then build the example (`H-G-PACK-FETCH`). Proof: the `packs` job green on the pushed head.

## 5. Closing

- [ ] 5.1 Docs: `docs/packs.md` (repository, releases, discovery, precedence, lock, offline use, fetch, seed and its risk), `library fetch|packs|seed` and `FEN-6004` in `docs/cli-contract.md`, links from `docs/index.md` and `docs/library-records.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
- [ ] 5.2 Agent guide: tested lines in `parts.md` for `fenolite library fetch --locked`, `fenolite library packs` and `fenolite library seed`, and for `FEN-6004`, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.3 Example `examples/packs/` (a design using one demo-pack device, its lock, offline with `--pack`). Proof: `uv run pytest tests/unit/test_examples.py -k packs tests/unit/cli/test_hermetic_examples.py -q`.
- [ ] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit, KiCad, packs) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
