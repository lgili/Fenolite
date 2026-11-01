## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`fenolite-component-catalog`, `cli-contract`, and `fenolite-library` once c0279 is archived) and the changes it builds on (c0279 phase A, c0259, c0262; c0260, c0261, c0254). Write under this task, with the date and the base commit:
  - c0279's item, provenance and lock-section names as implemented, and whether `fenolite get` copies into `fenolite_library/<kind folder>/`;
  - c0259's record module and `load_tree` rules, and c0262's command and job names used by the library CI;
  - which open change holds a delta of "Build resolves built-in definitions" (regenerate the MODIFIED block from the living text);
  - the final verb list of `fenolite library` (c0260, c0261, c0262, c0264, c0265, c0279), so `seed` joins it;
  - the maintainer's answers to the open questions of `design.md`;
  - the next free `S-` numbers (the LibrePCB format documentation and the LibrePCB library).

  Proof: `openspec validate c0266-device-packs --strict`; `make check-fast`.

Entry facts (2026-11-01; initial base 8dea6432, resolved prerequisite 7a2f6746): `openspec list` and the named living specs/changes read. c0279 uses `fenolite.library-item.v0` (`item.json`), `fenolite.provenance.v0` (`PROVENANCE.json`), `[library.items]`; `get` copies into `fenolite_library/<kind folder>/<namespace>/<name>/`. c0259 uses `catalog/records.py:load_tree`, recursive TOML, ignores JSON and families, excludes `VERSIONS.toml` and optional proposed paths, and rejects duplicate kind/id. c0262 provides `library check` and `library review`; external jobs remain `records`, `regenerate`, `versions`, `origin`, `renders`. c0259 holds the other open catalog MODIFIED delta; c0266 retained the complete living built-in requirement and added only vendored precedence/origins. Final actions are `symbol`, `generate`, `check`, `review`, `import`, `propose`, `seed`, `audit`, `replay`, `release`, `gallery`; c0265 supplies propose, legacy reserved fetch is replaced by get. All four recommended design decisions accepted 2026-11-01. S-1090..1097 reserved/actually read for public format/library facts. Full entry `make check-fast` remains root-owned and unclaimed.

## 1. Vendored records in the core

