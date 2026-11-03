## 0. Entry check

- [x] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `design-model`,
  `kicad-schematic`, `altium-schematic-writer`, `verification-loop`, `layout-lens`) and the state of c0269,
  c0250, c0249 and c0275. Write under this task the date, the base commit, and:
  - whether c0269 is archived, with the names of `SheetPin`, `sch.opaque_sheet_pins` and the block-sheet
    generator entry that decision 11 calls;
  - whether c0250's `edits.toml` and `sync` changes are archived, so that decision 9 builds on them;
  - whether `load_schematic`, `drawn_schematic`, `fenolite.model.drawn` and `fenolite.lens.drawn` are free
    names, and whether another open change adds a stage after `parity`;
  - the maintainer's answers to the open questions of `design.md`, in particular whether phase 6 (Altium)
    stays in this change.

  Proof: `openspec validate c0276-drawn-schematic --strict`; `make check-fast`.
  2026-10-30: base `0a710502` (circuits-as-code). c0269 is merged now (`SheetPin`, `SheetRef.pins`,
  `sch.opaque_sheet_pins`, the block sheets of `schgen.generate_schematic` with `groups`), and so is c0250;
  the stub of 2026-10-29 was resolved into c0269's names by the merge. Still open: `openspec validate --strict`
  is run by the coordinator (the CLI is not installed here); `make check-fast` is recorded under 9.2.
  2026-10-29: base `a170bc55` (circuits-as-code with c0246, c0247, c0249, dev 0.7.0.dev0 with c0243/c0244). c0269 is not merged (no `SheetPin`, no `sch.opaque_sheet_pins`, no block-sheet generator): this change adds the minimal stub c0269 specifies (`SheetPin`, `SheetRef.pins`, the writer's `pin`, `sch.opaque_sheet_pins`). c0250 is not merged (branch `cac/c0250-manual-edit-merge` in progress): decision 9 stands on the existing sync. `load_schematic`, `drawn_schematic`, `fenolite.model.drawn` and `fenolite.lens.drawn` were free; no other change adds a stage after `parity`. Open questions decided under each in design.md (maintainer's delegation): phase 6 stays in this change and is left open. Not ticked: the `openspec` CLI is not installed in this environment, so `openspec validate --strict` did not run; `make check-fast` is recorded under 9.2.

## 1. Facts and hypotheses

- [x] 1.1 Read the schematic editor manual (S-0046, again for this change) and the format page (S-0367)
  for wires, junctions, labels and their scope, buses, bus entries, bus aliases, sheet pins, power symbols
  and hidden power pins. Record each rule of design decision 4 as a row of
  `docs/formats/kicad/schematic.md` with its source and label (`INFERRED` until measured), and update the
  entry of S-0046 in `docs/evidence/sources.md` with what was read. Proof:
  `uv run pytest tests/unit -k "facts_page or sources" -q`.
  2026-10-29: rows of "Drawn schematic connectivity" in `docs/formats/kicad/schematic.md` (S-0046, S-0367, S-0020; `INFERRED`), S-0046 updated in `docs/evidence/sources.md`. Two rules changed by measurement with `kicad-cli` 9.0.9 and 10.0.6 (local docker images): a T joins only through a junction, a pin joins a wire at its end only. Proof passed.

- [x] 1.2 Register `H-K-DRAWN-CONNECT`, `H-K-DRAWN-NAMES`, `H-K-DRAWN-BUS`, `H-K-DRAWN-REPEAT`,
  `H-K-DRAWN-WRITE` and `H-A-DRAWN-WRITE` in `docs/hypotheses.md`, each with its settling test or kit
  request. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  2026-10-29: the six rows (pre-registered as proposed) now name `tests/kicad/schematic/test_drawn_oracle.py` or the kit request, with the local measurements; `H-A-DRAWN-WRITE` stays pending (phase 6). Proof passed.

## 2. Model and file

