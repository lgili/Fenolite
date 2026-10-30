## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`block-library`, `design-dsl`,
  `cli-contract`) and the state of c0249, c0268 and c0279. Write under this task the date, the base
  commit, and:
  - whether c0268 is archived, with the names of `describe`, `record_json`, the catalog sources and the
    `[blocks]` section;
  - whether c0279 phase A is archived, with the vendored folder name (`fenolite_library/`), the
    `[library.items]` key form and `FEN-6004`;
  - whether the runner puts the script's folder first on `sys.path`, so namespace packages under
    `fenolite_library/` import;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0273-block-packages --strict`; `make check-fast`.

## 1. Block items and discovery

- [ ] 1.1 Add `dsl/blockitem.py` (schema `fenolite.block-item.v0`, canonical text) and the verb
  `blocks index` with `--check`, with the authored test item `tests/data/library/demo/blocks/apache/Demo/led/`
  (CC0, authored for Fenolite; scenarios "Record file of a test item", "Index check fails on a stale file").
  Proof: `uv run pytest tests/unit/cli/test_blocks_index.py -q`.
- [ ] 1.2 Add `cli/blockvendored.py` (`find_vendored`), the catalog source `library`, `--script` on
  `blocks list|show|doc`, `blocks.item-broken` and `blocks.namespace-reserved` (scenarios "Listed without
  import", "Reserved namespace in a vendored folder"). Proof: `uv run pytest tests/unit/cli/test_blockvendored.py -q`.
- [ ] 1.3 Add the starter-library rules to the record tests (scenario "Starter block uses a library
  device"). Proof: `uv run pytest tests/unit/blocks/test_records.py -q`.

## 2. Build and lock

- [ ] 2.1 Vendored blocks in the build: import through `fenolite_library.blocks`, the record-file comparison,
  `[blocks]` entries next to c0279's `[library.items]` (scenarios "Vendored block imported by the script",
  "Locally edited vendored block", "Vendored block pinned twice over", "Starter blocks are not pinned as
  items"). Register `H-G-BLOCK-PACKAGES` with its new statement (vendored library blocks are listed
  without import, and pinned versions resolve the same blocks on every platform). Proof:
  `uv run pytest tests/unit/cli/test_build_library_blocks.py tests/unit/test_hypotheses_register.py -q`.
- [ ] 2.2 The `get` hint for an unpinned missing block module (scenario "Block never vendored"). Proof:
  `uv run pytest tests/unit/cli/test_build_library_blocks.py -k missing -q`.

## 3. Upgrade

- [ ] 3.1 Add the verb `blocks upgrade` with its plan, `result.upgrades`, the circuit difference and
  `blocks.upgrade-major`. Replace the hint of c0268's `lock.block-version` with
  `fenolite blocks upgrade <script>` (scenarios "Planned upgrade", "Build after the upgrade", "Circuit
  difference shown"). Proof: `uv run pytest tests/unit/cli/test_blocks_upgrade.py -q`.

## 4. Documentation, guide and the library

- [ ] 4.1 `docs/blocks.md`: the three tiers, writing a library block item (package folder, `block.json`,
  `--check` in the library's CI, sources, version rules), getting one with `fenolite get block`, the lock
  pins and upgrading. `docs/cli-contract.md`: `blocks index`, `blocks upgrade` and `--script`. Proof:
  `uv run pytest tests/consistency -q`.
- [ ] 4.2 Agent guide (AGENTS.md rule 6): a tested line for `fenolite get block`, `blocks index` and
  `blocks upgrade` on the page `commands`. Regenerate the generated pages. Proof:
  `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 4.3 In `lgili/fenolite-library`: the blocks jobs of `check.yml` (record-file check, version rules,
  c0270 tests and usage builds, import-graph and no-side-effect tests, sources) and a first authored
  `FenoliteBlocks` item. Proof: that repository's pull request green, and `fenolite library audit . --json`
  exits 0 there.

## 5. Closing

- [ ] 5.1 Run `uv run pytest tests/residue -q` and update evidence labels. Proof:
  `uv run pytest tests/residue tests/unit/test_inferred_hypotheses.py -q`.
- [ ] 5.2 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof:
  `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 5.3 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on
  that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4).
  Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