- [x] 1.1 `src/fenolite/catalog/vendored.py`: `load_vendored` over `fenolite_library/symbols`, `fenolite_library/footprints` and `fenolite_library/devices`, pairing records with their `item.json`. Author the vendored fixture `tests/data/library/project/`, each file with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/catalog/test_vendored.py -q`.
- [x] 1.2 Runner precedence, `library.overrides-item`, `library.item-conflict`, the origin `library` in the build (scenarios "Authored record wins", "Two vendored items, one id", "Unused vendored item changes nothing", "Vendored definition resolved offline"). Proof: `uv run pytest tests/unit/cli/test_build_vendored.py tests/unit/lens -k vendored -q`.
- [x] 1.3 Offline guard and the `get` hint for library ids (scenarios "Build with vendored records and no network", "Hint for a library id"). Register `H-G-DEVICE-PACKS` with its new statement (vendored records from a local release resolve the same records and build bytes as the library tree, offline). Proof: `uv run pytest tests/unit/cli/test_build_vendored.py -k "offline or hint" tests/unit/test_hypotheses_register.py -q`.
- [x] 1.4 c0254 picks of vendored rows record `catalog = "library:device/<id>@<version>"`. Proof: `uv run pytest tests/unit/cli/test_pick.py -k library -q`.
- [x] 1.5 Combined c0270/c0273 integration: exercise a block using a real fetched device, literal pins/origins/frozen build, missing-item preflight before code execution, single-run upgrade and source-bound replay, private usage/instantiate with authored overrides, conflict findings and private-copy link preservation. Teach the private device context and preserve original source bytes. Proof: `uv run pytest tests/unit/cli/test_block_device_integration.py -q`.

## 2. Device kinds in the library audit

- [x] 2.1 Device-kind rules in `fenolite library audit` (c0279): record id and licence equal to the item's, reserved namespace, `sources.toml` ids, `shippable()` (scenarios "Device item read", "Reserved namespace", "Unregistered source", "Version step missing"). Proof: `uv run pytest tests/unit/library/test_audit_devices.py -q`.
- [x] 2.2 External record checks use the validated D-id register loader: registered sources pass, unregistered ids remain errors even when mentioned in comments or the register is absent, and malformed source rows are bad input. Preserve shipped S-id checks. Proof: `uv run pytest tests/unit/cli/test_library_check.py -k external_sources -q`.
  Integration proof 2026-11-01: the registered/malformed cases fail before the fix; after validated
  dispatch, all four source scenarios and 96 related record/review/audit/import tests pass. No waiver
  or relaxed source-row parsing is used.
  A missing-register follow-up reproduced unchecked D ids exiting 0; after the guard, all five source
  scenarios pass. S-id records retain the existing optional-register behavior.
  External follow-up on clean core `04a9d07e`: three original UNVERIFIED D-0003 item records pass with
  no waived findings; reviewed sheet-plan confirmation produces six HTML sheets without acceptance
  or evidence promotion. Explicit regeneration and offline get/three pins/vendored/direct/frozen
  build and native-definition/board/connectivity comparisons pass with sockets/processes denied.
  These are local authored-item proofs; actual external CI and release requirements remain open.

## 3. LibrePCB seed

- [x] 3.1 `docs/formats/librepcb/library.md` from public LibrePCB documentation only (elements, files, units, axes, rotations, signal roles), each fact with source and evidence label; no parser code read. Proof: `uv run pytest tests/unit/test_provenance.py -q`.
- [x] 3.2 `src/fenolite/backends/librepcb/`: its tokenizer and element reader written from that page; authored fixtures under `tests/data/librepcb/demo/`. Proof: `uv run pytest tests/unit/backends/librepcb -q`; `uv run pytest tests/unit/test_import_graph.py -q`.
- [x] 3.3 `library seed`: licence gate, commit check, mapping to items and records, item files and `PROVENANCE.json`, ids, skips, plan and confirm, no overwrite of reviewed records, the `seed` verb and its `capabilities` entry (scenarios "Seed items carry their origin", "Not a CC0 library", "Commit mismatch", "Same bytes twice", "Custom pad outline skipped", "Reviewed record kept", "Board path form unchanged"). Proof: `uv run pytest tests/unit/cli/test_library_seed.py tests/unit/cli/test_library_cmd.py -q`.

## 4. The library repository

- [ ] 4.1 In `lgili/fenolite-library`: the `sources.toml`, the device-kind jobs `records`, `regenerate`, `versions`, `origin` and `renders` in `check.yml`, the seed risk in the README, and `reviews/`. Proof: the library's first pull request with device items green.
  Authorized local follow-up (2026-11-01): external library commit
  `2ce4d2f0dab580e7ea2f78e3bd48716352ad9918` adds D-0001/D-0002, `reviews/README`, seed-risk and
  contribution documentation, and the named workflow infrastructure. Source-register and check/seed
  capability guards passed locally with clean core `2c9afd54`. That infrastructure commit added no
  device, symbol or footprint items, LibrePCB seed, pull request or actual CI run. Subsequent authored
  D-0003 item proofs are recorded under 2.2; this task's actual CI proof remains open.
- [ ] 4.2 First device items (authored `FenoliteDevices` items and, after review of the run, a seeded LibrePCB set), released by c0279's release job. Proof: `fenolite library audit . --json` exits 0 in the library on the release tag.

## 5. Closing

- [x] 5.1 Docs: `docs/library-devices.md` (kinds, authored and seeded items, vendored records, precedence, origin labels, lock pins, offline use, seed and its risk), `library seed` in `docs/cli-contract.md`, links from `docs/index.md`, `docs/library-records.md` and `docs/library-repo.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
- [x] 5.2 Agent guide: tested lines in focused `device-packs.md` (parts/recovery were full; coordinated 2026-11-01) for `fenolite get device <id>` with vendored records and for `fenolite library seed`, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [x] 5.3 Example `examples/library-devices/` (a design using one demo device vendored from a local release folder, its lock, offline). Proof: `uv run pytest tests/unit/test_examples.py -k library_devices tests/unit/cli/test_hermetic_examples.py -q`.
- [x] 5.4 Run `uv run pytest tests/residue -q` and update evidence labels. Proof: `uv run pytest tests/residue tests/unit/test_inferred_hypotheses.py -q`.
- [x] 5.5 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.6 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit, KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.


