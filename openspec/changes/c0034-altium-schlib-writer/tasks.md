## 1. Sources, hypotheses, provenance and the fact page

- [x] 1.1 Register sources and hypotheses (first commit of the implementation; c0032's and c0033's groups 1 must already be on the branch).
  - Add S-0150 to S-0155 to `docs/evidence/sources.md` from the design table "Sources registered by this change". S-0150's URL is the AltiumSharp tree at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`, and its cell says "version 1 only; version 2 not used (LEGAL.md P1)". Widen the "used for" cells of S-0002, S-0131 and S-0148 as the design says.
  - Add the eleven `H-A-SCHLIB-*` rows to `docs/hypotheses.md` (backend `altium`), with the paragraph "Change c0034 (Altium schematic library) adds …". The level is `INFERRED`, with the result `pending (author report)`, except `H-A-SCHLIB-KICAD` (`INFERRED`, `pending (oracle)`) and `H-A-SCHLIB-KICAD9` (`UNKNOWN`, `pending (kicad-9 job)`).
  - In `tests/unit/test_altium_rows.py`, `STEMS` gains `H-A-SCHLIB-`.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py`; `grep -cE '^\| H-A-SCHLIB-' docs/hypotheses.md` prints `11`; `grep -cE '^\| S-015[0-5] ' docs/evidence/sources.md` prints `6`.
- [x] 1.2 Write the fact pages in Fenolite's own words.
  - `docs/formats/altium/schematic-library.md`: every fact of design Decisions 3 to 10 and the oracle observations, one row each (`| fact | source | label | hypothesis |`). It holds the binary pin table with offsets and the worked pin, the `FORMALTYPE`, implementation-index and name-list differences between sources, and a note on each S-0150 row that it is version 1 at the pinned commit.
  - The storage rows in `compound-file.md`.
  - `ALTIUM_HYPOTHESES` in `tests/unit/test_format_facts.py` widened to `H-A-(SCH|SCHBIN|SCHLIB|PRJ)-`.
  - `PROVENANCE.md` rows for library container, records, pins and mapping, and a `LEGAL-ANNEX.md` session row.

  Code in later groups is written from these pages, never from the sources' code or the researcher's scratch probe. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`; `uv run python tools/residue/scan.py` exits 0. This covers "Fact page checked".

- [x] 1.3 Check each fact that c0032's and c0033's fact pages cite from S-0142 (unpinned AltiumSharp) against S-0150 (version 1), reading only the version-1 files at the pinned commit.
  - Add "confirmed in S-0150" to the source cell of each confirmed row.
  - List any fact that only version 2 gives in a section "Facts awaiting a permitted source" of `schematic-library.md`, and report it to the coordinator. Change no c0032 or c0033 behaviour here (design Decision 12, Open Question 8).

  Proof: `uv run pytest tests/unit/test_format_facts.py`; `grep -c 'Facts awaiting a permitted source' docs/formats/altium/schematic-library.md` prints `1`; `grep -c 'S-0142' docs/formats/altium/*.md` shows where S-0142 is still cited.

## 2. First library: the sample's, and its kicad-cli round trip

- [x] 2.1 Extend `tests/_cfb_read.py` from `compound-file.md` (storage entries with start 0 and size 0, sibling trees per storage, paths). Then add `Storage`, `Entry`, nested `write_compound` and `storage_from_paths` to `cfb.py` (design Decision 3). Write `tests/unit/backends/altium/test_cfb_storage.py`. Proof: `uv run pytest tests/unit/backends/altium/test_cfb_storage.py tests/unit/backends/altium/test_cfb.py tests/unit/backends/altium/test_cfb_reader.py tests/unit/lens/test_altium_binary_golden.py`. This covers every scenario of "Compound file storages"; the binary golden is unchanged.
- [x] 2.2 Write `read_schlib` in `tests/_altium_read.py` from `schematic-library.md`.
  - Then write `altsym.py` (`AltiumPin`, `AltiumSymbol`, `from_generic`) and `schlib.py` (`pin_record`, `data_stream`, `write_schlib`, `storage_name`).
  - Add `project.schlib_name` and the generic lib-id union to `lens.altium.generic_pins`.
  - Write `tests/unit/backends/altium/test_schlib.py`: the worked pin, header keys, record order, and one negative control per reader check.

  Proof: `uv run pytest tests/unit/backends/altium/test_schlib.py tests/unit/test_import_graph.py tests/unit/test_spdx_headers.py`. This covers "Binary pin record", "Schematic library file", "Library component records", "Generic library symbols", "Library and storage names" and "Schematic libraries read back".
