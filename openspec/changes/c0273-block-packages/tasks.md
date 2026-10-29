## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`block-library`, `design-dsl`,
  `cli-contract`) and the state of c0249, c0266, c0267 and c0268. Write under this task the date, the base
  commit, and:
  - whether c0268 is archived, with the names of `describe`, `record_json`, the catalog sources and the
    `[blocks]` section;
  - whether c0249's `LockSection` and c0266's `library` section are archived, and the order of lock
    sections written so far;
  - the `FEN-6` codes taken by then (c0266 and c0267 both propose `FEN-6004`), and the number this change
    uses in place of `FEN-6006` if that one is taken. Rename it in every file of this change before task 2.2;
  - whether the entry-point group name `fenolite.blocks` is free on PyPI search and in the repository;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0273-block-packages --strict`; `make check-fast`.

## 1. Packages and the index

- [ ] 1.1 Add `dsl/blockindex.py` (schema `fenolite.block-index.v0`, canonical text) and the verb
  `blocks index` with `--check`, with the authored test distribution `tests/data/blocks/pkg/` (CC0,
  authored for Fenolite; scenarios "Index of the test distribution", "Index check fails on a stale file").
  Proof: `uv run pytest tests/unit/cli/test_blocks_index.py -q`.
- [ ] 1.2 Add `cli/blockpkg.py` (`find_packages`, entry points, `find_spec`, index reading) and the catalog
  source `package`. The tests install the test distribution into a temporary environment with `uv pip
  install --target`, without network (scenarios "Dotted value ignored", "Listed without import", "Two
  distributions, one namespace"). Proof: `uv run pytest tests/unit/cli/test_blockpkg.py -q`.
- [ ] 1.3 Add the starter-library rules to the record tests (scenario "Starter block uses a pack device").
  Proof: `uv run pytest tests/unit/blocks/test_records.py -q`.

## 2. Lock and build

- [ ] 2.1 Register the lock section `block-packages` with its resolution, the codes
  `lock.block-package-moved` and `lock.block-package-released`, and the build-time index comparison
  (scenarios "First use pins the package", "Package release with unchanged blocks", "Starter blocks are not
  pinned as a package", "Stale index in a build"). Proof:
  `uv run pytest tests/unit/dsl/test_lock_block_packages.py tests/unit/cli/test_build_block_packages.py -q`.
- [ ] 2.2 Register `FEN-6006` and map a missing pinned package to it in `cli/_script.py` (scenarios
  "Package not installed", "Code registered"). Proof:
  `uv run pytest tests/unit/cli/test_build_block_packages.py -k missing tests/unit/cli/test_explain_cmd.py -q`.

## 3. Upgrade, capabilities and doctor

- [ ] 3.1 Add the verb `blocks upgrade` with its plan, `result.upgrades`, the circuit difference and
  `blocks.upgrade-major`. Replace the hint of c0268's `lock.block-version` with
  `fenolite blocks upgrade <script>` (scenarios "Planned upgrade", "Build after the upgrade", "Circuit
  difference shown"). Proof: `uv run pytest tests/unit/cli/test_blocks_upgrade.py -q`.
- [ ] 3.2 Report block packages in `capabilities` and `doctor` (scenario "Installed package reported").
  Proof: `uv run pytest tests/unit/cli/test_capabilities.py tests/unit/cli/test_doctor_cmd.py -k block -q`.

## 4. Documentation and guide

- [ ] 4.1 `docs/blocks.md`: the three tiers, writing a block package (entry point, index, `--check` in its
  CI, sources registry, version rules), installing one as a project dependency, the lock pins and
  upgrading. `docs/cli-contract.md`: `blocks index`, `blocks upgrade`, `FEN-6006` and
  `capabilities.block_packages`. Proof: `uv run pytest tests/consistency -q`.
- [ ] 4.2 Agent guide (AGENTS.md rule 6): a tested line for `blocks index`, `blocks upgrade` and
  `FEN-6006` on the page `commands`, and for the exit-6 case on the page `recovery`. Regenerate the
  generated pages. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 4.3 Outside this repository, prepare the `fenolite-blocks` repository: `pyproject.toml` with the
  entry point, an empty package with its index, `sources.toml`, `VERSIONS.toml`, and a CI that runs the
  index check and the version rules with a pinned released `fenolite`. Record the repository address in
  `docs/blocks.md`. Proof: that repository's CI run is green, and its address is in `docs/blocks.md`
  (checked by `uv run pytest tests/consistency -q`).

## 5. Changelog and CI

- [ ] 5.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof:
  `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 5.2 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on
  that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4).
  Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
