## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`kicad-schematic`,
  `altium-schematic-writer`, `design-dsl`, `design-model`) and the state of c0251 and c0252. Write under this
  task the date, the base commit, and:
  - whether c0251 is archived, with the names of port members, the model `Port`, the KiCad sheet name
    rule and the implicit Altium groups;
  - whether c0252's kinds are archived and which of them make a net a member of a `power` interface;
  - which open change holds a delta of "Hierarchical sheets of a design", "Generated sheet content", "Own
    netlist of a generated sheet", "Netlist grammar check", "Deterministic sheet layout" or "Sheets of a
    module tree". If one was archived, regenerate the MODIFIED block from the living text;
  - whether `schematic_group` and `block_schematics` are free names in `fenolite.dsl`;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0269-block-schematic --strict`; `make check-fast`.

## 1. DSL and model

- [ ] 1.1 Add `schematic_group`, the builder's `schematic`, `dsl.block_schematics` and the sheet-name
  clash check of `port` (scenarios "Part of a nested block refused", "Cycle refused", "Groups reach every
  instance", "Clash with an interface member"). Proof: `uv run pytest tests/unit/dsl/test_block_schematic.py -q`.
- [ ] 1.2 Add `SheetPin` and `SheetRef.pins` to `model/schematic.py` and regenerate the schemas
  (scenarios "Older sheet data", "Refused shape"). Proof:
  `uv run pytest tests/unit/model/test_schematic.py -k sheet_pin -q`; `uv run python tools/gen_schemas.py --check`.

## 2. KiCad sheets

- [ ] 2.1 Write sheet pins and hierarchical labels in `sch.py`, and add `sch.opaque_sheet_pins`
  (scenario "Pins read back"; the existing writer scenarios keep passing). Record the forms in
  `docs/formats/kicad/schematic.md` with S-0367 and their label. Proof:
  `uv run pytest tests/unit/backends/kicad/test_sch_write.py -q`.
- [ ] 2.2 Generate hierarchical labels, sheet pins, their geometry and the merged case in `schgen.py`
  (scenarios "Port net labelled by the port", "Interface port members", "Sides and order", "Two ports
  joined outside", "Block instance with ports", "Plain modules unchanged"). Proof:
  `uv run pytest tests/unit/backends/kicad/test_schgen_blocks.py tests/unit/backends/kicad/test_schgen.py -q`.
- [ ] 2.3 Read hierarchical labels and sheet pins in `sch_netlist.py`, with the narrowed grammar rows
  (scenarios "Block sheets", "Block sheets are inside the grammar", "Sheet pin without a label"; "Hierarchy
  refused" and the other existing scenarios keep passing). Proof:
  `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py tests/unit/lens/test_build_netlist_guard.py -q`.
- [ ] 2.4 Order units by groups, size sheet references with pins, and share one arrangement per block in
  `schlayout.py` and `schgen.py` (scenarios "Groups start rows", "Declared chain", "Default group", "Two
  instances, one arrangement"; "Deterministic" of "Readable sheet layout" keeps passing). Proof:
  `uv run pytest tests/unit/backends/kicad/test_schlayout.py tests/unit/backends/kicad/test_schlayout_snap.py -q`.
- [ ] 2.5 Byte guard: designs without block instances keep every written byte. Proof:
  `uv run pytest tests/unit/lens/test_build_bytes_pinned.py -q`.

## 3. Altium sheets and composition

- [ ] 3.1 Cross block sheets by their ports in `hierarchy.py`, and add `build.block-sheet-name-clash`
  with the authored `tests/data/altium/blocks/design.py` (CC0, authored for Fenolite; scenarios "Block
  instance crossings", "Escaping net still crosses", "Power port stays global", "Escaping net named like a
  port"; "Two levels" and "Passed through the sheet between" keep passing). Proof:
  `uv run pytest tests/unit/backends/altium/test_hierarchy.py -q`.
- [ ] 3.2 Map local groups into Altium block composition and keep them out of the intent rules
  (scenarios "Local groups in block mode", "Library block in every mode"). Proof:
  `uv run pytest tests/unit/schematic/test_composition_blocks.py tests/unit/dsl/test_block_schematic.py -k altium -q`.

## 4. Evidence

- [ ] 4.1 KiCad CI job: build `examples/blocks/design.py` for each major, export its netlist with
  `kicad-cli` and run ERC (scenario "KiCad reads the block netlist"). Add the rows `H-K-SCH-BLOCK-PINS`
  and `H-K-SCH-BLOCK-ERC` to the evidence matrix as `KICAD-VERIFIED (9.0.x, 10.0.x)` only after the job
  passes. Proof: the KiCad job of the commit on GitHub CI is green;
  `uv run pytest tests/kicad/build/test_block_sheets.py -q` there.
- [ ] 4.2 Altium kit: add a step that compiles the authored block design and records the messages and
  net names (`H-A-BLOCK-ENTRIES`). The row stays `INFERRED` until the maintainer reports. Proof:
  `uv run pytest tests/unit/test_altium_verification_docs.py -q`.

## 5. Documentation and guide

- [ ] 5.1 `docs/schematic.md`: block sheets, hierarchical pins, sheet names, the merged case, groups and
  the shared arrangement. `docs/schematic-composition.md`: local groups in block mode and why they are not
  intent. `docs/dsl.md`: `b.schematic` and `schematic_group`. Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.2 Agent guide (AGENTS.md rule 6): a tested line for `schematic_group` and the builder's
  `schematic` on the page `design-script`, and for the two codes on the page `checks`. Regenerate the
  generated pages. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.

## 6. Changelog and CI

- [ ] 6.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof:
  `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 6.2 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on
  that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4).
  Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
