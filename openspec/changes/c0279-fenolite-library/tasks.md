## 0. Entry check

- [x] 0.1 Read `openspec list`, the living specs this change touches (`cli-contract`, `design-dsl`, `corpus-policy`, `ip-hygiene`, `public-presentation`) and the changes it builds on (c0249, c0259, c0262, c0266, c0268, c0273; c0275 to c0278 for phase B). Write under this task, with the date and the base commit:
  - c0249's `LockSection` protocol and the order of lock sections so far (`refs`, `picks`, `pins`, `blocks`, `library`);
  - the `FEN-` codes taken by then; confirm `FEN-6004`, `FEN-6006`, `FEN-4003` and `FEN-3021` are free or renumber them in every file of this change, c0266 and c0273 before task 2.4;
  - which `library` verbs other changes reserve (c0260 `generate`, c0261 `symbol`, c0262 `check`/`review`, c0264 `import`, c0265 `propose`, c0266 `seed`), so the dispatch table is final;
  - the host's per-release asset limit and the GitHub Pages rules, registered as sources;
  - the SPDX list entries of every allow-listed id and the normalised licence-text digests, registered as sources;
  - the next free `S-` numbers and hypothesis ids (`H-G-LIBRARY-GET`, `H-G-LIBRARY-REPLAY`).
  Open 2026-10-30: the entry check above is written; its proof (`openspec validate --strict`) is left to the coordinator.

  Proof: `openspec validate c0279-fenolite-library --strict`; `make check-fast`.

  Entry check 2026-10-30, base `52f32e8c` (`circuits-as-code`):
  - `LockSection(name, resolve, exact)` in `fenolite.dsl.lock`; sections on the base: `refs`, `picks`, `pins`
    (c0268's `blocks` is not merged). This change appends `library` with the new flag `paths=False`: its keys
    are `<kind>/<id>`, not component paths, so the carry and release steps leave it alone.
  - Codes: `FEN-6004` (shared with c0266 and c0273 by design), `FEN-6006` (c0273 no longer needs it) and
    `FEN-4003` are free on every branch. `FEN-3008` to `FEN-3010` are taken by c0306 to c0310 on other
    branches, so `FEN-3008` of this change is renumbered `FEN-3021` in every file of this change (c0266 and
    c0273 do not name it).
  - Reserved `library` verbs: `symbol` (c0261, available), `check`, `review` (c0262), `import` (c0264),
    `propose` (c0265), `fetch` (c0266); c0260's `generate` and c0266's `seed` are not in the dispatch table
    yet. This change adds `audit`, `replay`, `release`, `gallery`.
  - Sources registered: S-1000 (GitHub releases: up to 1000 assets per release, each file under 2 GiB),
    S-1001 (GitHub Pages limits: 1 GB site, 100 GB/month soft bandwidth, no commercial hosting), S-1002
    (SPDX License List 3.29.0: every allow-listed id is a licence id, except `SHL-2.0` and `SHL-2.1`, which
    are licence exceptions used as `Apache-2.0 WITH SHL-2.x`; both spellings map to the family `solderpad`).
    Normalised licence-text digests: lower case, whitespace runs collapsed to one space, no final newline
    (measured on the library's four boards: `CC-BY-SA-4.0` gives `17a696cf…`); the shipped table lists that
    digest only, so other ids need `licence_review` until the library records their digests.
  - Hypotheses `H-G-LIBRARY-GET` and `H-G-LIBRARY-REPLAY` are already proposed in `docs/hypotheses.md`.
  Proof: `make check-fast` passed (see 5.6); `openspec validate` is left to the coordinator.
- [x] 0.2 Write `docs/adr/0008-getting-library-items.md`, add a dated line under ADR-0007's decision 1 pointing to it, and add the dated `fenolite-library` line to ADR-0003. Proof: `uv run pytest tests/unit/test_adrs.py tests/unit/test_legal_docs.py -q`.
  Done 2026-10-30: ADR-0008 written and indexed (next free 0009), dated lines in ADR-0007 decision 1 and ADR-0003; `test_adr_0008_states_the_rules_and_is_linked`. Proof passed (33 passed).
- [x] 0.3 Add the AGENTS.md sentence under "Hard rules" and its test (scenarios "Sentence present", "Sentence removed"). Proof: `uv run pytest tests/unit/test_legal_docs.py -k fenolite_library -q`.
  Done 2026-10-30: the rule under "Hard rules" of AGENTS.md; `test_fenolite_library_sentence_present` and `_removed` in tests/unit/test_legal_docs.py. Proof passed.

  Integration recheck 2026-10-31, base `30efd832`, incoming `98e8eb945`: lock order is refs, picks, pins, blocks, library; both release and path policies are retained. Incoming sources were renumbered to S-1000/S-1001/S-1002 after collisions with c0260. Strict validation passed (valid, no warnings); 221 focused library/get/edit/overlay tests passed (one external-checkout test skipped), 66 lock/generator/paging tests passed, and 95 guide/generator tests passed. The licensed-items guide moved to library-items to preserve byte and line limits. Entry remains open until the batch check-fast proof finishes. External repository, release and dependent example tasks remain open.

## 1. Phase A: schemas, licences and audit

- [x] 1.1 `src/fenolite/library/items.py` and `provenance.py`: `fenolite.library-item.v0` and `fenolite.provenance.v0` readers, canonical JSON writers, id and family rules; add `library` to the layering table. Author `tests/data/library_repo/demo/`, each file with the authored-for-Fenolite line in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/unit/library/test_items.py tests/unit/library/test_provenance.py tests/unit/test_import_graph.py -q`.
  Done 2026-10-30: `fenolite.library.items` (kinds, ids, `item.json`, canonical JSON, the tree digest `fenolite-tree-1` of a file set) and `provenance` (every rule names its field; steps refuse other tools and `--plan`, c0281); the layering row of `library` gains `dsl` and `catalog`. Fixture `tests/data/library_repo/demo/` (34 files declared authored in `tests/data/MANIFEST.toml`; placeholder licence texts with their digests in the fixture's `licences.toml`). Proof passed.
- [x] 1.2 `src/fenolite/library/licences.py` and `cli/data/library-licences.toml`: the allow-list, deny reasons, families, reciprocal flags, obligations and normalised text digests. Proof: `uv run pytest tests/unit/library/test_licences.py -q`.
  Done 2026-10-30: `fenolite.library.licences` and `cli/data/library-licences.toml` (13 families, deny reasons, aliases `Apache-2.0 WITH SHL-2.x`, platform hosts, the `CC-BY-SA-4.0` text digest). Proof passed.
- [x] 1.3 `fenolite library audit` with every `library.*` audit code and `--base` version rules (scenarios "Item in the wrong family", "One id in two families", "Unlisted file", "Block items execute", "Converted item without a commit", "Provenance and manifest disagree", "Allowed id accepted", "Non-commercial licence refused", "Platform-restricted origin refused", "Notice without modification line", "README without the use statement"). Proof: `uv run pytest tests/unit/library/test_audit.py -q`.
  Done 2026-10-30: `fenolite library audit ROOT [--item PATH] [--base DIR|REF]` (`fenolite.library.audit`, `cli/_library_repo.py`); all eleven scenarios plus vendor-bundled, licence text, depends and git-ref base tests. Run on the library's `first-boards` tree: the four boards pass; its README lacks three statements (library task). Proof passed (19 passed).

## 2. Phase A: releases and `get`

- [x] 2.1 `fenolite library release`: index, shards, board archives, `SHA256SUMS`, byte-reproducible recipe (scenario "Release is reproducible"). Proof: `uv run pytest tests/unit/library/test_release.py -q`.
  Done 2026-10-30: `fenolite.library.release` (index rows also carry `authors`, `upstream` and `files`, a size and SHA-256 per file, so `get` can plan deferred writes before a download) and the verb `library release`. Proof passed.
- [x] 2.2 `src/fenolite/library/get.py` and `cli/cmd_get.py`: plan, closure, copy targets, `ATTRIBUTION.md`, `--from`, client licence check, licence acceptance (scenarios "Plan a device with its closure", "Confirmed copy keeps the licence files", "Share-alike item needs acceptance", "Accepted by name", "Release with a denied item", "Conflicting dependency"). Proof: `uv run pytest tests/unit/cli/test_get.py -q`.
  Done 2026-10-30: `fenolite.library.get` (pure planner) and `cli/cmd_get.py`; all six scenarios plus boards (`--into`, the pin merged into the board's own `design.lock`), `--from` a library checkout or a `file://` git URL (#ref), usage errors. The design name of a new lock is read from the script with `ast`, never run. Proof passed (10 passed).
- [x] 2.3 Cache, trust chain, network rules, `--offline`, `--refresh`, `cli/data/library.toml` (scenarios "Dry run makes no request", "Tampered archive", "Search the cached index", "Nothing cached"). Register `H-G-LIBRARY-GET`. Proof: `uv run pytest tests/unit/cli/test_get_cache.py tests/unit/test_hypotheses_register.py -q`; `uv run pytest tests/consistency -q`.
  Done 2026-10-30: `fenolite.library.cache` (`FENOLITE_LIBRARY_DIR`, stamp), `cli/data/library.toml` (no row yet), `fetch.download_url`; tests set `FENOLITE_LIBRARY_DIR` per test (tests/conftest.py). Deviation: a dry run plans every download as a deferred write with its size and digest; under `--confirm` the command reads the missing assets itself (one request each, checked) before it plans concrete writes, so a board's merged lock can be planned; with no cached index a dry run plans the index only (`result.stage` `index`). `H-G-LIBRARY-GET` measured (stays INFERRED). Proof passed: test_get_cache 9, register 41, consistency 638 passed.
- [x] 2.4 The lock section `library`, the build check, updates, removals, `--locked`, `--status`, `--list`, `--search`, and the codes `FEN-6004`, `FEN-6006`, `FEN-4003`, `FEN-3021` (scenarios "Pin written by get", "Build leaves the section alone", "Fresh clone without library folder", "Local edit protected", "Restore after a fresh clone", "Codes explained"). Proof: `uv run pytest tests/unit/cli/test_get_lock.py tests/unit/cli/test_exitcodes.py tests/unit/cli/test_explain_cmd.py -q`.
  Done 2026-10-30: `LockSection(..., paths=False)` and `[library.items."<kind>/<id>"]` in `fenolite.dsl.lock`; `check_library` in `cli/_lock.py` (`FEN-6004`); updates, `--remove` (files removed after the writes, listed in `result.removes`; such a plan is not staged so `--confirm --plan` reruns), `--locked`, `--status`, `--list`, `--search`; `FEN-3021` (renumbered from FEN-3008), `FEN-4003`, `FEN-6004`, `FEN-6006` registered, explained and in docs/cli-contract.md. Proof passed (8 + 46 passed).
- [x] 2.5 `capabilities` entries for `get` and the `library` verbs (scenario "Verbs listed"). Proof: `uv run pytest tests/unit/cli/test_capabilities.py -q`.
  Done 2026-10-30: `get` is a command; `library audit|replay|release|gallery` are listed in `result.commands` with `mutates` and `usage` (`test_get_and_library_verbs_listed`). Proof passed.

## 3. Phase A: the repository

- [x] 3.1 Create `lgili/fenolite-library`: `README.md` (licence and use statements), `LICENSE` (CC0-1.0 for its own files), `library.toml`, `licences.toml` (equal to the shipped copy), `sources.toml`, `CONTRIBUTING.md` (DCO, what may enter, licence lists), `CODEOWNERS`, the empty kind folders. Proof: `fenolite library audit . --json` exits 0 in that repository.
  Open 2026-10-30: library repository work (`lgili/fenolite-library` exists with README, POLICY.md and the kind folders). Still to add there: `LICENSE` (CC0-1.0), `library.toml`, `licences.toml` (copy of `src/fenolite/cli/data/library-licences.toml`), `sources.toml`, `CONTRIBUTING.md`, `CODEOWNERS`, and the README statements `library audit` checks (the repository's licence does not cover items; test and benchmark inputs; no machine-learning training). Measured 2026-10-30: `library audit` on `first-boards` reports only those three README statements and the boards' missing skip reasons.
- [x] 3.2 Its `check.yml` (audit, records, blocks, renders) and `release.yml`; a test in Fenolite keeps the shipped licence list equal to the library's at each release. Proof: the first pull request of the library green; `uv run pytest tests/unit/library/test_licences.py -k shipped_copy -q`.
  Open 2026-10-30: the workflows are library work. In Fenolite, `test_shipped_copy_equals_the_library_list` compares the shipped list with `<checkout>/licences.toml` when `FENOLITE_LIBRARY_CHECKOUT` is set (skipped otherwise); it passes once the library commits the copy.
  Local 2026-11-04, library `c58cdf2`, local stand-in runner for the `run:` steps of `check.yml` (act is not installed; KiCad 10.0.6 CLI, Python 3.12, core `e7673c81` in a clean venv), library branch `cac/library-completion`: inventory, audit, records, regenerate, versions,
  origin and blocks exit 0; renders exit 0 (run on the preceding `c7dde64`, whose workflow is the same). The
  library's composite action installs the pinned core and compares `licences.toml` with the shipped copy;
  Fenolite's `release.yml` now checks out the library and runs
  `pytest tests/unit/library/test_licences.py -k shipped_copy` with `FENOLITE_LIBRARY_CHECKOUT` set, so each
  Fenolite release fails when the lists differ (`test_release_compares_the_shipped_licence_list`). Proof run:
  `FENOLITE_LIBRARY_CHECKOUT=<clone of c58cdf2> uv run pytest tests/unit/library/test_licences.py -k shipped_copy -q`
  1 passed. Open: nothing is pushed, so no pull request or GitHub run of the library exists; the pin
  `e7673c81` must be published unchanged first.
  Done 2026-11-04: library CI run 41947694170 (`Library checks`, https://github.com/lgili/fenolite-library/actions/runs/41947694170, push of `cac/library-completion`, head `754ed737494ac5c9056f2adfac96477e3f90a158`, the commit tagged `v1.0.0`, core pin `e7673c81`) succeeded with all 21 jobs (inventory, audit, records, regenerate, versions,
  origin, blocks, renders, and six replay and six proof jobs); its composite action compared `licences.toml`
  with the pinned core's shipped copy. `release.yml` is in the library. The Fenolite test passes against a
  clone of that commit (1 passed), and Fenolite's own `release.yml` runs it.
- [ ] 3.3 First release `v1.0.0` with c0266's and c0273's first items, and its row in `cli/data/library.toml`. Proof: `uv run pytest tests/unit/cli/test_get_cache.py -k table -q`.
  Open 2026-10-30: waits for the library's first release `v1.0.0` (c0266 and c0273 items are not merged); then add its `[[release]]` row (version, index_bytes, index_sha256) to `src/fenolite/cli/data/library.toml`. `test_table_rows_are_well_formed` checks the rows.
- [x] 3.4 Corpus alignment: the manifest rule for `library:` rows and the residue rule for committed items (scenarios "Share-alike library row marked embeddable", "Vendored item committed"). Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue -q`.
  Done 2026-10-30: `library_row_problems` in tests/corpus/test_manifest.py (`library:<kind>/<id>@<version>`, `origin:third-party`, embeddable only under CC0) and tests/residue/test_library_items.py (no tracked `fenolite_library/` folder, no converted or seeded `PROVENANCE.json` unless declared authored, which the demo fixture is). Proof passed (91 passed).

## 4. Phase B: boards, replay, proof and gallery (after c0275 to c0278)

- [x] 4.1 `fenolite library replay` with the tool allow-list and the authored upstream fixture `tests/data/library/upstream/blink/` (scenarios "Replay reproduces an authored conversion", "Unknown tool refused"). Register `H-G-LIBRARY-REPLAY`. Proof: `uv run pytest tests/unit/library/test_replay.py tests/unit/test_hypotheses_register.py -q`.
  Done 2026-10-30: `cli/_library_replay.py` (`--upstream`, a shallow git fetch of the pinned commit, `--keep DIR` planned as writes, `--with-current`; `fenolite` steps run in process when the recorded version is the running one, else through `uvx --from fenolite==V`). Deviation: the upstream fixture is the authored `tests/data/fidelity/sensor` (converted in the test, not a new `blink` copy). `H-G-LIBRARY-REPLAY` measured (stays INFERRED). Proof passed (6 + 41 passed).
- [x] 4.2 The proof gate over c0278's report and the benchmark table (scenarios "Accepted difference passes", "New difference fails", "Benchmark table"). Proof: `uv run pytest tests/unit/library/test_proof_gate.py tests/unit/library/test_bench_table.py -q`.
  Done 2026-10-30: `fenolite.library.proof` (`gate`, `derive`, `bench_table`); `library audit` refuses a board whose recorded proof fails, and `library audit --item BOARD --proof REPLY.json` gates a verify-source reply (the proof job). A skipped level passes only with its recorded reason other than `build-failed` (c0281). The library's four boards record S skipped without `fidelity.proof.skipped`: they fail until `verify-source --record` runs again (library task). Proof passed (8 passed).
- [x] 4.3 `fenolite library gallery` (scenarios "Card attribution", "Restricted marks hidden") and the `public-presentation` check (scenario "Image without attribution"). Proof: `uv run pytest tests/unit/library/test_gallery.py tests/unit/test_public_presentation.py -k library -q`.
  Done 2026-10-30: `fenolite.library.gallery` and `cli/_library_gallery.py` (cards with the attribution line, proof, `fenolite get` command and item folder link; index and benchmark pages, the table read from `<release>/bench.json`); `library_image_problems` in tests/unit/test_public_presentation.py. Deviation: the verb writes the pages only; a board card shows `top.svg`/`bottom.svg` that the library's gallery workflow renders with `fenolite render` (task 4.4); cards of symbols, footprints, devices and blocks have no image until c0262 sheets and c0269 schematics land. Proof passed (2 + 2 passed).
- [ ] 4.4 In the library: `replay` and `proof` jobs in `check.yml`, `bench.yml`, `gallery.yml` with Pages; Fenolite's optional scheduled job `library-bench`. Proof: the library's workflows green on their first runs; `uv run pytest tests/unit/test_ci_workflow.py -q`.
  Open 2026-10-30: the workflows belong to the fenolite-library repository (`check.yml` jobs replay/proof: `fenolite library replay <item>`, `fenolite verify-source ... --json > reply.json` then `fenolite library audit . --item <item> --proof reply.json`; `bench.yml`; `gallery.yml` with Pages). Fenolite's optional `library-bench` job waits for the first library release (nothing to download yet).
  Local 2026-11-04: Fenolite's optional nightly job `library-bench` (`continue-on-error`, pinned KiCad 10.0.6
  image) runs `tools/library_bench.py`: newest release from the GitHub API (none yet: it writes
  `not-run.json`), the three boards with the fewest files, `library replay --with-current` and `verify-source`,
  `bench_table`. Proofs: `uv run pytest tests/unit/test_ci_workflow.py -q` (56 passed),
  `uv run pytest tests/unit/tools/test_library_bench.py -q` (4 passed), and an end-to-end run on the library's
  microwave board (equal, proof passed), which found the dangling-link replay crash (task 6.3). In the library
  (`ba21ee1`), the `proof` job now rebuilds the recorded `verify-source` step read-only: it passed the upstream
  folder with default options, so ecc83 (two project files) ended in FEN-2001 and the KiCad 10 projects were
  proved without `--target 10`. With the fix, on `c58cdf2` (local stand-in runner for the `run:` steps of `check.yml` (act is not installed; KiCad 10.0.6 CLI, Python 3.12, core `e7673c81` in a clean venv), library branch `cac/library-completion`), proof passes for nine of
  twelve boards (ecc83 and the Coldfire kit newly). `bench.yml` replays without `--upstream`. Open: the
  workflows' first GitHub runs, and the boards below.
  Partly done 2026-11-04: the `replay` and `proof` jobs passed in library CI run 41947694170 (`Library checks`, https://github.com/lgili/fenolite-library/actions/runs/41947694170, push of `cac/library-completion`, head `754ed737494ac5c9056f2adfac96477e3f90a158`, the commit tagged `v1.0.0`, core pin `e7673c81`), for all six boards of
  `v1.0.0`; Fenolite's `library-bench` job and `tools/library_bench.py` are in (c7fe7c9e). Still open,
  with exact blockers: (1) `bench.yml` has never run. `gh workflow run bench.yml --ref cac/library-completion`
  answers HTTP 404 "workflow bench.yml not found on the default branch", because the library's `main` holds only
  its initial layout. It runs once `cac/library-completion` is merged into `main` (a maintainer or coordinator
  decision). (2) `gallery.yml` runs after `Library checks`/`Library release assets` on a published GitHub
  Release and deploys Pages (`LIBRARY_PAGES_ENABLED`). Publishing the release waits for the maintainer's OK
  with Fenolite v0.7.0.
- [x] 4.5 First boards (research section 4.6): the KiCad demos with a usable licence (not the non-commercial one), each converted, replayed and proved, with accepted differences recorded and reviewed. Proof: the library's `check.yml` green on the pull request that adds them.
  Local 2026-11-04 with core `e7673c81` (the library pin): the twelve boards were converted on 2026-11-03 with
  cores `18351e40`/`5b0853b7` (the `codex/cac-next` line, before c0355 and later import changes). Replay (run
  with `fef4ea08`; `e7673c81` changes only `library review`): equal for ecc83, interf_u, the Coldfire kit,
  microwave, multichannel and pic_programmer; import exits 5 for tiny_tapeout, complex_hierarchy and video
  (c0355 `native project context requires unique supported same-target classes`); output differs for
  openair-max (`design.py`, `native/project*.context.json`), sonde_xilinx and royalblue54l_feather. Proof
  (library `c58cdf2`): sonde_xilinx and video differ at level 6 (the project's Default netclass and
  `max_curve_error` are absent from the payload); royalblue differs at L6, L7 (teardrops) and S. `release.yml`
  calls `check.yml`, which replays and proves every converted board, so v1.0.0 cannot publish until these six
  boards are refreshed with the pinned core (after a c0355 fix) or leave the release. Decided 2026-11-05 by
  the coordinator (design, "First release v1.0.0 without six boards"): they leave v1.0.0 (library `8b485ef`);
  their refresh is the v1.1 item. Open: the library's `check.yml` green on GitHub for the six remaining boards.
  Done 2026-11-04 for the six boards of `v1.0.0`: library CI run 41947694170 (`Library checks`, https://github.com/lgili/fenolite-library/actions/runs/41947694170, push of `cac/library-completion`, head `754ed737494ac5c9056f2adfac96477e3f90a158`, the commit tagged `v1.0.0`, core pin `e7673c81`) replayed and proved ecc83, interf_u,
  kit-dev-coldfire-xilinx_5213, microwave, multichannel and pic_programmer (CC-BY-SA-4.0; the non-commercial
  demo licence is never used), all green, with no accepted differences added. The other six (tiny_tapeout,
  complex_hierarchy, video, openair-max, sonde_xilinx, royalblue54l_feather) left the release by the
  coordinator's decision of 2026-11-05 (design). Their refresh after a core fix (c0355 native project
  context for the first three; native netclass and project context drift for the rest) is the v1.1 item.
- [x] 4.5a Prepare an external OpenAir1.0.2 candidate from the author's immutable
 89aacf5013fc0ffe4b988a2e3c5a227bce3c4983 six-input project (five CAD documents plus its active author DRU), not the incoherent
 KiCad-demo97acc source. Verify manifests/licence bytes, reviewed import plan
 and confirmation, then strict native10 full1–8/S with no accepted differences.
 Preserve the old failed source/647pin155group receipt and all969 authoritative
 payloads. Keep all233 portable3D references name-only: no vendor STEP/official
 library file or inferred model licence. Record external/not-included/not-judged
 3D scope. Only after proof prepare portable1.0.2 provenance/license/audit/review
 packet; root separately owns integration/publication.

  - 2026-11-03: external author-source1.0.2 item packet prepared with the actual reviewed full-proof recording (dry0/confirm0), all nine levels equal,0differences/exclusions/accepted entries,27notices retained. Actual library replay: exit0/equal=true,262payload files identical. Scoped audit with live proof and c62 version base passed; candidate267files private scan0/no exclusions or waivers. All1059authoritative tracked files remain unchanged. Whole archived-library audit still fails with19 pre-existing findings on nine other boards; no whole-library/publication/CI success or authoritative promotion is claimed. Source/proof/limitations: `openair-author-item-review-proof.json`; 4.5 and4.4 remain open.


  - Closure reconciliation2026-11-03:1355sealed packet hashes and267candidate files reverified; original packet unchanged. Located legacy native10.0.6 receipt and unchanged driver bind all five old CAD hashes to the official mirror at97acc. Its scope is647connected numbered/common pins,155native groups versus156PCB groups (2board-only/1native-only), a source mismatch, not equality. The receipt, driver, source copies, approved licence and original failed import exit5 are preserved in a separate external legacy supplement; see the exact hashes/scope in openair-author-item-review-proof.json.233source3D references remain nominal/portable,231vendored definition references share41names;0asset payloads. NoCAD rerun or authoritative write/publication;4.4/4.5global remain open.

  Open 2026-10-30: library repository work. The four KiCad demos of branch `first-boards` pass `library audit` except that their `fidelity.proof` records S skipped without `fidelity.proof.skipped` (rerun `verify-source --record` with this Fenolite) and the README lacks three statements.

- [x] 4.5b Prepare the approved external Tiny1.0.2 pilot from clean core18351e40568f55b4e4e3bb88a64a6e3a9f08c5b4 and immutable upstream97acc: all four CAD files, nominal tables, unchanged approved licence; no active DRU/worksheet/model payload omitted silently. Use explicit target10, actual reviewed import/record plans and readonly replay proof; no accepted differences or fabricated skip reasons. Preserve raw import verbatim, full payload/metadata delta and unrelated failures; keep authoritative library and publication gates unchanged. Proof: actual full1–8/S, replay equality, scoped proof/version audit, private scan and original-input/authoritative hashes. Stop on a real discrepancy.

  - 2026-11-03: external Tiny1.0.2 pilot completed on unchanged/clean18351. Fresh import dry0/confirm0; actual `verify-source --target 10` record dry0/confirm0, all nine levels equal with0differences/exclusions/accepts and one exact route-unjudged/GND/zones notice retained. Actual build target kicad-10; L6generated_major9 is the preserved native project schema, not the build target. Scoped proof/version audit0, actual replay0/equal with144payload files, final149file private scan0/no exclusions or waivers. Old154→new144payload:140changed/14removed/4added; full map retained externally. Authoritative library/input hashes unchanged; external frame changed only Tiny, unrelated17findings/eightitems remain. Intermediate selector9 result, audit-base usage error and harness field assertion are preserved and not presented as target10 acceptance. No authority/publication/CI/human approval follows;4.5/4.4 remain open.

- [x] 4.5c Prepare the approved external complex_hierarchy1.0.2 refresh on clean core5b0853b718e54f2ce487a2545a3ed44df7bd0f9a: full pinned CAD/active resources, byte-identical approved licence/notices, explicit target10, raw import verbatim and actual record dry/exact confirmation, readonly replay, scoped proof/version audit, private scan with no exclusions/waivers and full old/new maps. Keep every notice/unjudged scope and unrelated failures. Microwave routing/S skips require exact measured zero tracks/vias/zones and absent source schematic, never a zero-conductor claim. No new accepts, authoritative promotion or publication; stop/preserve any real discrepancy. Proof: source-bound actual receipts and hashes.

- [x] 4.5d Prepare the approved external ecc831.0.2 refresh on clean core5b0853b718e54f2ce487a2545a3ed44df7bd0f9a: full pinned CAD/active resources, byte-identical approved licence/notices, explicit target10, raw import verbatim and actual record dry/exact confirmation, readonly replay, scoped proof/version audit, private scan with no exclusions/waivers and full old/new maps. Keep every notice/unjudged scope and unrelated failures. Microwave routing/S skips require exact measured zero tracks/vias/zones and absent source schematic, never a zero-conductor claim. No new accepts, authoritative promotion or publication; stop/preserve any real discrepancy. Proof: source-bound actual receipts and hashes.

- [x] 4.5e Prepare the approved external interf_u1.0.2 refresh on clean core5b0853b718e54f2ce487a2545a3ed44df7bd0f9a: full pinned CAD/active resources, byte-identical approved licence/notices, explicit target10, raw import verbatim and actual record dry/exact confirmation, readonly replay, scoped proof/version audit, private scan with no exclusions/waivers and full old/new maps. Keep every notice/unjudged scope and unrelated failures. Microwave routing/S skips require exact measured zero tracks/vias/zones and absent source schematic, never a zero-conductor claim. No new accepts, authoritative promotion or publication; stop/preserve any real discrepancy. Proof: source-bound actual receipts and hashes.

- [x] 4.5f Prepare the approved external kit-dev-coldfire-xilinx_52131.0.2 refresh on clean core5b0853b718e54f2ce487a2545a3ed44df7bd0f9a: full pinned CAD/active resources, byte-identical approved licence/notices, explicit target10, raw import verbatim and actual record dry/exact confirmation, readonly replay, scoped proof/version audit, private scan with no exclusions/waivers and full old/new maps. Keep every notice/unjudged scope and unrelated failures. Microwave routing/S skips require exact measured zero tracks/vias/zones and absent source schematic, never a zero-conductor claim. No new accepts, authoritative promotion or publication; stop/preserve any real discrepancy. Proof: source-bound actual receipts and hashes.

- [x] 4.5g Prepare the approved external multichannel1.0.2 refresh on clean core5b0853b718e54f2ce487a2545a3ed44df7bd0f9a: full pinned CAD/active resources, byte-identical approved licence/notices, explicit target10, raw import verbatim and actual record dry/exact confirmation, readonly replay, scoped proof/version audit, private scan with no exclusions/waivers and full old/new maps. Keep every notice/unjudged scope and unrelated failures. Microwave routing/S skips require exact measured zero tracks/vias/zones and absent source schematic, never a zero-conductor claim. No new accepts, authoritative promotion or publication; stop/preserve any real discrepancy. Proof: source-bound actual receipts and hashes.

- [x] 4.5h Prepare the approved external pic_programmer1.0.2 refresh on clean core5b0853b718e54f2ce487a2545a3ed44df7bd0f9a: full pinned CAD/active resources, byte-identical approved licence/notices, explicit target10, raw import verbatim and actual record dry/exact confirmation, readonly replay, scoped proof/version audit, private scan with no exclusions/waivers and full old/new maps. Keep every notice/unjudged scope and unrelated failures. Microwave routing/S skips require exact measured zero tracks/vias/zones and absent source schematic, never a zero-conductor claim. No new accepts, authoritative promotion or publication; stop/preserve any real discrepancy. Proof: source-bound actual receipts and hashes.

- [x] 4.5i Prepare the approved external microwave1.0.2 refresh on clean core5b0853b718e54f2ce487a2545a3ed44df7bd0f9a: full pinned CAD/active resources, byte-identical approved licence/notices, explicit target10, raw import verbatim and actual record dry/exact confirmation, readonly replay, scoped proof/version audit, private scan with no exclusions/waivers and full old/new maps. Keep every notice/unjudged scope and unrelated failures. Microwave routing/S skips require exact measured zero tracks/vias/zones and absent source schematic, never a zero-conductor claim. No new accepts, authoritative promotion or publication; stop/preserve any real discrepancy. Proof: source-bound actual receipts and hashes.

  - 2026-11-03 4.5c: actual source5b0853b7 externalcomplex_hierarchy1.0.2, explicit buildtarget10; import/record dry0/exactconfirm0, full proof0/no new accepts or exclusions, readonly replay0/equal, scoped proof/version audit0. All113item bytes private-scan0/no exclusions or waivers. Payload54→108files, notices/skips/unjudged retained exactly in `complex_hierarchy-external-refresh-proof.json`. Authoritative/input hashes and external outside-item files unchanged; whole frame retains15unrelated findings. No publication, human/CI approval or4.5/4.4 closure.

  - 2026-11-03 4.5d: actual source5b0853b7 externalecc831.0.2, explicit buildtarget10; import/record dry0/exactconfirm0, full proof0/no new accepts or exclusions, readonly replay0/equal, scoped proof/version audit0. All32item bytes private-scan0/no exclusions or waivers. Payload20→27files, notices/skips/unjudged retained exactly in `ecc83-external-refresh-proof.json`. Authoritative/input hashes and external outside-item files unchanged; whole frame retains13unrelated findings. No publication, human/CI approval or4.5/4.4 closure.

  - 2026-11-03 4.5e: actual source5b0853b7 externalinterf_u1.0.2, explicit buildtarget10; import/record dry0/exactconfirm0, full proof0/no new accepts or exclusions, readonly replay0/equal, scoped proof/version audit0. All55item bytes private-scan0/no exclusions or waivers. Payload26→50files, notices/skips/unjudged retained exactly in `interf_u-external-refresh-proof.json`. Authoritative/input hashes and external outside-item files unchanged; whole frame retains11unrelated findings. No publication, human/CI approval or4.5/4.4 closure.

  - 2026-11-03 4.5f: actual source5b0853b7 externalkit-dev-coldfire-xilinx_52131.0.2, explicit buildtarget10; import/record dry0/exactconfirm0, full proof0/no new accepts or exclusions, readonly replay0/equal, scoped proof/version audit0. All208item bytes private-scan0/no exclusions or waivers. Payload108→203files, notices/skips/unjudged retained exactly in `kit-dev-coldfire-xilinx_5213-external-refresh-proof.json`. Authoritative/input hashes and external outside-item files unchanged; whole frame retains9unrelated findings. No publication, human/CI approval or4.5/4.4 closure.

  - 2026-11-03 4.5g: actual source5b0853b7 externalmultichannel1.0.2, explicit buildtarget10; import/record dry0/exactconfirm0, full proof0/no new accepts or exclusions, readonly replay0/equal, scoped proof/version audit0. All95item bytes private-scan0/no exclusions or waivers. Payload46→90files, notices/skips/unjudged retained exactly in `multichannel-external-refresh-proof.json`. Authoritative/input hashes and external outside-item files unchanged; whole frame retains7unrelated findings. No publication, human/CI approval or4.5/4.4 closure.

  - 2026-11-03 4.5h: actual source5b0853b7 externalpic_programmer1.0.2, explicit buildtarget10; import/record dry0/exactconfirm0, full proof0/no new accepts or exclusions, readonly replay0/equal, scoped proof/version audit0. All63item bytes private-scan0/no exclusions or waivers. Payload65→58files, notices/skips/unjudged retained exactly in `pic_programmer-external-refresh-proof.json`. Authoritative/input hashes and external outside-item files unchanged; whole frame retains5unrelated findings. No publication, human/CI approval or4.5/4.4 closure.

  - 2026-11-03 4.5i: actual source5b0853b7 externalmicrowave1.0.2, explicit buildtarget10; import/record dry0/exactconfirm0, full proof0/no new accepts or exclusions, readonly replay0/equal, scoped proof/version audit0. All14item bytes private-scan0/no exclusions or waivers. Payload8→9files, notices/skips/unjudged retained exactly in `microwave-external-refresh-proof.json`. Authoritative/input hashes and external outside-item files unchanged; whole frame retains2unrelated findings. No publication, human/CI approval or4.5/4.4 closure.

## 5. Closing

- [x] 5.1 Docs: `docs/library-repo.md` (repository, kinds, families, provenance, licences, CI, releases, gallery, `get`, cache, lock, use statement), `get` and the `library` verbs and the four codes in `docs/cli-contract.md`, links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`; `uv run pytest tests/consistency -q`.
  Done 2026-10-30: `docs/library-repo.md`, `## get` and "Library repository verbs" plus the four codes in `docs/cli-contract.md`, a row in `docs/index.md`. Proof passed (74 passed; consistency 638 passed).
- [x] 5.2 Agent guide (AGENTS.md rule 6): tested lines for `fenolite get`, `fenolite get --locked`, `fenolite get --search`, the `library` verbs and the four codes, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
  Done 2026-10-30: page `footprints` gains "Items from fenolite-library" (`get`, `--search`, `--locked`, `--status`, the board form and the four `library` verbs, tested lines); page `recovery` names `FEN-3021`, `FEN-4003`, `FEN-6004`, `FEN-6006` (trimmed to 11995 bytes); `HOME` maps `get` to `footprints`; `tools/gen_agent_guide.py` run (skill folder 316535 bytes). Proof passed (76 passed).
- [x] 5.3 Example `examples/library-devices/`: a design using one authored demo device got from a local release folder, with its lock, offline. Proof: `uv run pytest tests/unit/test_examples.py -k library_devices -q`.
  Open 2026-10-30: waits for c0266 (reading `fenolite_library/devices` as project records is not merged), so a design cannot use a got device yet; committing a vendored folder in `examples/` would also need the residue exemption. The offline flow (release folder, `get`, lock, `--locked --offline`) is covered by tests/unit/cli/test_get_lock.py.
  Decided 2026-11-01: reuse the existing authored c0266 worked example rather than duplicate its payload
  under `library-get`. It supplies the local deterministic release, lock and vendored dependency closure;
  its proof blocks connections/subprocesses during restore and compares every native build byte against
  the same authored records read directly. The all-zero release commit is a fixture, not publication,
  and the illustrative records remain UNVERIFIED.
  Proof passed on the combined source, 2026-11-01: 3 passed, 32 deselected. This closes only the
  existing worked-example task; external release/workflow and exact-head CI tasks remain open.
- [x] 5.4 Run `uv run pytest tests/residue -q` and update evidence labels of the new behaviours. Proof: `uv run pytest tests/residue tests/unit/test_inferred_hypotheses.py -q`.
  Done 2026-10-30: `tests/residue` passed (91 passed with tests/corpus/test_manifest.py); `H-G-LIBRARY-GET` and `H-G-LIBRARY-REPLAY` measured and kept `INFERRED`.
- [x] 5.5 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
  Done 2026-10-30: `dev` is at `0.7.0.dev0`; the entry is under `## [Unreleased]`. Proof passed (8 passed).
- [ ] 5.6 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit, KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
  Open 2026-10-30: the first `make check-fast` (2 workers) was stopped at 98% by the session's time limit with 10 failures; a rerun of its test set listed them (`get` hid `--frozen` from help; the demo fixture under `tests/data/library/` was read by the catalog tests, so it moved to `tests/data/library_repo/demo/`; the lock section list and paged-command list gained `library` and `get`). All fixed: the ten tests and 1172 affected tests pass, ruff, format and pyright clean. The second `make check-fast` was at 77% with no failure when the session closed: not reported as passed. Next: run `make check-fast`, publish the batch, confirm CI.

  Integration validation 2026-10-31: the complete check-fast finished with exit 2 (17712 passed, 49 skipped, 2 failed; 1382.87 s). No interruption occurred. Fixed duplicate proposed/measured hypothesis rows by retaining the measured rows, and updated the blocks-order guard to require blocks after pins and before library. Focused hypothesis/register and block-lock proof passed (53 tests, exit 0). The next full batch gate remains required before push; 0.1 and 5.6 stay open.

Integration proof 2026-10-31: `make check-fast` completed with exit 0 (17724 passed, 49 skipped); strict c0279 validation passed. Task 0.1 is complete. Task 5.6 remains open pending exact-head CI; external and dependent tasks remain open.

Integration history 2026-10-31: remote `135b4ab1` also records successful check-fast on `7a120e8d` (17708 passed, 53 skipped), with publication initially blocked by HTTP 403. Those historical results are retained here; the newer local proof above and renewed exact-head CI govern closure.

2026-10-31: task 3.1 completed in the separate library repository on `cac/c0279-library-setup`, commit `d7e887d7d6a171350bf460a8dd117d58091e749d`. Root metadata, the CC0 own-files licence, contribution rules and the identical shipped licence list are present. `library audit` exits 0, also with `--base first-boards`; `test_licences.py -k shipped_copy` passed. Board metadata 1.0.1 migrates the historical drawn-unavailable reason already stated in each accepted schematic difference; no new fidelity proof is claimed. Publication, workflows and renewed replay/proof remain pending; no release or pull request was created.

Dependency note 2026-10-31: tasks 3.2 and 4.4 prescribe installing a pinned released Fenolite in the external workflows. The current integration is 0.7.0.dev0 and those commands are not in the published 0.6 release; c0262, c0270 and c0273 also remain unimplemented. No release or tag is created under the current maintainer instruction, and no unavailable checks are represented as passing. Tasks 3.2, 3.3, 4.4, 4.5 and 5.3 stay open until their dependencies and actual CI proofs are available.

Integration gate 2026-10-31: the complete `make check-fast` on the reconciled integration (runtime and tests of `59aeafb7`) finished with exit 0. Ruff, generated-file checks, formatting, pyright, residue and all selected unit/consistency tests passed. Exact pushed-head CI remains required before closure.

## 6. Cross-platform integration corrections

- [x] 6.1 Override ambient Git newline conversion for fetched library and replay checkouts; prove pinned LF bytes survive a host configured for CRLF. Proof: `uv run pytest tests/unit/cli/test_get.py::test_from_a_checkout_and_a_file_git_url tests/unit/library/test_replay.py::test_replay_fetches_the_pinned_commit -q`.
- [x] 6.2 Make cache-plan path assertions portable without weakening the no-request proof. Proof: `uv run pytest tests/unit/cli/test_get_cache.py -q`.

- [x] 6.3 `library replay --upstream DIR` copies the given checkout with links kept as links, as a git checkout has them; a dangling link (KiCad's own `qa/tests/resources`) ended the replay with FEN-1001. Proof: `uv run pytest tests/unit/library/test_replay.py -q`.

  2026-11-04: found by running `tools/library_bench.py` (task 4.4) on the library's microwave board: the replay with `--upstream` exited 1 with FEN-1001 on the dangling `qa/tests/resources` link of KiCad `97acc80c`. The new regression test fails without `symlinks=True` and passes with it (8 passed in the file); the same board then replayed equal and its proof passed. The library's `bench.yml` now lets `replay` fetch the pinned commit itself, so its pinned core does not need this fix.

2026-10-31: task 6.1 reproduces both Windows failures on the local host with an isolated CRLF Git configuration (2 failed before the fix). Explicit per-command `core.autocrlf=false` and `core.eol=lf` made both regressions pass. No global Git configuration changes; repository attributes remain respected. Strict validation and focused lint passed.

2026-10-31: task 6.2 passed (9 tests). The index-cache assertion compares native path components; assertions of zero requests, no cache writes, expected digest and byte size remain unchanged.

Integration proof 2026-11-01: the complete quick gate of corrected source `9d1b8667` finished with exit 0 (17725 passed, 49 skipped; 1740.11 s). All five touched changes validated strictly without warnings. Exact-head CI remains required; interrupted earlier gates are not counted.


Local authoritative integration of4.5a–i —2026-11-03: the nine exact sealed
1.0.2 candidate subtrees are now integrated locally into fenolite-library,
996files/951payloads. Complete before/after maps and retired source trees are
preserved; all original terms,11other items including4LibrePCB, sources, public
pin and Royal bytes are unchanged. Nine real integrated --proof/--base item
audits pass; one combined root audit drops21→2unchanged Royal metadata errors.
Royal's two actualL7 failures remain unresolved and are not cleared by this
audit. Eight historic proofs equal1–8/S; Microwave retains its recorded
L5no-copper/Sno-schematic scopes. No native/replay rerun or new acceptance.
47focused tests and complete private-gated library residue pass. Library
receipt: docs/nine-board-local-integration-20261103.json. Parent4.5, required
exact-source CI, public pin, PR/release/Pages remain open; no publication.

Root reviewed all1018A/M/D actions against HEAD23deaee and current files by
SHA256/size, then committed the nine complete sealed item trees locally as
library8b38b308411b9c7e36d44f65625f648798910378 with maintainer DCO. Private staged scan
0hits/983present files/private gateON. Three whitespace-only warnings belong
to OpenAir's byte-identical upstream native DRU and were preserved explicitly;
all other staged paths pass whitespace checks. Library worktree is clean.
No library push, pin, CI or release is claimed by this local commit.
