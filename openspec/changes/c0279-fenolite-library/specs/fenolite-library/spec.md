## ADDED Requirements

### Requirement: Library repository layout
The repository `lgili/fenolite-library` SHALL hold every third-party-derived item in `<kind>/<family>/<id path>/`, with the kinds `symbols`, `footprints`, `devices`, `blocks` and `boards`, the family given by the item's SPDX id, and the id path the id with `:` replaced by `/`. An id MUST be unique within its kind. `fenolite library audit` SHALL report `library.family-mismatch` and `library.duplicate-id` as errors.

#### Scenario: Item in the wrong family
- **GIVEN** the authored library fixture `tests/data/library_repo/demo/` with a `CC-BY-SA-4.0` footprint moved under `footprints/cc0/`
- **WHEN** `fenolite library audit tests/data/library_repo/demo --json` runs
- **THEN** it exits 5 and `issues` holds `library.family-mismatch` naming the item and the family `cc-by-sa`

#### Scenario: One id in two families
- **GIVEN** the fixture with the device `Demo:EXB` under both `devices/cc0/` and `devices/mit/`
- **WHEN** the audit runs
- **THEN** it exits 5 with `library.duplicate-id` naming both folders

### Requirement: Library item manifest
Each item folder SHALL hold `item.json` (schema `fenolite.library-item.v0`) with `kind`, `id`, `version` (semantic), `title`, `summary`, `spdx`, `tags`, `files`, `depends` (kind, id, exact version) and `executes`, plus `LICENSE`, `NOTICE` and `PROVENANCE.json`. A file outside `files` and the fixed files MUST give `library.item-extra-file`; a `depends` cycle or unknown target MUST give `library.provenance-invalid`.

#### Scenario: Unlisted file
- **GIVEN** a fixture device item holding `notes.txt` not listed in `files`
- **WHEN** the audit runs on it
- **THEN** it exits 5 with `library.item-extra-file` naming `notes.txt`

#### Scenario: Block items execute
- **GIVEN** a fixture block item whose `item.json` says `"executes": false`
- **WHEN** the audit runs
- **THEN** it reports `library.provenance-invalid` stating that block and board items execute

### Requirement: Provenance record
`PROVENANCE.json` SHALL follow `fenolite.provenance.v0` in canonical JSON. A `converted` item MUST record the upstream URL, 40-hex commit, authors, copyright lines, SPDX id, a dated modification notice, tool versions, replayable steps, the outputs tree digest, c0275's record as `import` and, for a board, c0278's `fidelity`; an `authored` one records `sources`; a `seeded` one the source library and commit. A violation MUST give `library.provenance-invalid`.

#### Scenario: Converted item without a commit
- **GIVEN** a fixture board item whose `upstream.commit` is `main`
- **WHEN** the audit runs
- **THEN** it exits 5 with `library.provenance-invalid` naming `upstream.commit`

#### Scenario: Provenance and manifest disagree
- **GIVEN** a fixture item whose `PROVENANCE.json` says `MIT` and whose `item.json` says `CC0-1.0`
- **WHEN** the audit runs
- **THEN** it reports `library.provenance-invalid` naming both values

### Requirement: Licence allow-list
An item's `spdx` SHALL be one id of the closed allow-list in `licences.toml`: `CC0-1.0`, `CC-BY-3.0`, `CC-BY-4.0`, `CC-BY-SA-2.5`, `CC-BY-SA-3.0`, `CC-BY-SA-4.0`, `CERN-OHL-1.2`, `CERN-OHL-P-2.0`, `CERN-OHL-W-2.0`, `CERN-OHL-S-2.0`, `MIT`, `BSD-2-Clause`, `BSD-3-Clause`, `Apache-2.0`, `SHL-0.5`, `SHL-0.51`, `SHL-2.0`, `SHL-2.1`, `GPL-2.0-or-later`, `GPL-3.0-only`, `GPL-3.0-or-later` or `TAPR-OHL-1.0`.

#### Scenario: Allowed id accepted
- **GIVEN** a fixture board item with `spdx = "CERN-OHL-S-2.0"` in `boards/cern-ohl-s/` and a matching licence text
- **WHEN** the audit runs
- **THEN** it reports no licence issue for that item

### Requirement: Licence deny reasons
The audit SHALL refuse with `library.licence-denied`, naming the reason, an id with `-NC` or `-ND`, `NOASSERTION`, `NONE`, an empty licence, `LicenseRef-*`, any id outside the allow-list, an upstream URL on `easyeda.com`, `oshwlab.com`, `oshwhub.com` or `lceda.cn`, and an item marked `vendor-bundled`.

#### Scenario: Non-commercial licence refused
- **GIVEN** a fixture board item with `spdx = "CC-BY-NC-SA-4.0"`
- **WHEN** the audit runs
- **THEN** it exits 5 with `library.licence-denied` and the reason `non-commercial`

#### Scenario: Platform-restricted origin refused
- **GIVEN** a fixture item with `spdx = "CC-BY-4.0"` and an upstream URL on `oshwlab.com`
- **WHEN** the audit runs
- **THEN** it exits 5 with `library.licence-denied` and the reason `platform-restricted`

