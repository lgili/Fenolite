## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`fenolite-component-catalog`, `package-layering`) and the changes it builds on (c0246, c0248, c0249, c0254). Write under this task, with the date and the base commit:
  - c0248's final device schema, module names (`catalog/devices.py`, `core/quantities.py`) and project folder rule, and whether it is archived;
  - whether c0254 is merged: if so, `CATALOG_VERSION` and `VERSIONS.toml` exist and this change extends them (design decision 3); if not, this change adds them;
  - whether c0246's `Range` is merged (package dimensions read as ranges, design decision 1);
  - which open change holds a delta of "Offline Fenolite-authored standard catalog" or "Source and evidence labels" (regenerate the MODIFIED blocks from the living text if one was archived);
  - the maintainer's answers to the open questions of `design.md` (licence of shipped records first);
  - the next free `S-` number, for the LibrePCB library registration used by c0266.

  Proof: `openspec validate c0259-library-data-format --strict`; `make check-fast`.
  Note (2026-10-29, branch `cac/c0259-library-data-format` from `cac/c0248-device-catalog` at 635bc180): c0248
  is implemented on its branch and not archived: device schema `fenolite.device.v0`, modules
  `catalog/devices.py` and `core/quantities.py`, project devices in `devices/` beside the script. c0254 is not
  merged, so this change adds `CATALOG_VERSION` and `catalog/data/VERSIONS.toml`. c0246's `Range` is not
  merged: package dimensions keep exact integer bounds (`"a..b"`). No open change holds a delta of "Offline
  Fenolite-authored standard catalog" or "Source and evidence labels" but this one. Next free source number:
  S-0855 (not registered here: c0266 registers the LibrePCB library). Left open: the maintainer's answers to
  the open questions of `design.md` are not recorded; the migration writes `Apache-2.0` (question 1) and the
  recommended answers are implemented for questions 2 to 4.

## 1. Golden digests before the move

- [x] 1.1 Add `tools/catalog/golden.py` and write `tests/data/catalog/golden.json` from the Python catalog: `output_digest` per lib id (canonical JSON of the definition) and the SHA-256 of each file built for `examples/catalog*` with `--seed 1 --timestamp 2026-01-01T00:00:00Z`. Commit it on its own. Proof: `uv run pytest tests/unit/catalog/test_golden.py -q` (passes against the Python catalog).
  Done (2026-10-29): `tools/catalog/golden.py` and `tests/data/catalog/golden.json`, committed on its own (73a33f0c) before any record existed. There was no `examples/catalog*`: this change adds `examples/catalog/design.py`, a supply built from catalog ids alone. `.fenolite/meta.json` is left out of the built files because it names the version of Fenolite. Proof passed (`test_golden.py`, 3 tests, against the Python catalog).

## 2. Record format

