## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `design-model`,
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

- [ ] 2.3 Author the fixtures `tests/data/drawn/{flat,full,hier,bus,repeat}/` (CC0, authored for
  Fenolite, each with its design script) and declare them in `tests/data/MANIFEST.toml` with
  `origin = "authored"`. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py -q`.
  2026-10-29: `tests/data/drawn/{flat,full,hier,bus,repeat}/` and `examples/drawn/` (design script, `schematic.toml`, library tables naming the authored mini library), declared in the manifest. `tests/residue` passes; `tests/corpus/test_manifest.py` fails only on `examples/lock/design.lock` and `examples/lock/design.py`, undeclared by c0249 before this change (not touched here, for a clean merge).

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

- [ ] 5.3 Generated sheets inside a drawing (scenarios "Drawn top, generated block", "Missing pin").
  Proof: `uv run pytest tests/unit/lens/test_build_drawn.py -k generated -q`.
  2026-10-29: open: needs c0269's block rules, which are not merged. A `generated = true` sheet is read and left out of the coverage, and a build refuses it with `drawn.sheet-unknown` until c0269 lands.

- [x] 5.4 Add `checks/drawn.py`, the stage, its injection in `cmd_check` and its codes (scenarios of
  "Drawn schematic stage" and "Drawn schematic stage issue codes"). Proof:
  `uv run pytest tests/unit/checks/test_drawn_stage.py tests/unit/cli/test_check_drawn.py -q`.
  2026-10-29: `checks/drawn.py`, stage `schematic.drawn` after `parity`, injected by `cmd_check` (and `manifest`) for built input whose record names a drawn schematic, skip reason `no-drawing`. Proof passed.

- [x] 5.5 Sync of the drawn file and `--freeze-schematic` (scenarios of "Drawn schematic in the source
  tree" and "Drawn schematic sync refuses changed nets"). Proof:
  `uv run pytest tests/unit/lens/test_sync_drawn.py tests/unit/cli/test_sync_cmd.py -q`.
  2026-10-29: `lens.sync.plan_drawn`, `sync --freeze-schematic`, `result.drawn`; no `schematic-placements.toml` beside a drawn schematic. The c0250 interplay (`edits.toml`) is unchanged because c0250 is not merged. Proof passed.

## 6. Altium (phase that may be cut, open question 4)

- [ ] 6.1 Add `backends/altium/drawn.py` and the lossy rules (scenarios "Drawn example in Altium",
  "Off-grid point", "Text dropped"). Record the record forms used in `docs/formats/altium/` with S-0185
  and their labels. Proof: `uv run pytest tests/unit/backends/altium/test_drawn_altium.py -q`.
  2026-10-29: open: the Altium writer phase is not implemented in this batch (open question 4).

- [ ] 6.2 Add a kit step that compiles the drawn example and records the nets and messages
  (`H-A-DRAWN-WRITE`); the row stays `INFERRED` until the maintainer reports. Proof:
  `uv run pytest tests/unit/test_altium_verification_docs.py -q`.
  2026-10-29: open: depends on 6.1 and the maintainer's kit.

## 7. Evidence

- [ ] 7.1 KiCad CI job: compare the resolver with `kicad-cli sch export netlist` on the authored drawn
  fixtures and the demo schematic rows, and load and ERC the written drawn fixtures (scenarios "Oracle on
  9.0 and 10.0", "KiCad loads the drawn sheets"). Raise each hypothesis to `KICAD-VERIFIED (9.0.x,
  10.0.x)` only after the job passes. Proof: the KiCad job of the commit on GitHub CI is green;
  `uv run pytest tests/kicad/schematic/test_drawn_oracle.py tests/kicad/schematic/test_drawn_write_oracle.py -rA` there.
  2026-10-29: `tests/kicad/schematic/test_drawn_oracle.py` (resolver against `sch export netlist`, and ERC of the written sheets; one file for both scenarios) passed locally on `docker:kicad/kicad:9.0.9` and `:10.0.6`: connectivity and names equal on all six fixtures. Open: CI runs with the batch; the probes are not registered and no level is raised before the CI job passes.

- [ ] 7.2 Extract each demo schematic row of the corpus into a temporary folder, lower it, resolve it and
  record counts and timings in `docs/evidence/drawn-schematic.md` (row ids, kinds and counts only; no
  derived file is kept). Proof: `uv run pytest tests/kicad/schematic/test_drawn_corpus.py -rA` in the
  KiCad job.
  2026-10-29: open: the corpus is not fetched in this environment; `test_drawn_corpus.py` is not written.

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