- [x] 2.3 Plumb the library into the build:
  - `write_project(..., symbols=None)` returns `FenoliteSample.SchLib`, and `write_prjpcb(..., libraries=...)` lists it;
  - `cmd_build` gives `.SchLib` the kind `altium_schlib`, and `WRITE_KINDS` gains it;
  - rebuild the two committed project files with `FENOLITE_GOLDEN_WRITE=1`, and add `tests/unit/lens/test_altium_schlib_golden.py` with the committed `tests/data/altium/sample/FenoliteSample.SchLib`, declared in `MANIFEST.toml`, and `*.SchLib -text` in `.gitattributes`.

  Proof: `uv run pytest tests/unit/backends/altium tests/unit/lens -q`; `git diff --exit-code tests/data/altium/sample/altium_sample.SchDoc tests/data/altium/sample/binary/altium_sample.SchDoc` exits 0. This covers "Project file", "Altium writer package" and "Library of the sample".
- [x] 2.4 Write `tests/kicad/altium/test_schlib_oracle.py` for the sample's library: conversion, the generic pins, and the four negative controls. Record the observed exits on the fact page. Hand `FenoliteSample.SchLib` and the rebuilt project to the maintainer for step L1. Proof: `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/altium/test_schlib_oracle.py -q` passes with kicad-cli 10.0.6; `uv run pytest tests/kicad/altium -q` skips without kicad-cli.

## 3. Symbols from KiCad libraries

- [x] 3.1 Write `altsym.from_symbol_def` (design Decisions 6 and 7): directions, body ends, tables, Part Zero, rectangles, overbars, refusals and the `issues` it appends. Write `tests/unit/backends/altium/test_altsym.py`. Proof: `uv run pytest tests/unit/backends/altium/test_altsym.py`. This covers every scenario of "Library symbols from KiCad symbols".
- [x] 3.2 Author `examples/altium_kicad/` (CC0): `design.py`, `FenoliteDemo.kicad_sym` and `sym-lib-table`, covering every symbol feature that "Schematic library samples" lists. Then in `lens.altium` add:
  - `symbol_source`, `kicad_lib_ids` and the `resolver` argument;
  - the symbol's pins and the rewriting of members to pin numbers;
  - the `Footprint` and `Value` fallbacks;
  - `<name>.SchLib` for KiCad lib ids.

  `cmd_build` builds the resolver only when needed. Proof: `uv run pytest tests/unit/lens/test_altium_build.py -q`; `KICAD_CONFIG_HOME="$(mktemp -d)" uv run fenolite build examples/altium_kicad/design.py --out "$(mktemp -d)/b" --target altium --dry-run --json` exits 0. This covers "Altium symbol sources" and "Altium build target".
- [ ] 3.3 Extend the oracle test to `altium_kicad.SchLib`: per-symbol units and per-pin fields against the source `SymbolDef`, plus `Reference` and `Footprint`. Run it locally on 10.0.6 and record the result on the fact page and in `H-A-SCHLIB-KICAD`. Push and record the `kicad-9` job's outcome in `H-A-SCHLIB-KICAD9` (expected-to-fail on major 9 if it fails, with the message). Proof: `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/altium/test_schlib_oracle.py -q -rA`; `gh run view --log` of the `kicad-9` job shows the test's outcome. This covers "Schematic library oracle".

## 4. The schematic from the library geometry (cut here for the minimal scope)

- [x] 4.1 Change the layout and the schematic records to `AltiumSymbol` bodies:
  - component origin at `LOCATION`;
  - stubs in four directions, with `ORIENTATION` on vertical labels and ports;
  - edge-code keys on text pins;
  - `coord_fields` on 10 mil.

  Proof: `uv run pytest tests/unit/backends/altium -q`; `git diff --exit-code tests/data/altium/sample/` exits 0 after a golden run without `FENOLITE_GOLDEN_WRITE`. This covers "ASCII schematic form", "Generic component bodies", "Designator, comment and links", "Connectivity on the sheet", "Deterministic sheet layout" and "Sample schematic unchanged".
- [x] 4.2 Place multi-part symbols: one component record per part, `CURRENTPARTID`, all children, per-part unique ids, Part Zero stubs on part 1, consecutive cells. Proof: `uv run pytest tests/unit/backends/altium/test_schdoc.py tests/unit/backends/altium/test_layout.py -q`. This covers "Dual unit placed twice".
- [x] 4.3 Extend the net readback in `tests/_altium_read.py` to vertical stubs, rotated labels and part records, and compare the example's nets and pin positions with its model and library. Proof: `uv run pytest tests/unit/backends/altium/test_readback.py -q`. This covers "Pins at the library positions" and "Vertical stubs of the example".

