# fenolite-library Specification

## Purpose
TBD - created by archiving change c0281-import-copy-fidelity. Update Purpose after archive.
## Requirements
### Requirement: Skipped levels in the proof gate
The proof gate SHALL accept a level `skipped` only when `fidelity.proof.skipped` gives its reason and the reason is not `build-failed`; the derived result is unchanged by a skipped level and MUST list the skipped levels with their reasons. Until c0278's level S runs on drawn imports, `S` skipped with `drawn-unavailable` passes.

#### Scenario: Level S skipped with a reason
- **GIVEN** a fixture proof whose levels are `equal` and whose `S` is `skipped` with `fidelity.proof.skipped.S` `drawn-unavailable`
- **WHEN** `uv run pytest tests/unit/library/test_proof_gate.py -k skipped` runs
- **THEN** the gate result is `pass` and lists `S: drawn-unavailable`; without the reason, or with `build-failed`, it is `fail`

### Requirement: Replayable conversion steps
A step of `conversion.steps` SHALL NOT hold `--plan`: a plan id hashes its working folder and cannot replay elsewhere. A writing step MUST be recorded with `--confirm` alone. `library audit` MUST give `library.provenance-invalid` for a step with `--plan`; `replay` runs each step as recorded.

#### Scenario: Step with a plan id
- **GIVEN** a fixture board item whose second step ends with `--confirm --plan 0123456789abcdef`
- **WHEN** `uv run pytest tests/unit/library/test_audit.py -k plan_step` runs
- **THEN** the audit reports `library.provenance-invalid` naming the step; with `--confirm` alone it passes, and its replay in a fresh folder gives the recorded `outputs_tree`

### Requirement: Preserve approved licence registry entries across repositories
The shipped registry SHALL retain all previously approved text digests and
match the library registry after incorporating documented maintainer approvals.

#### Scenario: Synchronize the reviewed registry union
- **WHEN** both old registries and new text approvals are reconciled
- **THEN** every old approved digest remains allowed
- **AND** the shipped registry equals the library registry without relaxing any other licence rule

### Requirement: Conservative LibrePCB legacy metadata and pads
The bounded 0.1 seed SHALL select a unique unlocalized name alongside well-formed unique locale alternatives. It SHALL accept a scalar drill only when zero and unaccompanied by a hole. An absent package_pad MAY use the pad UUID only when declared by the package. Ambiguous names, unknown references and nonzero or malformed legacy drills SHALL remain explicit refusals.

#### Scenario: Localized metadata preserves the default
- **GIVEN** an authored element with one default name and distinct valid localized names
- **WHEN** it is read
- **THEN** its default name is kept and no translated text replaces it

#### Scenario: Ambiguous defaults refuse
- **WHEN** two unlocalized names or duplicate locale identities are present
- **THEN** the element is explicitly refused

#### Scenario: Legacy surface pad binds safely
- **GIVEN** a zero scalar drill and pad UUID declared in its package
- **WHEN** the footprint is seeded
- **THEN** its exact surface pad geometry and package mapping are retained

#### Scenario: Drill information cannot disappear
- **WHEN** a scalar drill is nonzero, malformed or coexists with a hole
- **THEN** the footprint is refused without a fabricated surface pad

#### Scenario: Declared reference prefix remains visible
- **GIVEN** an authored component declaring a valid prefix
- **WHEN** symbol and device records are seeded
- **THEN** both keep that prefix; a missing field alone uses U and an invalid field is refused

### Requirement: Numeric internal function normalization is reversible
The seed converter SHALL normalize an ASCII numeric internal function name to
Pin_<original>, without changing the symbol's visible pin name, pin number,
UUID relationship or electrical mapping. It SHALL refuse identifier collisions
and other invalid names. It SHALL emit library.seed-function-normalized and
record the ordered UUID/original/normalized map in the existing dated provenance
modification_notice and NOTICE. Geometry and evidence SHALL remain unchanged.

#### Scenario: Numeric resistor functions
- **WHEN** authored signals named 1 and 2 map to two symbol pins and package pads
- **THEN** device functions are Pin_1 and Pin_2, symbol names/numbers remain 1/2,
  and replay preserves the same partition and source-bound normalization map

#### Scenario: Legal identifier collision
- **WHEN** signals 1 and Pin_1 would share a normalized identifier
- **THEN** the device is refused explicitly and no device is planned