### Requirement: Licence text and notices
An item's `LICENSE`, normalised (lower case, whitespace collapsed), SHALL match a digest listed for its SPDX id, or `PROVENANCE.json` MUST hold `licence_review`; else `library.licence-text`. `NOTICE` SHALL start with the dated modification notice of `PROVENANCE.json`, followed by the upstream notices; else `library.notice-missing`.

#### Scenario: Notice without modification line
- **GIVEN** a fixture converted item whose `NOTICE` holds only the upstream notice
- **WHEN** the audit runs
- **THEN** it exits 5 with `library.notice-missing` naming the item

### Requirement: Replay from the pinned upstream
`fenolite library replay ITEM` SHALL fetch the upstream at the recorded commit (or archive with its digest) into a temporary folder. It SHALL check the input digests and run the recorded steps with the recorded versions of `fenolite` and `kicad-cli`, refusing any other tool. It compares the tree digest of `out/` with `outputs_tree` and the payload, reporting `library.replay-differs` on a difference, and writes nothing into the repository.

#### Scenario: Replay reproduces an authored conversion
- **GIVEN** the authored fixture upstream `tests/data/library/upstream/blink/` and a fixture board item converted from it with recorded steps
- **WHEN** `fenolite library replay <item> --upstream tests/data/library/upstream/blink --json` runs
- **THEN** it exits 0 and `result.outputs_tree` equals the item's `outputs_tree`

#### Scenario: Unknown tool refused
- **GIVEN** a fixture item whose step names the tool `sh`
- **WHEN** the replay runs
- **THEN** it exits 3 with `FEN-3004` naming the step, and runs nothing

### Requirement: Board proof gate
The library's CI SHALL run c0278's `verify-source` on each changed board with the item's `fidelity.accepted` entries as exclusions. Every level MUST be `equal` or `accepted` and equal to `fidelity.proof.levels`; otherwise it SHALL give `library.proof-failed` naming the level and difference. The derived result SHALL be `pass`, `pass-with-accepted` or `fail`.

#### Scenario: Accepted difference passes
- **GIVEN** a fixture proof report with one level-7 difference and a matching `fidelity.accepted` entry
- **WHEN** `uv run pytest tests/unit/library/test_proof_gate.py -k accepted` runs
- **THEN** the gate result is `pass-with-accepted`

#### Scenario: New difference fails
- **GIVEN** the same report with a second level-7 difference that no entry matches
- **WHEN** the gate is evaluated
- **THEN** it gives `library.proof-failed` naming the new difference

### Requirement: Benchmark runs
On a weekly schedule and on each Fenolite release, the library's CI SHALL replay every board with the newest Fenolite, rerun every proof, publish a table of boards, levels, durations and differences, and open one issue per newly failing board, without blocking merges.

#### Scenario: Benchmark table
- **GIVEN** two fixture boards, one of whose proofs fails under the tested version
- **WHEN** `uv run pytest tests/unit/library/test_bench_table.py` builds the table with the documented recipe
- **THEN** the table lists both boards with their levels, and only the failing one is marked for an issue

### Requirement: Library releases
A tag `v<version>` of the library SHALL publish `index.json` (`fenolite.library-index.v0`, one row per item with kind, id, version, SPDX, family, reciprocal, path, tree, bytes, archive, depends, executes, evidence and proof), shard archives per kind and family, one archive per board, and `SHA256SUMS`. `fenolite library release` SHALL build them byte-reproducibly.

#### Scenario: Release is reproducible
- **GIVEN** the authored library fixture
- **WHEN** `fenolite library release tests/data/library_repo/demo --version 1.0.0 --out` is confirmed into two empty folders
- **THEN** both folders hold identical bytes, and each index row's `tree` equals the tree digest of its item folder

### Requirement: Gallery with attribution
`fenolite library gallery` SHALL write a static site of images rendered by Fenolite only. Every card MUST show the title, the authors, the upstream link, the SPDX id, the Fenolite version, "Not endorsed by the authors" (for converted items), the proof result and the `fenolite get` command. An item with `trademarks.restricted` MUST NOT appear.

#### Scenario: Card attribution
- **GIVEN** the release fixture with one converted board licensed `CERN-OHL-S-2.0`
- **WHEN** the gallery is planned with `--dry-run --json`
- **THEN** the planned card page of that board holds the attribution line with its authors, upstream link and `CERN-OHL-S-2.0`

#### Scenario: Restricted marks hidden
- **GIVEN** a fixture board with `trademarks.restricted = true`
- **WHEN** the gallery is planned
- **THEN** no card or image of that board is planned

### Requirement: Library use statement
The library's README SHALL state that each directory keeps its upstream licence, that the repository's own licence does not cover items, that items are test and benchmark inputs and starting points for users, and that no item is used to train a machine-learning model unless a separate public decision says otherwise. `fenolite library audit` SHALL check these statements.

#### Scenario: README without the use statement
- **GIVEN** the library fixture whose README lacks the training sentence
- **WHEN** the audit runs at the root
- **THEN** it exits 5 with `library.provenance-invalid` naming `README.md`