## 5. Build rules, issue codes and capabilities

- [x] 5.1 Add the ten issue codes and their checks (unknown pin, off-grid, long pin text, name collisions, library size, lossy pins, simplified symbols, section keys, generic libraries, libraries not in a kept project), and restrict `altium.generic-symbols` to Altium links. Proof: `uv run pytest tests/unit/lens/test_altium_issues.py -q`. This covers "Schematic library issue codes" and "Net member by pin name".
- [x] 5.2 Add `result.libraries`, `result.symbols` and the summary fields, the edited-output and kept-project rules for libraries, and the evidence and capabilities entry with four write kinds. Proof: `uv run pytest tests/unit/lens tests/unit/cli -q`; `uv run fenolite capabilities --json --no-tools | python3 -c "import json,sys; e=json.load(sys.stdin)['result']['experimental'][0]; print(sorted(e['write_kinds']))"` prints the four kinds. This covers "Schematic library outputs", "Schematic library evidence and capabilities", "Altium build outputs" and "Altium schematic format option".
- [x] 5.3 Extend `tests/unit/lens/test_altium_determinism.py` to the example (two in-process builds and two subprocess builds with different seeds, timestamps and hash seeds; the example's own library table). Proof: `uv run pytest tests/unit/lens/test_altium_determinism.py -q`.

## 6. Goldens, protocol and documentation

- [x] 6.1 Commit the example's build under `tests/data/altium/kicad_example/` and declare it in `MANIFEST.toml`. Add Part L to `docs/evidence/altium-schematic.md` (L1 to L6, the SHA-256 values, the rows each step settles, the example's net table, and the licence rule), and update Part A's project-file SHA-256 values. Hand both libraries and projects to the maintainer. Proof: `uv run pytest tests/unit/lens/test_altium_schlib_golden.py tests/corpus/test_manifest.py -q`. This covers "Schematic library samples" and "Schematic library author reports".
- [x] 6.2 Document the libraries in `docs/altium.md`: the two symbol sources, `<name>.SchLib`, the generic stand-in libraries and their risk, the project listing, the kept project file and the oracle. Proof: `grep -c 'SchLib' docs/altium.md` prints a non-zero count; `uv run python tools/residue/scan.py` exits 0. This covers "Schematic library is documented".

## 7. The maintainer's report

- [ ] 7.1 Record the maintainer's Part L report as c0032's "Altium author reports" requires: tool `AD <major>.<minor>`, date, one generic outcome per step, and only results from a licence the maintainer may use. Fix any fault named, with a regression test naming its hypothesis, after recording the changed fact. Rebuild the goldens and update the SHA-256 values. Without a report, the rows stay `pending (author report)`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py tests/unit/test_format_facts.py tests/unit/lens/test_altium_schlib_golden.py`.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `make check`; `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0 (model unchanged); `uv run pytest tests/unit/test_import_graph.py` passes with no `ALLOWED` change; `grep -c '^dependencies = \[\]' pyproject.toml` prints `1`; `openspec validate c0034-altium-schlib-writer --strict --no-interactive` passes.
- [ ] 8.2 Update the evidence labels from the results:
  - `H-A-SCHLIB-KICAD` and the KiCad-read rows of `schematic-library.md` become `ORACLE-VERIFIED(kicad-cli)` with the version and date;
  - `H-A-SCHLIB-KICAD9` gets the observed result;
  - the other rows follow task 7.1.

  `ALTIUM_BUILD_EVIDENCE` stays `INFERRED`, and the entry stays experimental. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py tests/unit/cli/test_capabilities_experimental.py`.
- [ ] 8.3 Add to `CHANGELOG.md` under Unreleased: "Altium target writes schematic libraries: `fenolite build --target altium` writes `<name>.SchLib` with the resolved KiCad symbols (pins, units, Part Zero, synthesised body) and a generic `X.SchLib` for each Altium link library, lists them in the project file and draws the schematic from the same geometry; `cfb.Storage` for nested storages; write kind `altium_schlib`; new `altium.*` issue codes; kicad-cli `sym upgrade` round trip as oracle; evidence `INFERRED`, Altium checks as author reports". Proof: `git diff CHANGELOG.md`.
