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
  2026-10-29: base `5028255f` (circuits-as-code with c0246-c0251, c0248, c0276, c0278). c0251 is merged, not archived: port members `net`, `hv`/`lv`, `sda`/`scl`…, the model `Port(name, owner, kind, direction, members, optional)` with members ordered by name, the sheet name `<name> (<block name>)` and the implicit Altium groups (`dsl/schematic.py::_implicit`). c0252 is not merged: no `Rail`/`Ground`/`Logic`; a net is a power net through `Power` only. No other open change holds a delta of the six requirements. `schematic_group` and `block_schematics` were free. c0276 had added the `SheetPin` stub (built on, not duplicated). Open questions decided in design.md (maintainer's delegation). Not ticked: the `openspec` CLI is not installed here (`openspec validate --strict` did not run); `make check-fast` is recorded under 6.2.

  Proof: `openspec validate c0269-block-schematic --strict`; `make check-fast`.

## 1. DSL and model

- [x] 1.1 Add `schematic_group`, the builder's `schematic`, `dsl.block_schematics` and the sheet-name
  clash check of `port` (scenarios "Part of a nested block refused", "Cycle refused", "Groups reach every
  instance", "Clash with an interface member"). Proof: `uv run pytest tests/unit/dsl/test_block_schematic.py -q`.
- [x] 1.2 Add `SheetPin` and `SheetRef.pins` to `model/schematic.py` and regenerate the schemas
  (scenarios "Older sheet data", "Refused shape"). Proof:
  `uv run pytest tests/unit/model/test_schematic.py -k sheet_pin -q`; `uv run python tools/gen_schemas.py --check`.
  2026-10-29: `dsl/blockschematic.py` (`schematic_group`, `declare`, `block_schematics`), `Block.schematic` and the sheet-name check of `b.port`; neutral records in `schematic/block_sheets.py`. A single-member port is a port of kind `Net` (design.md, decision 2). Proof passed (21 tests).
  2026-10-29: `SheetPin` and `SheetRef.pins` existed (c0276 stub); added the shape check (`PIN_SHAPES`: c0276's drawn sheets also use `tri_state` and `passive`, so the scenario refuses `clock`; spec amended). Schemas unchanged. Proof passed.

## 2. KiCad sheets

- [x] 2.1 Write sheet pins and hierarchical labels in `sch.py`, and add `sch.opaque_sheet_pins`
  (scenario "Pins read back"; the existing writer scenarios keep passing). Record the forms in
  `docs/formats/kicad/schematic.md` with S-0367 and their label. Proof:
  `uv run pytest tests/unit/backends/kicad/test_sch_write.py -q`.
- [x] 2.2 Generate hierarchical labels, sheet pins, their geometry and the merged case in `schgen.py`
  (scenarios "Port net labelled by the port", "Interface port members", "Sides and order", "Two ports
  joined outside", "Block instance with ports", "Plain modules unchanged"). Proof:
  `uv run pytest tests/unit/backends/kicad/test_schgen_blocks.py tests/unit/backends/kicad/test_schgen.py -q`.
- [x] 2.3 Read hierarchical labels and sheet pins in `sch_netlist.py`, with the narrowed grammar rows
  (scenarios "Block sheets", "Block sheets are inside the grammar", "Sheet pin without a label"; "Hierarchy
  refused" and the other existing scenarios keep passing). Proof:
  `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py tests/unit/lens/test_build_netlist_guard.py -q`.
- [x] 2.4 Order units by groups, size sheet references with pins, and share one arrangement per block in
  `schlayout.py` and `schgen.py` (scenarios "Groups start rows", "Declared chain", "Default group", "Two
  instances, one arrangement"; "Deterministic" of "Readable sheet layout" keeps passing). Proof:
  `uv run pytest tests/unit/backends/kicad/test_schlayout.py tests/unit/backends/kicad/test_schlayout_snap.py -q`.
- [x] 2.5 Byte guard: designs without block instances keep every written byte. Proof:
  `uv run pytest tests/unit/lens/test_build_bytes_pinned.py -q`.
  2026-10-29: the writer's `pin` and `hierarchical_label` and `sch.opaque_sheet_pins` came with c0276; scenario "Pins read back" is `test_schgen_blocks.py::test_pins_read_back` (targets 9 and 10). Forms recorded in `docs/formats/kicad/schematic.md` (S-0367, INFERRED, `H-K-SCH-BLOCK-PINS`). Proof passed.
  2026-10-29: `schgen._block_sheets`, `_placed_ref`, labeller in `_content`, `build.block-port-merged`; scenarios in `tests/unit/backends/kicad/test_schgen_blocks.py` ("Port net labelled by the port" is pin 1 of `R_EN`, net `VIN`: spec text corrected to the example). Proof passed.
  2026-10-29: `sch_netlist` joins hierarchical labels and sheet pins (`_Joined`), the narrowed `label-kind` and the new `sheet` rows; reasons unchanged. Proof passed (with `test_schgen_blocks.py` for the block scenarios).
  2026-10-29: `layout_units(groups=, widths=)`, `RefPin`, `ref_height`, `ref_pin_points`, snapping per group, `schgen._shared_widths`. Proof passed.
  2026-10-29: Proof passed; plain modules keep their sheets (`test_plain_modules_unchanged`).

## 3. Altium sheets and composition

- [x] 3.1 Cross block sheets by their ports in `hierarchy.py`, and add `build.block-sheet-name-clash`
  with the authored `tests/data/altium/blocks/design.py` (CC0, authored for Fenolite; scenarios "Block
  instance crossings", "Escaping net still crosses", "Power port stays global", "Escaping net named like a
  port"; "Two levels" and "Passed through the sheet between" keep passing). Proof:
  `uv run pytest tests/unit/backends/altium/test_hierarchy.py -q`.
- [x] 3.2 Map local groups into Altium block composition and keep them out of the intent rules
  (scenarios "Local groups in block mode", "Library block in every mode"). Proof:
  `uv run pytest tests/unit/schematic/test_composition_blocks.py tests/unit/dsl/test_block_schematic.py -k altium -q`.
  2026-10-29: `hierarchy.block_crossings`, `name_clashes`, `Crossing.label` (stub label = circuit net), `build.block-sheet-name-clash` in `lens/altium.py`; authored sample `tests/data/altium/blocks/design.py` (in MANIFEST; Apache-2.0 header, which the SPDX test requires of every `.py` under `tests/`, instead of CC0). Tests in `tests/unit/backends/altium/test_block_entries.py`; port order is the model's (design.md, decision 5). The `build.block-net-escape` of scenario "Escaping net still crosses" is c0251's KiCad check, not an Altium code. Proof passed (`test_hierarchy.py` and `test_block_entries.py`).
  2026-10-29: `dsl/schematic.py::_local_groups`; KiCad and Altium-grid CLI builds of a library block (`test_library_block_in_every_mode`). Proof passed.

## 4. Evidence

- [ ] 4.1 KiCad CI job: build `examples/blocks/design.py` for each major, export its netlist with
  `kicad-cli` and run ERC (scenario "KiCad reads the block netlist"). Add the rows `H-K-SCH-BLOCK-PINS`
  and `H-K-SCH-BLOCK-ERC` to the evidence matrix as `KICAD-VERIFIED (9.0.x, 10.0.x)` only after the job
  passes. Proof: the KiCad job of the commit on GitHub CI is green;
  `uv run pytest tests/kicad/build/test_block_sheets.py -q` there.
- [x] 4.2 Altium kit: add a step that compiles the authored block design and records the messages and
  net names (`H-A-BLOCK-ENTRIES`). The row stays `INFERRED` until the maintainer reports. Proof:
  `uv run pytest tests/unit/test_altium_verification_docs.py -q`.
  2026-10-29: `tests/kicad/build/test_block_sheets.py` passed locally with `FENOLITE_KICAD_CLI=docker:kicad/kicad:10.0.6` (six nets under their circuit names, ERC empty). Rows stay INFERRED with that note: open until the KiCad job of CI passes on 9.0.x and 10.0.x (CI runs with the batch).
  2026-10-29: Part K (steps K1 to K3) in `docs/evidence/altium-schematic.md`; `H-A-BLOCK-ENTRIES` stays INFERRED until the maintainer's kit run. Proof passed.

## 5. Documentation and guide

- [x] 5.1 `docs/schematic.md`: block sheets, hierarchical pins, sheet names, the merged case, groups and
  the shared arrangement. `docs/schematic-composition.md`: local groups in block mode and why they are not
  intent. `docs/dsl.md`: `b.schematic` and `schematic_group`. Proof: `uv run pytest tests/consistency -q`.
- [x] 5.2 Agent guide (AGENTS.md rule 6): a tested line for `schematic_group` and the builder's
  `schematic` on the page `design-script`, and for the two codes on the page `checks`. Regenerate the
  generated pages. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-10-29: `docs/schematic.md` ("Block sheets", netlist and grammar), `docs/schematic-composition.md`, `docs/dsl.md` (Blocks: sheet names, block schematic groups). Proof passed.
  2026-10-29: blocks are taught on the page `parts` (its block example calls `b.schematic(schematic_group(...))`, and the port bullet names the sheet pins), because `design-script` is at 11 985 of its 12 000 bytes; the two codes on `checks`; `block_schematics` joins `DSL_NOT_TAUGHT` as a build call. Generated pages regenerated. Proof passed.

## 6. Changelog and CI

- [x] 6.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof:
  `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 6.2 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on
  that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4).
  Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
  2026-10-29: open: CI runs with the batch. `make check-fast PYTEST_WORKERS=2` passed locally (TMPDIR outside the worktree): 16 243 passed, 48 skipped, exit 0.

  2026-10-29: entry under `## [Unreleased]` (the base already holds 0.7.0.dev0 entries). Proof: `tests/consistency` passed.