### Requirement: Signed cardinal pin angles retain exact orientation
The seed converter SHALL canonicalize only exact cardinal pin rotations modulo
360 degrees, preserve a source-bound map in warning and existing provenance
notice, and refuse noncardinal input without rounding.

#### Scenario: Signed cardinal and near-cardinal
- **WHEN** a source pin has rotation -90deg
- **THEN** it emits270deg with the same native orientation and partition
- **WHEN** it has45deg or -90.0001deg
- **THEN** its component and dependent devices are explicitly refused

### Requirement: Curated artwork is explicit and reproducible
The review draft SHALL retain its immutable raw seed separately and record its
exact source-bound change in existing provenance notice and NOTICE. Only two
resistor graphical pin lengths SHALL change from2,000,000nm to2,032,000nm; pin
anchors/names/numbers, device mappings and physical footprint geometry SHALL
remain unchanged. No checker waiver or source-parser rounding is permitted.

#### Scenario: Reproducible four-item review candidate
- **WHEN** the external recipe runs twice on the same byte-attested raw seed
- **THEN** all candidate file hashes match, complete library check returns exit0 with zero ERROR and all four preferred100mil WARN visible,
  and native before/after partitions match the same expected three nets
- **AND** the generated preview identifies the two changed lengths explicitly
- **AND** human acceptance, integration and release gates remain pending

### Requirement: Device item kinds
A `symbol` item of `fenolite-library` SHALL hold one c0259 `pins` record with `[symbol]`, a `footprint` item one `package` record, and a `device` item one `device` record with its parts, whose `depends` names its symbol and footprint items. Each record's id MUST equal the item id and its `licence` the item's `spdx`, else `library.provenance-invalid`. The namespace `Fenolite` MUST be refused.

#### Scenario: Device item read
- **GIVEN** the authored library fixture `tests/data/library/demo/` with the items `symbol`, `footprint` and `device` `Demo:EXB`
- **WHEN** `fenolite library audit tests/data/library/demo --json` runs
- **THEN** it exits 0 and reports three device-kind items with their records

#### Scenario: Reserved namespace
- **GIVEN** a fixture device item with the id `Fenolite:X`
- **WHEN** the audit runs
- **THEN** it exits 5 with `library.provenance-invalid` naming the namespace `Fenolite`

### Requirement: Authored device items
An authored device-kind item SHALL use `spdx = "CC0-1.0"`, the family `cc0`, and record `sources` naming only `D-` ids of the library's `sources.toml`, whose rows hold `id`, `title`, `url`, `licence`, `retrieved` and `used`. An unregistered id MUST give `FEN-3004` naming the record and the id; a record that `shippable()` rejects MUST give `library.not-shippable`.

#### Scenario: Unregistered source
- **WHEN** a fixture authored record names `D-0099` and `sources.toml` lacks it
- **THEN** the audit fails with `FEN-3004` naming the record and `D-0099`

### Requirement: Device source registers in library checks
`library check` SHALL read an external `fenolite.library-sources.v0` D-id register through the validated device-register loader. Registered D ids MUST pass the source check; unregistered ids MUST produce `library.source-unknown` even when mentioned in comments or the register is missing. Malformed register rows MUST fail with `FEN-3004`. Existing shipped S-id checks SHALL remain available.

#### Scenario: Registered external device sources
- **GIVEN** authored external symbol, footprint and device items citing registered `D-0003`
- **WHEN** `library check` checks their records
- **THEN** source validation passes for all three kinds

#### Scenario: Unregistered external source in a comment
- **GIVEN** the records cite `D-0099`, mentioned only in a source-register comment
- **WHEN** `library check` checks them
- **THEN** it exits 5 with `library.source-unknown` naming `D-0099`

#### Scenario: Missing external source register
- **GIVEN** authored item records cite D ids but have no source register
- **WHEN** `library check` checks them
- **THEN** it exits 5 with `library.source-unknown` rather than accepting unchecked D ids

#### Scenario: Malformed external source row
- **GIVEN** `D-0003` lacks its required `used` field
- **WHEN** `library check` checks a record citing it
- **THEN** it exits 3 with `FEN-3004` and plans no write