- [x] 2.1 Add `Junction`, `BusWire`, `BusEntry`, `BusAlias` and the new `SchematicSheet` collections to
  `model/schematic.py`, and regenerate the schemas (scenarios "Older sheet data", "Read sheets stay
  opaque", "No float"). Proof: `uv run pytest tests/unit/model/test_schematic.py -q`;
  `uv run python tools/gen_schemas.py --check`.
  2026-10-29: `Junction`, `BusWire`, `BusEntry`, `BusAlias`, the c0269 stub `SheetPin`/`SheetRef.pins` and the four collections; schema regenerated; `Wire` stays horizontal or vertical (a slanted drawn segment is written as an opaque `wire`). Proof passed.

- [x] 2.2 Add `model/drawn.py` with the drawn value and `instances()` (scenarios "Equality and hashing",
  "Instances from paths"). Proof: `uv run pytest tests/unit/model/test_drawn_value.py -q`.
  2026-10-29: `model/drawn.py` (`DrawnSchematic.walk()`/`instances()`; the title block as text pairs so the value hashes). Proof passed.

- [x] 2.3 Author the fixtures `tests/data/drawn/{flat,full,hier,bus,repeat}/` (CC0, authored for
  Fenolite, each with its design script) and declare them in `tests/data/MANIFEST.toml` with
  `origin = "authored"`. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py -q`.
  2026-10-29: `tests/data/drawn/{flat,full,hier,bus,repeat}/` and `examples/drawn/` (design script, `schematic.toml`, library tables naming the authored mini library), declared in the manifest. `tests/residue` passes; `tests/corpus/test_manifest.py` fails only on `examples/lock/design.lock` and `examples/lock/design.py`, undeclared by c0249 before this change (not touched here, for a clean merge).
  2026-10-30: the proof passes on `0a710502` (88 passed, 1 skipped without `kicad-cli`); ticked.

- [x] 2.4 Add `lens/drawn.py` with `read_drawn` and `write_drawn`, and
  `schemas/fenolite.drawn-schematic.v0.json` (scenarios of "Drawn schematic file", "Drawn file numbers",
  "Drawn sheet items", "Canonical drawn file"). Proof: `uv run pytest tests/unit/lens/test_drawn_file.py -q`.
  2026-10-29: `lens/drawn.py` and `schemas/fenolite.drawn-schematic.v0.json` (checked against the closed key sets by `tests/consistency/test_drawn_schema.py`); paper names are those of `SheetFrameRef`. Proof passed.

## 3. Resolver and comparison

- [x] 3.1 Add `model/drawn_connect.py` with `resolve` for wires, junctions, labels, power symbols, hidden
  power pins and sheet pins (scenarios "Hermetic", "Order and splitting do not matter", "T joint and
  crossing", "Junction on a crossing", "Hierarchical pin", "Local labels stay on their instance").
  Proof: `uv run pytest tests/unit/model/test_drawn_connect.py -q`.
  2026-10-29: `resolve` with the measured T, crossing and pin rules. Proof passed.

- [x] 3.2 Add buses, bus entries and aliases (scenarios "Data bus through a sheet", "Entry without a
  label"). Proof: `uv run pytest tests/unit/model/test_drawn_connect.py -k bus -q`.
  2026-10-29: buses, entries and aliases (`expand`). Proof passed.

- [x] 3.3 Add net names (scenarios "Names in a child sheet", "Two global labels on one net"). Proof:
  `uv run pytest tests/unit/model/test_drawn_connect.py -k names -q`.
  2026-10-29: names; a global name wins at any depth, else the highest sheet, then code-point order. Proof passed.

- [x] 3.4 Add `compare`, the coverage check, the repeated-value check, `ISSUE_CODES` and their
  `explain.toml` entries (scenarios "A faithful drawing", "A wire moved to the wrong pin", "Name only",
  "Part added in code only", "Unused unit", "Different resistor per channel", "Two channels, one sheet",
  "Cycle refused", "Closed and explained"). Proof:
  `uv run pytest tests/unit/model/test_drawn_compare.py tests/unit/model/test_drawn_instances.py tests/unit/model/test_drawn_codes.py -q`.
  2026-10-29: `compare`, `coverage`, `ISSUE_CODES` and fifteen `explain.toml` entries; `drawn.net-name-differs` only when no label of the group carries the code net's name. Proof passed.

## 4. KiCad

- [x] 4.1 Add `sch.opaque_drawing` (scenario "Junctions of a read sheet"). Proof:
  `uv run pytest tests/unit/backends/kicad/test_sch_opaque_drawing.py -q`.
  2026-10-29: `sch.opaque_drawing`, `sch.opaque_sheet_pins`, `sch.symbol_field_poses`. Proof passed.

- [x] 4.2 Write the new entities, local labels, power symbols and opaque items in `sch.write_schematic`,
  with repeated sheets (scenarios "Every kind written", "Too-new opaque item", "Two channels"; the existing
  writer scenarios keep passing). Proof:
  `uv run pytest tests/unit/backends/kicad/test_sch_write_drawn.py tests/unit/backends/kicad/test_sch_write.py -q`.
  2026-10-29: writer entities, sheet pins, field poses (`DRAWN_EXT`) and opaque items through the emit gate; repeated sheets written once with one instance path per reference. Proof passed.

- [x] 4.3 Add `backends/kicad/drawn.py` with `lower_drawn` (scenarios "Same contract as the generator",
  "Deterministic ids"). Proof: `uv run pytest tests/unit/backends/kicad/test_drawn_lower.py -q`.
  2026-10-29: `lower_drawn`; wires cut at junctions and buses at entries (9.0.9 needs it). Proof passed.

- [x] 4.4 Add `extract`, opaque items and freezing (scenarios "Hand-drawn fixture", "Write and extract
  again", "Text kept", "Unknown symbol kept", "Frozen blink"). Proof:
  `uv run pytest tests/unit/backends/kicad/test_drawn_extract.py tests/unit/backends/kicad/test_drawn_freeze.py -q`.
  2026-10-29: `extract`/`extract_with_pins`, opaque items, freezing as extraction of the generated sheets. "Frozen blink" equals the generated texts except label, wire and flag uuids (decided in design.md, spec amended); the board is byte-equal. Proof passed.

- [x] 4.5 Complete the KiCad project import prerequisite: retain the parsed hierarchy, vendor its real
  embedded source symbol definitions and power definitions with native slots and hidden power pins,
  select project instance references, extract using the final component paths, and emit
  `schematic.toml`/`load_schematic`. Refuse conflicting definitions or unsupported source poses before
  staging. Build the imported drawing in the self-check so the actual written-byte connectivity guard
  runs; preserve board-only bytes and source files. Keep all c0278 levels and planted-junction assertions.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py -q`;
  `uv run pytest tests/unit/importer/test_vendor.py tests/unit/importer/test_sheets.py tests/unit/lens/test_build_drawn.py tests/unit/lens/test_build_drawn_guard.py tests/unit/backends/kicad/test_symembed.py -q`.
  2026-11-01: `Source.hierarchy` already retained the parsed sheets; the emitter now preserves native
  definitions, extracts using final component paths, and self-checks a written drawing. The focused
  importer/CLI/drawn/serializer/layering selection passed 199 tests; its one skipped deterministic
  formatting case then passed with the installed venv's `ruff` on PATH. The 19 new cases cover strict
  all-nine-level equality on sensor/flat/full/hier/bus/repeat with copper actually compared, native
  graphics and hidden power pins, source collisions/unsupported poses, foreign project references,
  built-in-id precedence, reviewed input changes, written-wire faults, and four complete emission byte
  maps independently measured from clean `3da72066` for board-only input on targets 9/10. Three older
  hierarchy fixtures now keep their native drawing and consistent local/global labels instead of
  dropping geometry or orphaning board parts. Only `drawn@9` and `drawn@10` changed their schematic and
  symbol-library byte pins to retain hidden power pins; every other byte pin remained unchanged.
  Guide/byte selection: 77 passed; current census regression: 7 passed. Types, lint, format, generated
  guide/schema checks, residue and strict validation passed. Native Altium and exact-commit KiCad CI
  gates remain open under 6.2, 7.1 and 9.2.

- [x] 4.6 Refresh the authored `examples/import_python` snapshot through its existing exact import
  recipe after source drawing preservation, including canonical drawing, native symbols, provenance
  and manifest declarations. Keep the literal freshness assertion and build checks, and remeasure only
  that example's affected byte rows with their reason recorded.
  Proof: `uv run pytest tests/unit/test_examples.py -k import_python -q`;
  `uv run pytest tests/corpus/test_manifest.py tests/residue -q`;
  `uv run pytest tests/unit/test_build_bytes.py -k import_python -q`.
  2026-11-01: regenerated with unchanged `tests/_importexample.py` and its original stamped recipe.
  Exactly one produced file is added (`schematic.toml`), five change, and none is removed. Provenance
  keeps the same input hashes and drops the obsolete generated-drawing/symbol findings. The manifest
  declares the authored drawing and correctly describes the native symbol copy. Literal freshness and
  build: 2 passed; manifest/residue: 127 passed, 7 corpus-dependent checks not enabled in this focused
  run; the three explicitly remeasured `import_python` byte rows: 3 passed. No assertion was relaxed.
  Lint, formatting, residue scan and strict OpenSpec validation passed; runtime source is unchanged.

- [x] 4.7 Preserve mirrored source power symbols through extraction, canonical TOML, both KiCad
  lowerings and level S. Keep default canonical bytes and strict written connectivity checks.
  Proof: `uv run pytest tests/unit/backends/kicad/test_drawn_extract.py tests/unit/lens/test_drawn_file.py tests/unit/checks/equivalence/test_level_s.py tests/consistency/test_drawn_schema.py -q`;
  `uv run pytest tests/unit/importer/test_drawn_import.py -k mirrored -q`.
  2026-11-01: optional `DrawnPower.mirror` is preserved by canonical TOML, schema, extraction, native
  lowerings and pin transforms; level S compares it. The combined focused selection passed 169 cases,
  including four strict authored import/confirm/build/all-nine comparisons and an asymmetric rotated
  power-pin transform. Six drawn/import_python default byte guards remain unchanged. Lint, format,
  source types (zero diagnostics), schemas/guide generation, residue and strict validation passed.
  The historical public refusal census is unchanged; a new source snapshot needs a fresh strict run.

- [x] 4.8 Preserve legacy source power instances without a power flag only when the one hidden
  power-input pin at the origin supplies the same global name. Keep malformed lookalikes refused and
  prove actual strict import/confirm/build/all-nine equality without adding a native flag.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py -k legacy_power tests/unit/backends/kicad/test_drawn_extract.py -q`.
  2026-11-01: the narrow form uses the existing hidden-input global-net rule and keeps the source
  definition without a power flag. Eight focused cases passed: strict import/confirm/build/all-nine
  comparisons for both source majors, the positive extracted form and five malformed lookalikes
  (visible/signal/differently named/off-origin/extra pins). No unknown electrical symbol is accepted
  merely because its reference starts with `#PWR`. The complete two-file selection passed 54 tests;
  source types, lint/format, residue and strict validation passed.

- [x] 4.9 Preserve pinless excluded native graphic symbols as opaque drawing instances together with
  their resolved embedded definitions; keep unknown/electrical symbols refused. Prove strict
  import/replay/build/all-nine equality and refusal after a graphic definition gains an electrical pin.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py -k graphic_symbol tests/unit/backends/kicad/test_drawn_extract.py -q`.
  2026-11-01: opaque native instances use the existing schematic reader and project library resolver;
  lowering embeds their same slot-preserving definition. Six new cases passed: two strict all-nine
  round trips, refusal after a graphic gains an electrical pin, either excluded-instance flag removed,
  and malformed native pose reported as bad input. The importer/extractor/build/guard selection passed
  70 tests; the tested guide line, types (zero diagnostics), lint/format, generator check, residue and
  strict validation passed. No public census baseline or native acceptance was added.

- [x] 4.10 Vendor unqualified embedded aliases under their source instance's library namespace (or
  private `_Source` fallback), retaining native slots, power identity, poses and collision refusal.
  Prove strict ordinary/power alias round trips for both source majors without changing board-only or
  existing example bytes.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py -k embedded_alias -q`;
  `uv run pytest tests/unit/importer/test_drawn_import.py tests/unit/importer/test_vendor.py tests/unit/backends/kicad/test_drawn_extract.py -q`.
  2026-11-01: the shared source-identity helper qualifies bare aliases and preserves native slots.
  Eight strict all-nine round trips passed (ordinary/power/graphic aliases for both majors plus private
  fallback cases), and a bare/qualified canonical-id collision cannot bypass the definition cache.
  The importer/vendor/extractor selection passed 71 tests, including all four board-only byte maps;
  the unchanged literal example, three byte rows and guide line passed six tests. Source types (zero
  diagnostics), lint/format, generated guide, residue and strict validation passed. The original signed
  corpus snapshot is retained until an actual refreshed run; per-unit aliases remain separate work.

- [x] 4.11 Preserve native per-unit source aliases through an optional drawn-symbol library binding,
  with exact logical-unit pin compatibility, deterministic primary selection and same-unit conflict
  refusal. Bind extraction to code during build/check/sync, retaining single-unit overrides and
  pin-pad variants. Keep default canonical bytes and all strict fidelity levels.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py tests/unit/backends/kicad/test_drawn_extract.py tests/unit/lens/test_drawn_file.py tests/unit/checks/equivalence/test_level_s.py tests/unit/lens/test_sync_drawn.py tests/unit/lens/test_build_drawn_guard.py tests/consistency/test_drawn_schema.py -q`.
  2026-11-01: the exact combined proof passed 122 tests. Twelve new cases cover strict all-nine
  per-unit alias round trips and sync with both source majors/native output targets, same-unit and
  logical-pin conflicts, canonical/schema/type checks, level S identity, single-unit overrides with
  and without swapped pad mappings, missing/incompatible build bindings, and a moved native pin caught
  by the actual written-net guard. Sync/rebuild keeps the same native sheet bytes in the mapping
  controls. Nine default literal/example/byte/guide cases passed; all board-only maps are unchanged.
  Source types (zero diagnostics), lint/format, generated guide/schemas, residue and strict validation
  passed. No public corpus observation or native acceptance baseline was changed.

- [x] 4.12 Honor explicit board/BOM exclusions on pinless source instances even when their library
  defaults include them. Preserve the default flags and native body, with electrical lookalikes still
  refused. Prove strict all-nine round trips for each differing default combination on both source majors.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py -k 'graphic_symbol or graphic_instance' -q`.
  2026-11-01: 12 cases passed, including six new strict all-nine round trips for differing library
  defaults on both source majors. Native default flags and explicit instance exclusions remain intact;
  electrical/board/BOM/malformed lookalikes still refuse. Types (zero diagnostics), lint/format,
  residue and strict validation passed. This follows the actual 13-row probe on signed `abf0cf0e`,
  which failed 13 cases in 234.84s (two validation, six unexpressed-content and five build-guard
  refusals); no baseline or comparison acceptance was inferred from that failed source snapshot.

- [x] 4.13 Preserve a common code-module prefix on root-sheet parts instead of treating the root as
  a child module. Keep child relative paths unchanged and prove strict root-module import/build/all-nine
  equality for both source majors.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py -k root_module -q`;
  `uv run pytest tests/unit/backends/kicad/test_drawn_extract.py tests/unit/model/test_drawn_instances.py -q`.
  2026-11-01: two strict all-nine source-major round trips passed with every root-sheet part in one
  named code module. The existing extractor/instance group passed 32 cases; child relative paths are
  unchanged. Source types (zero diagnostics), lint/format, residue and strict validation passed.

- [x] 4.14 Keep a uniquely matched active source symbol despite native PCB board-only metadata,
  preserving the attribute independently. Retain duplicate/invalid/unmatched keyed behavior and strict
  electrical checks. Coordinate the tiny emitter hunk after the c0318 identity checkpoint.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py -k 'native_board_only or keyed_board_only' -q`;
  `uv run pytest tests/unit/importer/test_board_items.py tests/unit/importer/test_drawn_import.py -q`.
  2026-11-01: three focused guards passed, including strict import/build/all-nine equality on both
  source majors and duplicate/unmatched refusal semantics. The combined source/board group passed
  62 cases; native attributes survived and source typing reported zero diagnostics.

- [x] 4.15 Resolve KiCad's native slash spellings in connection keys while preserving actual drawn text,
  generic/other-backend semantics, and strict code partition checks. Add authored positive and distinct-net
  collision proofs; rerun the original public PIC case without allowances.
  Proof: `uv run pytest tests/unit/backends/kicad/test_drawn_native_names.py tests/unit/importer/test_drawn_import.py -k 'native_name or slash' -q`;
  `uv run pytest tests/kicad/schematic/test_drawn_oracle.py -k slash -q`.
  2026-11-01: authored local/global alias and distinct-code-net guards passed, as did actual native
  alias exports on the installed KiCad 9.0.2 (two cases, no 9.0.9/10.0.6 claim). Sheet-pin and bus-member
  controls passed too (12 focused; 131 combined), source types reported zero diagnostics, and lint,
  format, generated-guide, residue and strict checks passed. The actual strict public rerun on signed
  `8b8b86f2661b280451d5903783ab9e08bb11ff06` failed two cases in 51.35s: both now pass import/build
  and level S; 10-pcb-12 is equal at 1–7, with two render differences, while 9-pcb-03 is equal at 1–6,
  with two field-pose and two render differences. All nine positive assertions remain; no acceptance
  or whole-fidelity/native-9.0.9/10.0.6 passing claim follows from those observations.

- [x] 4.16 Preserve explicitly board/BOM-excluded native visible passive instances without adding
  circuit nodes. Keep hidden/active/power definitions and missing exclusions strict. Prove authored
  all-nine round trips, the native common-pin partition and native absence of the excluded reference.
  Proof: `uv run pytest tests/unit/importer/test_drawn_import.py -k excluded_passive -q`;
  `uv run pytest tests/kicad/schematic/test_drawn_oracle.py -k excluded_passive -q`.
  2026-11-01: seven authored proofs passed, including strict all-nine round trips on both source
  majors and five malformed/active-form refusals. The native export control passed on installed
  KiCad 9.0.2: the excluded reference had no exported node and the common-pin partition was equal.
  Native 9.0.9/10.0.6 and whole-fidelity acceptance remain unproved here.
  The actual strict public 10-pcb-01 rerun on signed `6a6026051bae3902d881fababc36af91b785f5a9`
  failed in 11.96s: the R601 refusal was removed, and the next unmapped native instance M705 remains
  an explicit `FEN-3004` import refusal. No passing corpus row or accepted baseline was added.

## 5. DSL, build, check and sync

- [x] 5.1 Add `Design.load_schematic` and `dsl.drawn_schematic` (scenarios of "Drawn schematic in the
  DSL"). Proof: `uv run pytest tests/unit/dsl/test_load_schematic.py -q`.
  2026-10-29: `Design.load_schematic`, `dsl.drawn_schematic` (in `DSL_NOT_TAUGHT` as a build call). Proof passed.

- [x] 5.2 Build with a drawn schematic: reading in `cmd_build`, `lower_drawn` in `build_design`, the
  read-back guard, the result keys and `drawn.placements-ignored`; add `examples/drawn/` (authored, CC0)
  (scenarios of "Drawn schematic in a build", "Drawn schematic build guard", "Drawn schematic build
  result"). Proof:
  `uv run pytest tests/unit/lens/test_build_drawn.py tests/unit/lens/test_build_drawn_guard.py tests/unit/lens/test_build_bytes_pinned.py -q`.
  2026-10-29: `cmd_build` reads the file (`FEN-3004`), `build_design(drawn=)` lowers it, the read-back guard (`drawn_netlist_issues`), `result.schematic.source`/`drawn`, the build record's `schematic`, `drawn.placements-ignored`, `examples/drawn/`. Proof passed.

- [x] 5.3 Generated sheets inside a drawing (scenarios "Drawn top, generated block", "Missing pin").
  Proof: `uv run pytest tests/unit/lens/test_build_drawn.py -k generated -q`.
  2026-10-29: open: needs c0269's block rules, which are not merged. A `generated = true` sheet is read and left out of the coverage, and a build refuses it with `drawn.sheet-unknown` until c0269 lands.
  2026-10-30: done on c0269's block sheets: `lower_drawn(..., groups=)` runs the generator once and takes, for
  each instance of a `generated` sheet, the generator's sheet of its module and its sub-modules (byte-equal to
  a generated build), at `schgen.sheet_file(<module>)`, with their footprint paths, open-pin names and symbol
  definitions; the reference must carry the generator's sheet pins by name and shape
  (`drawn.sheet-pin-unmatched`), and the instance must stand at the module's place of the generated hierarchy
  (`drawn.sheet-unknown`). The resolver now joins a label standing on a sheet pin's point to that pin, as the
  block sheets draw them (row in `docs/formats/kicad/schematic.md`). Proof passed (2 tests); the KiCad check
  `test_generated_blocks_inside_a_drawing` in `tests/kicad/schematic/test_drawn_oracle.py` passed locally on
  `docker:kicad/kicad:10.0.6` (KiCad's partition equal, ERC clean).

- [x] 5.4 Add `checks/drawn.py`, the stage, its injection in `cmd_check` and its codes (scenarios of
  "Drawn schematic stage" and "Drawn schematic stage issue codes"). Proof:
  `uv run pytest tests/unit/checks/test_drawn_stage.py tests/unit/cli/test_check_drawn.py -q`.
  2026-10-29: `checks/drawn.py`, stage `schematic.drawn` after `parity`, injected by `cmd_check` (and `manifest`) for built input whose record names a drawn schematic, skip reason `no-drawing`. Proof passed.

- [x] 5.5 Sync of the drawn file and `--freeze-schematic` (scenarios of "Drawn schematic in the source
  tree" and "Drawn schematic sync refuses changed nets"). Proof:
  `uv run pytest tests/unit/lens/test_sync_drawn.py tests/unit/cli/test_sync_cmd.py -q`.
  2026-10-29: `lens.sync.plan_drawn`, `sync --freeze-schematic`, `result.drawn`; no `schematic-placements.toml` beside a drawn schematic. The c0250 interplay (`edits.toml`) is unchanged because c0250 is not merged. Proof passed.

## 6. Altium (phase that may be cut, open question 4)

- [x] 6.1 Add `backends/altium/drawn.py` and the lossy rules (scenarios "Drawn example in Altium",
  "Off-grid point", "Text dropped"). Record the record forms used in `docs/formats/altium/` with S-0185
  and their labels. Proof: `uv run pytest tests/unit/backends/altium/test_drawn_altium.py -q`.
  2026-10-29: open: the Altium writer phase is not implemented in this batch (open question 4).
  2026-10-30: still open: the Altium sheet writer (`schdoc.py`) writes from a composition `SheetPlan`, not
  from drawn geometry; drawn polylines, junctions, ports, sheet entries and power ports need a writer of
  their own and record forms from S-0185, a phase of its own that can follow this change.
  2026-11-01: implemented the native ASCII/binary drawn writer and final-byte guards. The authored
  proof passed 36 cases: all six fixtures in both forms, native component/unit/pin/document defects,
  physical maps, post-template wire faults, compatible/missing/incompatible unit aliases, alias-input
  review invalidation, exact pose geometry and explicit unsupported-pose findings. Source types
  reported zero diagnostics. Only `drawn@altium` and `import_python@altium` byte rows were refreshed;
  both retain their PCB, PCB library and symbol library hashes. The focused byte selection passed
  21 cases. Documentation/guide proofs passed 106 cases. Native Altium acceptance is not implied.

- [ ] 6.2 Add a kit step that compiles the drawn example and records the nets and messages
  (`H-A-DRAWN-WRITE`); the row stays `INFERRED` until the maintainer reports. Proof:
  `uv run pytest tests/unit/test_altium_verification_docs.py -q`.
  2026-10-29: open: depends on 6.1 and the maintainer's kit.
  2026-10-30: still open (6.1, then the maintainer's Altium).
  2026-11-01: the concrete compile/export/save kit is documented and its metadata proof passed.
  The maintainer reports Altium unavailable, so actual application acceptance and this gate remain
  open; `H-A-DRAWN-WRITE` stays `INFERRED`. No old author report is reused as a drawn-sheet result.
  2026-11-02: actual Altium 22.2.1 compiles all six authored original cases;
  complete native pin partitions equal code, including after new-copy native
  save/reopen. c0331 repairs the full fixture's invalid bus alias and proves a
  connected boundary plus an independently broken native control. Original
  source ERC and raw name findings remain, so the no-connectivity-message
  criterion and this task stay open. See `docs/evidence/altium-drawn-native.md`.

- [x] 6.3 Author an independent native clean-ERC bus acceptance control with explicit
  intentional no-connects ONLY on the two truly unused input pins U1-11/U1-12.
  Preserve the full40-pin universe, all connected bus groups and original source
  findings. Build both Altium forms and verify the two exact native marker positions;
  compile/export/save/reopen the isolated controls and record every message/name.
  Retain the independent broken-bus full-partition negative. This control does not
  retroactively pass the original examples or suppress messages on connected pins.
  Proof: focused authored writer controls and actual source-bound native receipts.
  2026-11-03: actual Altium24.5.2.23 on writerda89051f compiles both marked forms with
  full40pins/36groups/zero declared-name differences and Info1 only. Unmarked retains2 errors/
  2 warnings, and NAME-only broken bus retains all40pins but40groups/4 name differences/14errors.
  Four new-copy native binary documents were saved, closed/reopened and both projects recompiled
  with identical complete partitions/all36 native short/full names and Info-only logs. Both exact
  marker positions/flags/symbols and all60 source inputs are unchanged. Receipt:
  `docs/evidence/altium-clean-drawn-native.json`; narrative: `docs/evidence/altium-drawn-native.md`.
  This passes only the independent6.3 control: original6.2 findings and H-A-DRAWN-WRITE INFERRED
  remain, as do exact-head9.2 CI and the other literal gates.

- [x] 6.4 Reproduce the current original example's actual native24 findings, then implement the approved authored correction: R3-2 terminates the input chain at GND, intentional no-connects only on unused U1-11/U1-12, and local IN label on the existing root wire. Preserve all38pins/four components/33groups and native writer behavior, with independent full membership/name checks, both forms, actual native save/reopen, immutable original inputs and focused authored regressions. Never change global ERC settings or reuse6.3 as a retroactive original pass. Exact-head CI and other original fixture findings remain separate.
  Preserve complete old/new deterministic plans before updating only the three drawn example byte rows. The intentional source circuit change moves R3-2 from VCC to GND, so its PCB/board/circuit bytes legitimately change alongside root/child schematics; all library/project/rule/manufacturing hashes and every unrelated example row stay fixed. Do not refresh an unmeasured file or weaken the complete-file assertion.
  2026-11-03 partial proof: original current963 actual24.5.2.23 reproduces38pins/33groups, IN naming and3Error/2Warning. Authored regression3fails before and3passes after. Corrected binary/ASCII both retain every38pins/33groups with names exact and Info1 only. Four native binary documents saved/closed/reopened retain exact marker positions/flags; saved binary full recompile/export also passes. Saved ASCII export remains incomplete on operator I/O32 at stage.txt append, with no CAD-failure or completed-export claim. Before retry, consciously stop the paused owned SDK and prove an immutable-event/final-marker I/O protocol; do not poll an actively appended file. Receipt and sourceS-1295 are separate from6.3. Focused neighbors78pass; actual KiCad9/10 example oracle/load2passes each. All45original/30save-source hashes remain unchanged at collection. The three source-driven byte rows pass with complete old/new maps retained. Keep6.4/6.2 and exact-head CI OPEN.

- [ ] 6.5 Repair the original FULL authored circuit after source-bound current24 baseline capture. Add real R3/R4 10k pull-down terminals to B0/B1 and GND, keeping all36 old pins and explicitly measuring the complete40pin/five-component universe; retain32groups. Keep existing11 NC, declare only actually unused11/12, add the missing12 drawn marker, and label IN on its existing wire. Preserve all drawn item kinds and exact buses/entries/hierarchy/poses. Start with authored RED regression, then focused code/drawn/native-record proofs and actual binary/ASCII compile/export/save/reopen. No connected NoERC, global ERC/scope change, pin filtering, comparator renaming or broad byte refresh. Record every native message/name and keep historical failures/independent6.3 separate.
  Coordinator design review approved2026-11-03; current24 baseline and implementation proofs remain pending. No source fixture was edited before this task/design.

- [ ] 6.6 Propose and prove canonical code-net preference for repeated local labels ONLY under a complete physical group↔circuit-net bijection and casefold-unique native identity. Preserve existing explicit fallback/refusal and label-text-change info for ambiguity/collisions, plus all8pins/five groups and local isolation. Establish RED positive FB0/FB1 and negatives for missing/unmatched/ambiguous groups, duplicate names, global/power collision and ordinary-sheet behavior before runtime. Never change the native comparator, measured results, net scope or ERC policy. Actual native both forms/save-reopen and inventoried byte effects are separate required proofs.
  Coordinator approved the narrow proposal direction2026-11-03; binding-carrier design and RED controls must be reviewed before runtime. Current __local_<id>_FB behavior remains explicit and unchanged.

  2026-11-03 local6.5 checkpoint: authored RED1failed0.88s before source edits; after repair3focused pass1.97s, including all40native records/all physical refs+pins and exact code memberships in both forms. Focused neighbors89pass10.55s. Actual KiCad9.0.9 and10.0.6 FULL export/load2cases each pass2.77s/3.07s; obsolete9 label_dangling exception removed, with no replacement waiver. Complete old binary/ASCII reviewed plans(15files each, source6de40c69) were preserved before edit. Actual Altium24 baseline/final compile/export/save/reopen and wider6.2/CI remain pending; task6.5 stays unchecked.


  2026-11-03 follow-up6.5: the style-loss control previously replaced the whole FULL power-port
  collection while styling its first port. Preserve every remaining authored power port so the new
  R3/R4 pull-down returns stay connected. Keep the strict refusal and explicit-loss acceptance
  assertions unchanged; this is test setup repair, with no writer or loss-policy change.
  Proof: `PYTHONPATH=src uv run pytest tests/unit/backends/altium/test_drawn_fonts.py -q`.


  2026-11-03 local6.6 implementation: reviewed RED first proves all8 covered pins/five groups and
  fails only the two qualified FB names in both forms. The ephemeral complete-group carrier then
  passes16 focused cases, including partial cross-sheet canonical membership, all ambiguity/name
  controls, three complete native fallback partitions and ordinary-sheet byte equality. The native
  comparator/ERC policy are unchanged; text rewrites retain their explicit informational notice.
  Native KiCad9.0.9 and10.0.6 repeated fixture export/load each pass2 cases. Exact parentcd69b353
  drawn module versus new lowering yields75 complete deterministic plans/1011 files with zero
  differences; both full maps are retained externally. The historical byte guard currently passes74
  and fails2 Altium PCB rows identically with the parent and new lowering; no golden is refreshed.
  Actual Altium24 both forms/save-reopen, coordinated check-fast and exact-current-head CI remain
  pending. Task6.6 remains unchecked.

- [x] 6.7 Isolate the repeated-name caller tests in temporary source copies with the authored Mini library tables. Prove the original fixture file map stays unchanged and no generated design.lock enters tests/data; preserve every physical/name/fallback assertion. Proof: `uv run pytest tests/unit/backends/altium/test_drawn_repeat_names.py tests/unit/backends/altium/test_drawn_fonts.py tests/unit/test_build_bytes.py tests/corpus/test_manifest.py -q` —176 passed (19.36s), including all76 complete default byte guards; every repeat-test teardown compares the original fixture's complete file map. The previously generated untracked resolver lock is preserved externally, never committed; the source tree gains no lock or cache. Ruff/format and strict OpenSpec pass. Full fast/exact CI and native24 remain separate pending gates.

## 7. Evidence

- [ ] 7.1 KiCad CI job: compare the resolver with `kicad-cli sch export netlist` on the authored drawn
  fixtures and the demo schematic rows, and load and ERC the written drawn fixtures (scenarios "Oracle on
  9.0 and 10.0", "KiCad loads the drawn sheets"). Raise each hypothesis to `KICAD-VERIFIED (9.0.x,
  10.0.x)` only after the job passes. Proof: the KiCad job of the commit on GitHub CI is green;
  `uv run pytest tests/kicad/schematic/test_drawn_oracle.py tests/kicad/schematic/test_drawn_corpus.py -rA` there.
  2026-10-29: `tests/kicad/schematic/test_drawn_oracle.py` (resolver against `sch export netlist`, and ERC of the written sheets; one file for both scenarios) passed locally on `docker:kicad/kicad:9.0.9` and `:10.0.6`: connectivity and names equal on all six fixtures. Open: CI runs with the batch; the probes are not registered and no level is raised before the CI job passes.
  2026-10-30: `test_generated_blocks_inside_a_drawing` added to the same file; the file passed locally on
  `docker:kicad/kicad:10.0.6` (13 tests). Still open: CI runs with the batch; no 9.0.9 image here today.

- [ ] 7.2 Extract each demo schematic row of the corpus into a temporary folder, lower it, resolve it and
  record counts and timings in `docs/evidence/drawn-schematic.md` (row ids, kinds and counts only; no
  derived file is kept). Verify cached manifest hashes, compare full original/lowered/native pin
  partitions and record naming outcomes/refusals separately. Preserve per-row census JSON even on
  failure; no accepted differences or loss flag. Proof: `uv run pytest tests/kicad/schematic/test_drawn_corpus.py -rA` in both required
  KiCad jobs, with actual per-row reports and version-bound evidence.
  2026-10-29: open: the corpus is not fetched in this environment; `test_drawn_corpus.py` is not written.
  2026-10-30: still open for the same reason (no corpus here); it belongs to the KiCad job.
  2026-11-01: the declared cache is now available. Strict source-followup runs are recorded above,
  with source refusals and presentation/render differences still visible. The separate all-demo
  extract/lower/native-oracle harness and its exact-job proof remain unfinished; no passing corpus
  result or accepted baseline is inferred from the source followups.
  2026-11-02 continuation: the external cache is available. The new driver and local measurement
  follow the dated design decision. Local 9.0.2 results, explicit refusals or a completed census
  do not establish native 10.0.6 equality or close this literal CI proof.
  The actual failed `9c44f7a2` measurement and its limits are recorded under 7.3 below.
  2026-11-02 owner-context replay: the clean signed `ce3b999244af8e6a246f9457289ef6b5023bba05`
  producer, all 132 schematic and 54 project hashes verified, actual native 9.0.2: 41 failed,
  51 passed, 38 incompatible-tag skips in 1276.45 s (exit 1). All 130 per-row records and owner
  instance maps are in `docs/evidence/drawn-context.json`. Thirty-six VME rows retain the real
  owner's conflicting-definition refusal; five formats remain below the reader floor. All 51
  compared row contexts match in all three complete partition comparisons; 21 row contexts
  still have naming warnings. Missing comparisons are not zero differences. There are no
  missing/invalid cache cases, internal errors or retained CAD files. The earlier `695dee0f`
  diagnostic and byte-identical `9c44f7a2` artifact remain separate. Task 7.2 remains open for
  source coverage and actual required versioned CI; neither native 10 nor full CI is claimed.

- [x] 7.3 Implement and prove the census driver/comparison/privacy controls with authored CC0 inputs,
  preserving every production drawn/model field and strict native contract; retain the actual measured
  result and any remaining refusal/mismatch instead of marking 7.2 from code completion.
  Proof: `uv run pytest tests/unit/test_drawn_census.py -q`;
  `uv run ruff check .`; `uv run ruff format --check .`;
  `npx -y @fission-ai/openspec validate c0276-drawn-schematic --strict`.
  Local driver proof 2026-11-02: 61 authored/workflow cases passed in 6.32 s, including real
  lowering of flat, hierarchical, full, bus and repeated authored fixtures with stubbed native
  boundaries, strict native-only-node/singleton controls, hash-before-parser checks and refusal
  privacy. A separate real KiCad 9.0.2 flat prototype matched all three partition comparisons.
  Whole-tree lint/format, source types (0 errors/warnings), guide, public residue (0 hits; 16
  existing waivers) and strict validation pass. Production/model/schema/S fields are unchanged.
  This local proof does not close 7.2; the source-bound actual corpus measurement follows the
  clean harness commit; the actual source-bound result follows below.
  Source-bound measurement 2026-11-02 on signed `9c44f7a224790b31ccbe017a0cce4c059b8c9b25`,
  native KiCad 9.0.2: the literal 130-row driver completed with 76 failed, 16 passed and 38
  incompatible-tag skips in 158.13 s (exit 1). All reports are recorded in
  `docs/evidence/drawn-schematic.json` and summarized in the evidence page: 16 connectivity-equal,
  six different, 50 explicit refusals, 20 missing compatible cache entries, 38 incompatible tags;
  zero internal errors and zero retained CAD files. Original-native comparisons exist for 69 rows,
  lowered-native comparisons for 22. The normal-sandbox fetcher could not fill the missing cache
  (EPERM; no new permission request). This records actual limits, not accepted loss or a CI pass.
  The driver/comparison/reporting work of 7.3 is complete; 7.2 remains open for the failing cases,
  complete inputs and actual required 9.0.9/10.0.6 jobs. Altium 6.1/6.2 remains independent.

- [x] 7.4 Preserve each corpus row's real owning-project and repeated-instance context. Discover every
  registered root that reaches a child, hash all declared inputs before discovery, measure the full
  owner hierarchy and record per-row owner/export-root/instance bindings. Keep standalone/orphan,
  missing, unsupported and ambiguous contexts explicit; do not remove a row, pin or finding.
  Fetch the declared owner project inputs in both KiCad jobs and require their exact hashes.
  Proof: `uv run pytest tests/unit/test_drawn_census.py tests/unit/test_drawn_context.py tests/unit/test_drawn_context_evidence.py -q`;
  `uv run pytest tests/kicad/schematic/test_drawn_context.py -q` on the actual installed CLI.
  Record the cache-complete `695dee0f` leaf-root run separately before a fresh context-correct rerun.
  This driver proof does not close task 7.2's strict corpus equality in both required CI jobs.
  Passed locally 2026-11-02: the literal authored/hash/context proof passes 26 cases in 4.21 s;
  both native child-port/repeated-root controls pass on actual KiCad 9.0.2 (2 cases in 4.94 s).
  The workflow/context group passed 72 cases before the two additional dispatch regressions;
  those new controls prove the actual corpus dispatcher exports its owner root and refuses a
  missing project before native execution, retaining the row and cleaning copied CAD. All 49
  post-lowering guards in the earlier `695dee0f` run were artificial child-as-root contexts;
  native owner selection does not weaken any production resolver, reader-floor or definition guard.
  The 130-row source-bound rerun and its exact required CI proof remain task 7.2, unchecked.
  The final combined authored/workflow group passed 74 cases in 5.72 s; four existing
  source-conflict, incompatible-binding and electrical-pin guards passed in 5.54 s. The
  source-bound local measurement remains failed as recorded under 7.2; artifact-integrity
  controls verify both new observations and preserve the original historical artifact hash.
  The expanded literal proof, including artifact-integrity controls, passes 28 cases in 5.58 s.

## 8. Documentation and guide

- [x] 8.1 Write `docs/drawn-schematic.md`, and update `docs/dsl.md`, `docs/schematic.md` and
  `docs/lens.md` (scenario "Pages cover the names"). Proof: `uv run pytest tests/consistency -q`.
  2026-10-29: `docs/drawn-schematic.md`, `docs/dsl.md`, `docs/schematic.md`, `docs/lens.md`, `docs/cli-contract.md`, `docs/index.md`. Proof passed.

- [x] 8.2 Agent guide (AGENTS.md rule 6): a tested line for `load_schematic` on the page `design-script`
  and for the stage and its codes on the page `checks`; regenerate the generated pages. Proof:
  `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-10-29: `load_schematic` and `sync --freeze-schematic` are taught on the page `files` (a tested `fenolite-cmd` line), not `design-script`, which is at 11 985 of its 12 000 bytes; the stage row is on `checks`; generated pages regenerated. Proof passed.

## 9. Changelog and CI

- [x] 9.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit -k changelog -q`.
  2026-10-29: one entry under `## [Unreleased]` (dev is at 0.7.0.dev0). Proof passed.

- [ ] 9.2 `make check-fast` passes locally; publish the batch to its working branch and confirm the unit
  and KiCad jobs on the exact commit. Proof: `make check-fast`; the required CI jobs are green on the
  commit.
  2026-10-29: open: CI runs with the batch. `make check-fast PYTEST_WORKERS=2`: lint, format, pyright and residue pass; the tests pass except two failures present on the base commit `a170bc55` (`tests/unit/test_altium_rows.py::test_rows_are_well_formed` on the row of c0269's proposal, since renamed `H-A-BLOCK-ENTRIES`, and `tests/unit/lens/test_altium_build.py::test_evidence`), not touched by this change.
  2026-10-30: `make check-fast PYTEST_WORKERS=2` on the finished batch: lint, format, pyright and residue
  pass; the tests gave 16 954 passed, 50 skipped and one failure (`test_package.py::test_modules`, the module
  list lacked `drawn.py` in order), fixed and passed after; lint, format, pyright and residue re-run clean.
  Open: CI runs with the batch.

Native7.2 local observation, 2026-11-03: complete clean-sourceb50fd0f0 runs
finish on9.0.9 (92passed/38version skips,87equal/5explicitfloorrefusals) and
10.0.6 (114passed/16version skips,113equal/1explicitfloorrefusal), bothexit0.
`docs/evidence/drawn-native-census-20261103.json` preserves per-row/context
counts, naming differences, findings and raw receipt/log digests. The source
checkout remains clean and unchanged. Task7.2 stays unchecked pending the
required exact-current-source CI; naming differences are not silently accepted.

  2026-11-03 completion of6.4: the user consciously stopped the paused owned SDK. Independent Windows I/O control reproduced sharing error32 and passed1000 existence-only marker checks with closed-export hash exact, without touching CAD. Fresh ASCII-saved-v2 uses immutable unique events and zero active-stage reads. Actual Altium24.5.2.23 exports all38pins/33groups/all declared names exactly with Info1 only, identical partitionSHA to both corrected source forms and saved binary. No successful case was repeated; historical I/O32 remains recorded. Task6.4 native scope is complete; wider6.2, other original fixtures, H-A-DRAWN-WRITE and exact-head CI remain OPEN. Proof: focused original acceptance and verification metadata tests.