- [x] 2.1 `src/fenolite/catalog/records.py`: `parse_record`, the common header, exact lengths, the four kinds, `FormatError` codes (scenarios "Each kind is read", "Newer schema", "Unknown header key", "Missing licence", "Mils are exact", "Sub-nanometre length refused"). Author the test records under `tests/data/library/`, each opening with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/catalog/test_records.py -q`.
  Done (2026-10-29): `catalog/records.py` (`parse_record`, the header, the four kinds, exact lengths through `core.quantities.parse_length` and `parse_angle`); test records under `tests/data/library/`, declared in the manifest. Proof passed.
- [x] 2.2 `record_text`, `record_uid`, `record_digest`, `output_digest`, `interface_digest` (scenarios "Regeneration keeps the uid", "Round trip", "A review does not change the digest"). Proof: `uv run pytest tests/unit/catalog/test_records.py -k "uid or digest or round" -q`.
  Done (2026-10-29): `record_text`, `record_uid`, `record_digest`, `output_digest`, `interface_digest`. The arrays keep the order of their file (the order of a symbol's pins and of a footprint's pads is part of the definition), so the spec delta says "in their order". A review names the digest of the record as it is after the review, with the label it asserts. Proof passed.
- [x] 2.3 Licence, origin and review rules (scenarios "Shipped record with another licence", "Unreviewed seeded record claims a higher label", "Origin from a non-CC0 library", "Stale review"). Proof: `uv run pytest tests/unit/catalog/test_records.py -k "licence or origin or review" -q`.
  Done (2026-10-29): the licence, origin and review rules (stale reviews are reported by the build, task 4.2). Proof passed.
- [x] 2.4 Pins and package records give `SymbolDef` and `FootprintDef` with today's id rules; `library.generator-missing` (scenarios "Pin placed twice", "No drawing and no generator", "Explicit footprint", "Family package before its generator"). Proof: `uv run pytest tests/unit/catalog/test_records_defs.py -q`.
  Done (2026-10-29): `symbol_def`, `footprint_def` with today's id rules, `GeneratorMissingError` and `library.generator-missing` in the build. Proof passed (7 tests).
- [x] 2.5 `fenolite.device.v1` and parts: header, `[[part]]`, `fenolite.part.v0`, inheritance, interface and narrowing rules; c0248's `v0` still read (scenarios "A grade variant inherits the packing", "Cycle refused", "Footprint in a part", "Wider temperature"). Proof: `uv run pytest tests/unit/catalog/test_devices.py tests/unit/catalog/test_parts.py -q`.
  Done (2026-10-29): `fenolite.device.v1` with `[[part]]`, `fenolite.part.v0` (id `<device id>@<mpn>`), `resolved_part` and `effective_part`, the interface and narrowing rules; `v0` files are still read (`catalog/devices.py` gains `parse_device_data` and `device_text(header=False)`). Proof passed (47 tests).
- [x] 2.6 `load_tree`, `shipped_tree`, duplicate ids, and the recursive project folder in `cli/_script.py` (scenarios "Duplicate id in a tree", "Project package overrides a shipped footprint", "Load time"). Register `H-G-LIBRARY-RECORDS`. Proof: `uv run pytest tests/unit/catalog/test_tree.py tests/unit/cli/test_script.py -k devices -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  Done (2026-10-29): `load_tree`, `shipped_tree`, duplicate ids, `replaces`, and the recursive project folder
  (`cli/_script.read_project_library`; `ScriptRun.library`). `H-G-LIBRARY-RECORDS` is registered. The scenario
  "Load time" has a relative budget, so that it holds on any runner: the tree reads in at most 2.5 times the
  time `tomllib` alone takes on the same files (116 ms against 94 ms here); the spec delta says so. Proofs
  passed.

## 3. The move

- [x] 3.1 Add `tools/catalog/to_data.py`, write `src/fenolite/catalog/data/pins/*.toml` and `data/packages/*.toml` from today's definitions (`version = "1.0.0"`, the licence decided at 0.1), rewrite c0248's shipped devices as `fenolite.device.v1` under `data/devices/`, and add the package data to the wheel. Proof: `uv run pytest tests/unit/catalog/test_records.py -k round -q`; `make residue`.
  Done (2026-10-29): `tools/catalog/to_data.py` wrote 49 pins and 100 package records and rewrote c0248's ten devices as `fenolite.device.v1` under `data/devices/`; each record was read back and its definition compared with the Python one. The wheel is built by hatchling from `src/fenolite`, which includes the TOML files. Proofs passed (`-k round`; `make residue`: 0 hits).
- [x] 3.2 Switch `get_symbol`, `get_footprint`, `ENTRIES` (lazy), `list_entries`, `default_pad_map` and the two tuples to the records (scenarios "Definitions equal the golden digests", "Pad map from the records"). Proof: `uv run pytest tests/unit/catalog -q`.
  Done (2026-10-29): `get_symbol`, `get_footprint` (cached), `ENTRIES`, `ANODE_FIRST_SYMBOLS` and `CATHODE_FIRST_LANDS` (lazy, through a module `__getattr__`), `list_entries` and `default_pad_map` read the records; every definition equals `golden.json`. Proof passed (`tests/unit/catalog`).
- [x] 3.3 Delete `catalog/_symbol_expansion.py`, the geometry functions and tables, and `tools/catalog/to_data.py` (scenario "No geometry in code"). Proof: `uv run pytest tests/unit/catalog/test_data_only.py tests/unit/catalog/test_golden.py -q`; `make check-fast`.
  Done (2026-10-29): `catalog/_symbol_expansion.py`, the geometry functions and tables, `catalog/devices/` and `tools/catalog/to_data.py` are deleted (git history keeps them). Proofs passed (`test_data_only.py`, `test_golden.py`; `make check-fast`).