### Requirement: Device kinds in the library CI
The library's CI SHALL run, for changed device-kind items: `fenolite library check` (c0262), regeneration of generated footprints and symbols compared with committed outputs, c0259's version rules against the base branch, the rule that seeded records are `UNVERIFIED` or reviewed, and c0262 sheets with an old/new visual diff as a pull-request artefact.

#### Scenario: Version step missing
- **GIVEN** a fixture base tree and a head tree whose `Demo:EXB` record changed without a version step
- **WHEN** `fenolite library audit <head> --base <base> --json` runs
- **THEN** it exits 5 with `library.version-rule` naming `Demo:EXB`

### Requirement: Seeded records from LibrePCB
`fenolite library seed --from-librepcb DIR --commit SHA` SHALL convert LibrePCB packages, components with symbols, and devices with parts into `cc0` library items, each with `item.json`, the CC0 legal code as `LICENSE`, a dated `NOTICE` and `PROVENANCE.json` (`origin: seeded`), and records with `origin` (library, commit, element UUID), `CC0-1.0` and `UNVERIFIED`. A non-CC0 licence file MUST give `FEN-3004`.

#### Scenario: Seed items carry their origin
- **GIVEN** the authored fixture `tests/data/librepcb/demo/` (CC0 legal code, one package, one component with a symbol, one device with two parts), written for Fenolite from the public format page
- **WHEN** `fenolite library seed --from-librepcb tests/data/librepcb/demo --commit <40 hex> --library Demo --into out --dry-run --json` runs
- **THEN** the plan lists one footprint, one symbol and one device item, each with `PROVENANCE.json` of origin `seeded` and records whose `origin.element` is their element UUID and evidence `UNVERIFIED`

#### Scenario: Not a CC0 library
- **GIVEN** the same fixture with another licence file
- **WHEN** the command runs
- **THEN** it exits 3 with `FEN-3004` naming the licence file and plans nothing

### Requirement: Seed determinism and safety
Two seed runs on the same checkout and commit SHALL give the same ids and bytes. Ids SHALL be `<namespace>:<name>` with other characters replaced by `_`; a collision SHALL append `_` and the first 8 hex digits of the element UUID (`library.seed-renamed`). An element that cannot be converted SHALL be skipped with `library.seed-skipped`. A reviewed record MUST NOT be overwritten (`FEN-7001`).

#### Scenario: Same bytes twice
- **WHEN** the seed of the fixture is confirmed into two empty folders
- **THEN** both folders have one tree digest

#### Scenario: Custom pad outline skipped
- **GIVEN** a fixture package with a custom pad outline
- **WHEN** it is seeded
- **THEN** `issues` holds `library.seed-skipped` naming the package UUID and the reason, and the device using it is skipped too

#### Scenario: Reviewed record kept
- **GIVEN** a seeded item in `--into` whose record has a `reviewed_by` entry
- **WHEN** the seed runs again over it with `--confirm`
- **THEN** it exits 7 with `FEN-7001` naming the record and writes nothing

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
`fenolite library gallery` SHALL write a static site of images rendered by Fenolite only. Every card MUST show the title, the authors, the upstream link, the SPDX id, the Fenolite version, "Not endorsed by the authors" (for converted and seeded items), the proof result and the `fenolite get` command. The attribution and licence of every item SHALL come from its `PROVENANCE.json`, cross-checked with the release index: only an item whose provenance says `origin = "authored"` MAY say "Authored for fenolite-library"; a `seeded` item MUST name its upstream authors, link the upstream at its commit, name its licence and say that it was converted. A provenance that is missing, of an unknown origin, or that contradicts the index or itself MUST fail the command with `library.provenance-invalid` errors naming the item and write nothing; it MUST NOT fall back to "Authored" or to CC0. An item with `trademarks.restricted` MUST NOT appear.

#### Scenario: Card attribution
- **GIVEN** the release fixture with one converted board licensed `CERN-OHL-S-2.0`
- **WHEN** the gallery is planned with `--dry-run --json`
- **THEN** the planned card page of that board holds the attribution line with its authors, upstream link and `CERN-OHL-S-2.0`

#### Scenario: Restricted marks hidden
- **GIVEN** a fixture board with `trademarks.restricted = true`
- **WHEN** the gallery is planned
- **THEN** no card or image of that board is planned

