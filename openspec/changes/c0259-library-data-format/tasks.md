## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`fenolite-component-catalog`, `package-layering`) and the changes it builds on (c0246, c0248, c0249, c0254). Write under this task, with the date and the base commit:
  - c0248's final device schema, module names (`catalog/devices.py`, `core/quantities.py`) and project folder rule, and whether it is archived;
  - whether c0254 is merged: if so, `CATALOG_VERSION` and `VERSIONS.toml` exist and this change extends them (design decision 3); if not, this change adds them;
  - whether c0246's `Range` is merged (package dimensions read as ranges, design decision 1);
  - which open change holds a delta of "Offline Fenolite-authored standard catalog" or "Source and evidence labels" (regenerate the MODIFIED blocks from the living text if one was archived);
  - the maintainer's answers to the open questions of `design.md` (licence of shipped records first);
  - the next free `S-` number, for the LibrePCB library registration used by c0266.

  Proof: `openspec validate c0259-library-data-format --strict`; `make check-fast`.

## 1. Golden digests before the move

- [ ] 1.1 Add `tools/catalog/golden.py` and write `tests/data/catalog/golden.json` from the Python catalog: `output_digest` per lib id (canonical JSON of the definition) and the SHA-256 of each file built for `examples/catalog*` with `--seed 1 --timestamp 2026-01-01T00:00:00Z`. Commit it on its own. Proof: `uv run pytest tests/unit/catalog/test_golden.py -q` (passes against the Python catalog).

## 2. Record format

- [ ] 2.1 `src/fenolite/catalog/records.py`: `parse_record`, the common header, exact lengths, the four kinds, `FormatError` codes (scenarios "Each kind is read", "Newer schema", "Unknown header key", "Missing licence", "Mils are exact", "Sub-nanometre length refused"). Author the test records under `tests/data/library/`, each opening with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/catalog/test_records.py -q`.
- [ ] 2.2 `record_text`, `record_uid`, `record_digest`, `output_digest`, `interface_digest` (scenarios "Regeneration keeps the uid", "Round trip", "A review does not change the digest"). Proof: `uv run pytest tests/unit/catalog/test_records.py -k "uid or digest or round" -q`.
- [ ] 2.3 Licence, origin and review rules (scenarios "Shipped record with another licence", "Unreviewed seeded record claims a higher label", "Origin from a non-CC0 library", "Stale review"). Proof: `uv run pytest tests/unit/catalog/test_records.py -k "licence or origin or review" -q`.
- [ ] 2.4 Pins and package records give `SymbolDef` and `FootprintDef` with today's id rules; `library.generator-missing` (scenarios "Pin placed twice", "No drawing and no generator", "Explicit footprint", "Family package before its generator"). Proof: `uv run pytest tests/unit/catalog/test_records_defs.py -q`.
- [ ] 2.5 `fenolite.device.v1` and parts: header, `[[part]]`, `fenolite.part.v0`, inheritance, interface and narrowing rules; c0248's `v0` still read (scenarios "A grade variant inherits the packing", "Cycle refused", "Footprint in a part", "Wider temperature"). Proof: `uv run pytest tests/unit/catalog/test_devices.py tests/unit/catalog/test_parts.py -q`.
- [ ] 2.6 `load_tree`, `shipped_tree`, duplicate ids, and the recursive project folder in `cli/_script.py` (scenarios "Duplicate id in a tree", "Project package overrides a shipped footprint", "Load time"). Register `H-G-LIBRARY-RECORDS`. Proof: `uv run pytest tests/unit/catalog/test_tree.py tests/unit/cli/test_script.py -k devices -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 3. The move

- [ ] 3.1 Add `tools/catalog/to_data.py`, write `src/fenolite/catalog/data/pins/*.toml` and `data/packages/*.toml` from today's definitions (`version = "1.0.0"`, the licence decided at 0.1), rewrite c0248's shipped devices as `fenolite.device.v1` under `data/devices/`, and add the package data to the wheel. Proof: `uv run pytest tests/unit/catalog/test_records.py -k round -q`; `make residue`.
- [ ] 3.2 Switch `get_symbol`, `get_footprint`, `ENTRIES` (lazy), `list_entries`, `default_pad_map` and the two tuples to the records (scenarios "Definitions equal the golden digests", "Pad map from the records"). Proof: `uv run pytest tests/unit/catalog -q`.
- [ ] 3.3 Delete `catalog/_symbol_expansion.py`, the geometry functions and tables, and `tools/catalog/to_data.py` (scenario "No geometry in code"). Proof: `uv run pytest tests/unit/catalog/test_data_only.py tests/unit/catalog/test_golden.py -q`; `make check-fast`.
- [ ] 3.4 Compare built files with `golden.json` in the KiCad job, and the review sheets of `tools/catalog/render_*.py` with their outputs before the move (scenario "Built files are byte-identical"). Register `H-K-CATALOG-DATA`. Proof: `uv run pytest tests/kicad/build/test_catalog_golden.py -rA` (in CI).

## 4. Versions, deprecation and parts in builds

- [ ] 4.1 `catalog/data/VERSIONS.toml`, `CATALOG_VERSION` over all records, `tools/catalog/versions.py --update` and the version test (scenarios "Changed land without a new version", "Metadata change is a patch", "Pad renumbered under an id", "Removed id reused", "Replaces must match a deprecation"). Proof: `uv run pytest tests/unit/catalog/test_versions.py -q`.
- [ ] 4.2 Build codes `library.deprecated` and `library.review-stale` in `lens/build.py` and `explain.toml` (scenarios "Deprecated footprint used", "Stale review"). Proof: `uv run pytest tests/unit/lens/test_build_library_records.py tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 4.3 `design.part(device="<id>@<mpn>")` and the part's fields in the model (scenarios "Reel variant placed", "Unknown MPN"). Proof: `uv run pytest tests/unit/dsl/test_device_parts.py -k mpn -q`.
- [ ] 4.4 `catalog list` and `catalog show` add `version`, `licence`, `uid` (scenario "Show a moved entry"). Proof: `uv run pytest tests/unit/cli/test_catalog.py -q`; `uv run pytest tests/consistency -q`.

## 5. Closing

- [ ] 5.1 Docs: `docs/library-records.md` (kinds, header, ids, versions and the interface rule, licences and origin, reviews, parts and inheritance, the tree), links from `docs/devices.md` and `docs/index.md`, and the `catalog` section of `docs/cli-contract.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
- [ ] 5.2 Agent guide: a tested line in `parts.md` for `design.part(device="<id>@<mpn>")` and one for the record header, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.3 Add an example project record tree (`examples/devices/devices/` gains a pins, a package and a part file). Proof: `uv run pytest tests/unit/test_examples.py -k devices -q`.
- [ ] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