- [x] 3.4 Compare built files with `golden.json` in the KiCad job, and the review sheets of `tools/catalog/render_*.py` with their outputs before the move (scenario "Built files are byte-identical"). Register `H-K-CATALOG-DATA`. Proof: `uv run pytest tests/kicad/build/test_catalog_golden.py -rA` (in CI).
  Done (2026-10-29): `tests/kicad/build/test_catalog_golden.py` rebuilds `examples/catalog` and compares every file with `golden.json`; the review sheets are compared in `test_golden.py`. `H-K-CATALOG-DATA` is registered. Proof: passed locally (no `kicad-cli` is needed to build); it runs in the KiCad job in CI.

## 4. Versions, deprecation and parts in builds

- [x] 4.1 `catalog/data/VERSIONS.toml`, `CATALOG_VERSION` over all records, `tools/catalog/versions.py --update` and the version test (scenarios "Changed land without a new version", "Metadata change is a patch", "Pad renumbered under an id", "Removed id reused", "Replaces must match a deprecation"). Proof: `uv run pytest tests/unit/catalog/test_versions.py -q`.
  Done (2026-10-29): `catalog/data/VERSIONS.toml` (catalog `1.0.0`, 159 entries), `fenolite.catalog.CATALOG_VERSION`, `tools/catalog/versions.py [--update]` and `version_problems`/`updated_versions`. Proof passed (7 tests).
- [x] 4.2 Build codes `library.deprecated` and `library.review-stale` in `lens/build.py` and `explain.toml` (scenarios "Deprecated footprint used", "Stale review"). Proof: `uv run pytest tests/unit/lens/test_build_library_records.py tests/unit/cli/test_explain_cmd.py -q`.
  Done (2026-10-29): `LIBRARY_ISSUE_CODES` in `catalog/records.py` (registered in `cli/explain.py` and `explain.toml`); `cmd_build` reports them for the records a design uses (the lens does not import the catalog). Proofs passed.
- [x] 4.3 `design.part(device="<id>@<mpn>")` and the part's fields in the model (scenarios "Reel variant placed", "Unknown MPN"). Proof: `uv run pytest tests/unit/dsl/test_device_parts.py -k mpn -q`.
  Done (2026-10-29): `design.part(device="<id>@<mpn>")` resolves the part from the design's, the project's or the shipped records (`Design.devices` also takes a device record with its parts); an unknown MPN lists the device's parts. Proof passed.
- [x] 4.4 `catalog list` and `catalog show` add `version`, `licence`, `uid` (scenario "Show a moved entry"). Proof: `uv run pytest tests/unit/cli/test_catalog.py -q`; `uv run pytest tests/consistency -q`.
  Done (2026-10-29): `version`, `licence` and `uid` on every entry of `catalog list` and `show` (devices included); `CatalogEntry` gains the three fields with defaults. Proofs passed (`test_catalog.py`; `tests/consistency`).

## 5. Closing

- [x] 5.1 Docs: `docs/library-records.md` (kinds, header, ids, versions and the interface rule, licences and origin, reviews, parts and inheritance, the tree), links from `docs/devices.md` and `docs/index.md`, and the `catalog` section of `docs/cli-contract.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
  Done (2026-10-29): `docs/library-records.md`, links from `docs/devices.md`, `docs/index.md` and `docs/catalog/README.md`, and the `catalog` section of `docs/cli-contract.md`. Proof passed (69 tests).
- [x] 5.2 Agent guide: a tested line in `parts.md` for `design.part(device="<id>@<mpn>")` and one for the record header, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
  Done (2026-10-29): `parts.md` gains a line on the record header and a design block that places `Proj:REG@REG100DR` from a record given to `design.devices`; generated pages rewritten; `test_pages_kicad.py` names the new block. Proof passed.
- [x] 5.3 Add an example project record tree (`examples/devices/devices/` gains a pins, a package and a part file). Proof: `uv run pytest tests/unit/test_examples.py -k devices -q`.
  Done (2026-10-29): `examples/devices/devices/` holds the device as `fenolite.device.v1` with a `[[part]]`, a part file (`parts/`), two pins records (the regulator's symbol, which leaves the script, and a test point) and a package record (a test pad placed as `TP1`). Proof passed.
- [ ] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
  Left open (2026-10-29): `dev` is at the unpublished 0.6.0 and `tests/unit/test_release_record_v06.py`
  requires `## [Unreleased]` to stay empty, so the entry waits until `dev` is at `0.7.0.dev0`.
- [ ] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
