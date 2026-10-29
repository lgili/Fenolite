## 0. Entry check

- [ ] 0.1 Read `openspec list` and the changes and living specs this change builds on, and record under this task, with the date and the base commit:
  - whether c0248, c0259, c0260 and c0261 are archived. If c0248 is not, move its `catalog import` code into `fenolite.library.importer` as part of its own implementation (design decision 9). Take the device tree, the record keys (`origin`, `licence`, `shippable`) and the stable-id rule from c0259 as archived, and adapt the paths of this change if c0259 kept flat `devices/*.toml` files;
  - the package and function names of c0260's generators and whether `fenolite.library` needs an import edge to them or to `catalog` (update "Allowed import edges" through the change that owns it if so);
  - whether another library change (c0262, c0265, c0266, c0279) already added the subcommand dispatch of `fenolite library`;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0264-library-import --strict`; `make check-fast`.

## 1. Sources and zip safety

- [ ] 1.1 Add `src/fenolite/library/importer/zipsafe.py`: in-memory reading with the limits and name rules of design decision 5, counted while inflating (scenarios "A compression bomb", "Path traversal refused", "Legacy library skipped"). Archives are built inside the tests. Proof: `uv run pytest tests/unit/library/importer/test_zipsafe.py -q`.
- [ ] 1.2 Add `importer/sources.py`: one reader per source kind (KiCad symbol and footprint, Altium `.SchLib`/`.PcbLib` through the existing adapters, STEP header), item selection and the `.IntLib` refusal (scenarios "IntLib refused", "Two footprints, none picked", "Not a STEP file"). Author the test sources under `tests/data/library_import/`, each with the authored-for-Fenolite line and an `example.invalid` datasheet. Proof: `uv run pytest tests/unit/library/importer/test_sources.py -q`.

## 2. Records

- [ ] 2.1 Add `importer/records.py`: the device, pins and package records with `[origin]`, `licence`, `evidence`, the canonical KiCad files, the copied STEP and the model entry (scenarios "Origin rows", "STEP copied unchanged", "Altium symbol drawn from pins", "Same bytes twice"). Register `H-L-IMPORT` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/library/importer/test_records.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 2.2 Move c0248's pin template (function names, identity map, `--pin`, `catalog.pin-without-pad`, `catalog.pad-unmapped`) into the importer, and add `shippable()` and `library.not-shippable` (scenario "An imported device in a pack"). Proof: `uv run pytest tests/unit/library/importer -k "pins or shippable" -q`.

## 3. Cross-check

- [ ] 3.1 Write `docs/formats/library/import-crosscheck.md`: the classifier's features, the tolerances (pitch 0.01 mm, pad centre 0.10 mm, pad size 20 % or 0.10 mm), each labelled `INFERRED`, authored for Fenolite and citing no IPC table. Proof: `uv run pytest tests/unit -k "facts_page or docs" -q`.
- [ ] 3.2 Add `importer/crosscheck.py`: `classify`, `crosscheck(footprint, package=None)` with c0260's generators, and the `library.import-*` findings (scenarios "A matching download", "Clockwise numbering caught", "A pad moved", "KiCad and Altium differ"). Proof: `uv run pytest tests/unit/library/importer/test_crosscheck.py -q`.

## 4. Command

- [ ] 4.1 Add the subcommand dispatch of `fenolite library` if no other change did (scenarios "The board form is unchanged", "A board folder named like a word"). Proof: `uv run pytest tests/unit/cli/test_library.py -q`.
- [ ] 4.2 Add `library import` with its options, the `--into` rules, re-import, the result schema and the codes in `fenolite.library.codes` and `explain.toml` (scenarios "Import an authored archive", "Shipped catalog refused", "Re-import over a reviewed device", "Result fields", "Consistency suite covers the import"). Proof: `uv run pytest tests/unit/cli/test_library_import.py tests/consistency -q`.
- [ ] 4.3 Make `catalog import` the alias with `catalog.import-deprecated` (scenario "Alias keeps its bytes"). Proof: `uv run pytest tests/unit/cli/test_catalog_import.py -q`.
- [ ] 4.4 Author `examples/library_import/` (the authored archive imported into the example's `devices/` and a design that places it) and the KiCad build test (scenario "Confirmed import builds"). Proof: `uv run pytest tests/unit/test_examples.py -k library_import -q`; `uv run pytest tests/kicad/build/test_imported_device.py -rA` (in CI).

## 5. Closing

- [ ] 5.1 Docs: `docs/library-import.md` (sources, what is written, origin and licence, the zip limits, the cross-check, re-import, what sharing the project means for the source terms), `library import` in `docs/cli-contract.md`, links from `docs/index.md` and `docs/devices.md`. Proof: `uv run pytest tests/unit -k docs -q`.
- [ ] 5.2 Agent guide: a tested line of `library import` on the page `parts.md`, saying that the device stays `UNVERIFIED` until reviewed, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.3 Residue and evidence: no third-party file in the repository (every test source authored for Fenolite), the evidence matrix regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
