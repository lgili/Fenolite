## 0. Entry check

- [x] 0.1 Read `openspec list`, the living specs this change touches (`block-library`, `design-dsl`,
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

  Entry read 2026-11-01, base `8d74a798`: c0249, c0268 and c0279 are implemented and unarchived.
  No living `block-library` file exists yet; its c0268 delta is the current contract. `describe`,
  `record_json`, sources `builtin` and `file`, and `[blocks]` are implemented. Phase A of c0279 supplies
  `fenolite_library/`, `[library.items."<kind>/<id>"]` and FEN-6004. Lock order is refs,picks,pins,blocks,library.
  `_run_script` inserts the script folder first but currently fails to isolate namespace-package cache
  entries; task 2.1 covers that. Open decisions take the dated choices in design.md. Strict validation
  is run locally; the complete gate is reserved for the integration worker, so 0.1 stays open for it.
  Strict validation passed without warnings. The integrated make check-fast proof is deliberately
  unrun here under the user's serialized-gate instruction.

  Entry refresh 2026-11-02, integration base `697cdf02b39c570b7827bd2b7b5419dfcf6bdea6`:
  c0249/c0268/c0279 phase A remain active and implemented; no living block-library
  or fenolite-library spec exists yet. `dsl.record.describe/record_json` retain canonical
  block records, and `cli.blocksrc.SOURCES` is builtin/library/file. `[blocks]` pins block
  identity/version separately from `[library.items]`; section order is refs,picks,pins,blocks,library.
  `get` uses fenolite_library/ and the missing pinned item remains FEN-6004. `_run_script`
  puts the script folder first and now restores/isolates namespace imports as well, so the
  earlier entry's cache-isolation defect is implemented rather than still pending. All four
  accepted recommendations remain authored FenoliteBlocks/Apache-2.0 items, a small core
  starter set, private repositories later in the same format, and separate get/upgrade reviews.
  None of this records an external release, third-party legal approval or completed CI.

  Available proof: `openspec validate c0273-block-packages --strict` passes without warnings
  (OpenSpec 1.16.0).
  The literal `make check-fast` is not run by this worker and has no applicable passing
  serialized receipt yet. Task 0.1 remains unchecked for that actual proof; independent
  CI, native/manual and release criteria are unchanged.

  Entry proof completed 2026-11-02 on `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`: root
  ran the serialized `make check-fast` from 09:45:03 to 10:17:02 UTC, exit 0
  (19564 passed, 55 skipped; JUnit records zero failures/errors). Fresh OpenSpec
  1.16.0 strict validation of this change also passes without warnings. The
  `a85f7846` entry review was checked against this source: dependencies remain
  active, no new archival requires rebasing a delta, and the named APIs, accepted
  decisions and current dispatcher/record contracts still apply.
  This dated proof supersedes the earlier missing-fast-gate blocker only.
  Independent CI, native/manual, corpus, external-library and release criteria
  remain unchanged. The source-bound receipt, log and JUnit hashes are recorded
  in [the integration validation record](../c0319-integration-repairs/validation.md).

## 1. Block items and discovery

- [x] 1.1 Add `dsl/blockitem.py` (schema `fenolite.block-item.v0`, canonical text) and the verb
  `blocks index` with `--check`, with the authored test item `tests/data/library_repo/block_items/blocks/cc0/Demo/led/`
  (CC0, authored for Fenolite; scenarios "Record file of a test item", "Index check fails on a stale file").
  Proof: `uv run pytest tests/unit/cli/test_blocks_index.py -q`.
  Passed 2026-11-01: 13 tests, including source-bound review, stale same-process imports, manifest
  identity, exact export count and static range-text/digest/page round trips.
- [x] 1.2 Add `cli/blockvendored.py` (`find_vendored`), the catalog source `library`, `--script` on
  `blocks list|show|doc`, `blocks.item-broken` and `blocks.namespace-reserved` (scenarios "Listed without
  import", "Reserved namespace in a vendored folder"). Proof: `uv run pytest tests/unit/cli/test_blockvendored.py -q`.
  Passed 2026-11-01: 11 tests; poison imports stay unexecuted for list/show/doc, malformed records
  are named, reserved namespace and duplicate ids fail, and documentation plans bind static inputs.
- [x] 1.3 Add the starter-library rules to the record tests (scenario "Starter block uses a library
  device"). Proof: `uv run pytest tests/unit/blocks/test_records.py -q`.
  Passed 2026-11-01: 4 tests; the authored outside-device control is named and real shipped records pass.

## 2. Build and lock

- [x] 2.1 Vendored blocks in the build: import through `fenolite_library.blocks`, the record-file comparison,
  `[blocks]` entries next to c0279's `[library.items]` (scenarios "Vendored block imported by the script",
  "Locally edited vendored block", "Vendored block pinned twice over", "Starter blocks are not pinned as
  items"). Register `H-G-BLOCK-PACKAGES` with its new statement (vendored library blocks are listed
  without import, and pinned versions resolve the same blocks on every platform). Proof:
  `uv run pytest tests/unit/cli/test_build_library_blocks.py tests/unit/test_hypotheses_register.py -q`.
  Passed 2026-11-01: 45 tests. Authored release get/build preserves literal item pins and records
  instances; local code edits warn; namespace packages restore across projects; missing pins stop
  before script execution; reviewed builds bind vendored source bytes.
- [x] 2.2 The `get` hint for an unpinned missing block module (scenario "Block never vendored"). Proof:
  `uv run pytest tests/unit/cli/test_build_library_blocks.py -k missing -q`.
  Passed 2026-11-01: 5 tests; absent namespace ancestors retain the full literal block id from the
  failed import statement, unrelated missing modules keep the normal script error, and pinned misses
  retain FEN-6004 before execution.

## 3. Upgrade

- [x] 3.1 Add the verb `blocks upgrade` with its plan, `result.upgrades`, the circuit difference and
  `blocks.upgrade-major`. Replace the hint of c0268's `lock.block-version` with
  `fenolite blocks upgrade <script>` (scenarios "Planned upgrade", "Build after the upgrade", "Circuit
  difference shown"). Proof: `uv run pytest tests/unit/cli/test_blocks_upgrade.py -q`.
  Passed 2026-11-01: 15 tests, covering reviewed lock-only writes, all step types, selection,
  baseline circuit changes/additions/removals, stale inputs, major refusal, errors and no script rerun.
  The final package proof adds the block-body relative-import regression (16 upgrade cases total).

## 4. Documentation, guide and the library

- [x] 4.1 `docs/blocks.md`: the three tiers, writing a library block item (package folder, `block.json`,
  `--check` in the library's CI, sources, version rules), getting one with `fenolite get block`, the lock
  pins and upgrading. `docs/cli-contract.md`: `blocks index`, `blocks upgrade` and `--script`. Proof:
  regenerate derived command references, then `uv run pytest tests/consistency -q`.
  Passed 2026-11-01: 662 tests, 41 expected mutating-command skips. Derived commands were regenerated;
  the written block-package guide follows in task 4.2.
- [x] 4.2 Agent guide (AGENTS.md rule 6): a tested line for `fenolite get block`, `blocks index` and
  `blocks upgrade` on the written page `library-items` (the generated command pages are regenerated).
  The existing design-script page is at its byte budget. Proof:
  `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
  Passed 2026-11-01: 81 tests; generated references and --check are current. The written library-items
  page teaches static discovery, explicit indexing, separate item/instance pins and reviewed upgrades.
- [ ] 4.3 In `lgili/fenolite-library`: the blocks jobs of `check.yml` (record-file check, version rules,
  c0270 tests and usage builds, import-graph and no-side-effect tests, sources) and a first authored
  `FenoliteBlocks` item. Proof: that repository's pull request green, and `fenolite library audit . --json`
  exits 0 there.
  Authorized local follow-up (2026-11-01): external library commit
  `2ce4d2f0dab580e7ea2f78e3bd48716352ad9918` adds the original CC0
  `FenoliteBlocks:resistor_link` package, record, usage, golden and two connectivity tests, plus block
  index/test, AST-import and import-side-effect workflow checks. With clean core `5d8afc2f`, index
  `--check`, usage/golden/two tests, the item audit and the exact local block-workflow body pass.
  The task remains open: no actual external branch CI or pull request ran, the public `b8b24842` tool
  pin lacks the new commands, the immutable KiCad image is unset, and the unchanged board tree's root
  audit still reports 38 existing findings. Follow-up with combined core `7c2f1df2` passes the same
  external item's index check, usage/golden/two tests and item audit, with external source status
  unchanged. This is an item-level local proof; no push, PR, tag, release, Pages publication, full
  external audit success or actual CI is claimed.

  Local source update — 2026-11-03, library
  `5edffa69584890dbf5c4cea0bc3ad613fa176f6c`: the immutable KiCad image is
  already configured as
  `docker.io/kicad/kicad@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`.
  The actual read-only root audit now exits 0 with zero findings across 20
  items; the 19 other item rows are identical to the preceding audit. The
  actual Royal per-item audit with base `8b38b30` also exits 0, including its
  metadata version step. See `local-library-audit-proof.json` for commands,
  sources and complete log/receipt hashes. This dated update supersedes only
  the older unset-image and 38-finding status above.

  Royal's correction restores historical metadata only: the expected checksum
  of 67 unchanged payload files and the original documented S skip reason.
  Payload, licence, accepted entries and original proof levels remain intact.
  It is not a new replay or current fidelity qualification; the two fresh L7
  findings remain open separately. The public core pin is still `b8b24842`;
  actual required library CI/publication and release gates remain open.
  Task 4.3 is not checked by this local schema-audit result.

## 5. Closing

- [x] 5.1 Run `uv run pytest tests/residue -q` and update evidence labels. Proof:
  `uv run pytest tests/residue tests/unit/test_inferred_hypotheses.py -q`.
  Passed 2026-11-01 on staged files: 41 tests, 5 unfetched-corpus skips. The package hypothesis remains
  inferred; no cross-platform CI or external-repository workflow result is claimed.
- [x] 5.2 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof:
  `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
  Passed 2026-11-01 on the supplied 0.7.0.dev0 base: 710 tests, 41 expected mutating-command skips;
  one Added entry records the package protocol and reviewed upgrades.
- [ ] 5.3 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on
  that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4).
  Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
  Open: the integration worker owns publication, the serialized local gate and exact-commit CI.
  This worker makes signed local commits only and claims no CI result.