#### Scenario: Authored and third-party attribution
- **GIVEN** the release fixture with the authored device `Demo:EXB` and the seeded `CC-BY-SA-4.0` footprint `Demo:SA_PAD`
- **WHEN** the gallery is written
- **THEN** the device page says "Authored for fenolite-library", and the footprint page and card say "Derived from Demo Pad Authors (https://example.org/demo-pads) at commit 000000000000, licence CC-BY-SA-4.0", link the upstream as its source and never say "Authored for fenolite-library"

#### Scenario: Contradictory provenance fails the gallery
- **GIVEN** the release fixture where the seeded footprint's `PROVENANCE.json` says `CC0-1.0` while its index row says `CC-BY-SA-4.0`, or has no upstream, or has no origin
- **WHEN** the gallery is planned
- **THEN** it exits 5 with a `library.provenance-invalid` error naming `Demo:SA_PAD` and the field, and plans no write

### Requirement: Library use statement
The library's README SHALL state that each directory keeps its upstream licence, that the repository's own licence does not cover items, that items are test and benchmark inputs and starting points for users, and that no item is used to train a machine-learning model unless a separate public decision says otherwise. `fenolite library audit` SHALL check these statements.

#### Scenario: README without the use statement
- **GIVEN** the library fixture whose README lacks the training sentence
- **WHEN** the audit runs at the root
- **THEN** it exits 5 with `library.provenance-invalid` naming `README.md`

### Requirement: Checkout newline independence
Git checkouts used by local-file `get` and by `library replay` SHALL disable ambient automatic newline conversion and select LF, without changing global Git configuration. A host configured for CRLF MUST NOT rewrite pinned payload bytes through automatic checkout conversion.

#### Scenario: Host configured for CRLF
- **GIVEN** an authored LF source committed to Git and a host configured with automatic CRLF conversion
- **WHEN** the item is fetched or its pinned conversion is replayed
- **THEN** the payload bytes and their digests remain equal to the committed LF bytes

### Requirement: Designed gallery pages
`fenolite library gallery` SHALL write an index page with a card grid, a text search and filters by kind and
licence, a light and dark theme and a link to the benchmark page; every card MUST show a thumbnail, the
title, the kind, the licence and the attribution. Each item page MUST show the item's images, the
attribution line, a facts table, the `fenolite get` command with a copy control, the proof result, the
evidence level and links to the item's LICENSE and NOTICE. The site MUST NOT load anything from another
origin.

#### Scenario: Index page structure
- **GIVEN** the release fixture
- **WHEN** the gallery is written
- **THEN** `index.html` holds one card per visible item with its thumbnail, kind and licence, the search
  field, the kind and licence filters and the theme control, and no page refers to another origin

#### Scenario: Item page structure
- **GIVEN** the release fixture
- **WHEN** the gallery is written
- **THEN** the page of the demo footprint holds its image, the facts table with its pad count, the
  `fenolite get` command with a copy button, the proof result and the LICENSE and NOTICE links

### Requirement: Item images drawn by Fenolite
The gallery SHALL draw symbol items as an SVG of the symbol, footprint items as an SVG of their land with
pin 1 marked, and device items as the images of their symbol and footprint side by side. Board views and
block sheets SHALL come from `--renders DIR`; a block's `schematic.kicad_sch` SHALL be drawn by Fenolite,
cropped and without its drawing sheet. The same inputs MUST give the same bytes.

#### Scenario: Images for each kind
- **GIVEN** the release fixture and a renders folder with the board's views and the block's schematic
- **WHEN** the gallery is written with `--renders`
- **THEN** the symbol, footprint, device, board and block pages each show at least one image, and the
  footprint image marks pad 1

#### Scenario: Block sheet drawn by Fenolite
- **GIVEN** a renders folder with the block's `schematic.kicad_sch`
- **WHEN** the gallery is written
- **THEN** the block page shows `schematic.svg` drawn from that sheet, and an unreadable sheet gives a
  placeholder naming the error instead

#### Scenario: Deterministic site
- **GIVEN** the same release, root and renders folder
- **WHEN** the gallery is planned twice
- **THEN** every planned file has the same bytes

### Requirement: Image placeholders
An item whose image cannot be made SHALL get a placeholder that names why, and `result.placeholders` MUST
list the item and the reason; the site is still written.

#### Scenario: Missing board render
- **GIVEN** the release fixture and no renders folder
- **WHEN** the gallery is written
- **THEN** the board page shows a placeholder saying no render was supplied, and `result.placeholders`
  holds the board with that reason