Local proof record (2026-11-01): changed-source lint/format and pyright pass; strict c0266 validates.
Task proofs are logged in the coordinator scratch folder `fenolite-validation/c0266-device-packs`: catalog pairing,
build/lens precedence and byte equality, offline/hint, version-bound picks and whole-family items, audit
identity/source/shippability, public provenance/import graph, bounded reader and seed scenarios, docs,
agent pages, local release/get/frozen build, residue/inferred labels and changelog all passed. Authored
LibrePCB fixtures establish only the documented subset; no upstream oracle or live-library seed is claimed.
All committed fixtures, including licence placeholders/declarations, are original Fenolite test data.
The S-1097 public legal-text hash stays pinned; a test-only expected hash enables authored positives and
an explicit test proves the placeholder is rejected by unchanged production defaults. No third-party
CAD, parser or licence payload is committed. No new FEN codes duplicate FEN-6004 or FEN-3021.

Integration: c0265 feature 8b61fe84 is merged after prerequisite 7a2f6746. Proposal publication additionally
requires current human review and the exact `proposal_outputs_current` canonical/raw output verifier.
Real proposals accept review metadata and refuse a subsequent native/proposal byte edit in the focused
proof. The CLI retains both propose and seed, and both focused guide topics stay within existing budgets.

Open 0.1/5.6: root owns the serialized full `make check-fast`, publication and exact-head CI. Neither was
run or claimed here. Local external infrastructure is recorded under 4.1; tasks 4.1/4.2 still require
device items, digest-bound human reviews, actual CI, an audited initial release and a real release tag.
No external PR/tag/release is created. Current public format documentation
leaves newer versions and several field/axis facts unverified; external seed validation remains required.

Authored-fixture correction (2026-11-01): the stricter fixture policy takes precedence. Removed all copied
full CC0 legal text from the LibrePCB fixture and example source/vendored items, regenerated the local
release and lock, and replaced it with original declarations/placeholders. Production S-1097 hashes and
seed validation are unchanged. Positive seed/audit unit paths inject only an authored expected hash; a
separate unpatched production-default scenario rejects it with FEN-3004. Real legal-text and upstream
compatibility proofs remain external; this correction grants no licence approval to upstream material.

Local integration candidate (2026-11-01): merged authored-only library head `2c9afd54` with catalog/CI
candidate `171b14b110c594a731fc123ebe007bdb6e0bab6b`, using common base `8d74a798` for VERSIONS.
All 159 CC0 licences, 80 existing PATCH versions and 121 explicit waiver entries are preserved; output
and interface digests stay unchanged and the regenerated catalog remains 1.0.1. Both migration helpers
and import/proposal/review/body fields remain available. Guide command homes and teaching assertions
are unioned; regenerated start is 11,796 bytes and 152 lines. Focused compatibility: 374 passed,
two skips; migration/vendor/provenance/manifest/portability: 190 passed; guide/source/residue: 213 passed,
five corpus skips. Source types, lint, formatting, residue and generated-file checks pass. The shipped
library check passes all 159 records with only the existing 150 waived informational findings.
This combines local proofs only. Root still owns the full local gate, publication and required CI on
the exact pushed head. External LibrePCB/legal-text validation and the separate data repository work
remain open as recorded above; no external fixture, release, tag or evidence promotion was added.

Combined block/library proof (2026-11-01): candidates `5d8afc2f` and `7645b893` retain common base
`171b14b1`. The real fetched-block/device regression has 15 passing cases, including missing-item
preflight, unchanged item pins, single-run upgrades, replay invalidation, private device contexts,
authored precedence, inactive proposals and conflict findings. Build/block/check compatibility passed
401 tests (two empty shipped-block skips); final affected proofs passed 156 (the same two skips).
Library/import/proposal/catalog/guide compatibility passed 732 (one absent external library checkout
and 19 KiCad-10 skips).
Command/docs/residue consistency passed 602 (41 mutating-command and five unavailable-corpus skips).
The shipped library check has 159 records, no errors or warnings and 150 existing waived infos.
Catalog bytes equal the incoming library candidate. All four generators reproduce; guide start is
11,993 bytes/154 lines, within the unchanged budget. Static source checks and residue pass. This
candidate excludes the separately owned c0282 geometry and later CI census changes. Root still owns
the complete local gate and exact-head CI; no external publication or human review is claimed.
