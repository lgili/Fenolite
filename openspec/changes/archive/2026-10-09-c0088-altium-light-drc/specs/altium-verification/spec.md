## MODIFIED Requirements

### Requirement: Check on Altium inputs
`fenolite check PATH` SHALL check an Altium document, project file or project folder as document input (`verification-loop`, "Check command input"), read-only and without any external tool.
- **Path.** A missing path MUST exit 3 with `FEN-3001`. A folder that holds Altium files, no KiCad project or board, and not exactly one project file MUST exit 2 with `FEN-2001` and a hint that lists the candidates.
- **Built or native.** The input MUST be built when `<root>/.fenolite/meta.json` or `<root>/.fenolite/build.json` exists, `<root>` being the set's root, and native otherwise. The built model MUST be loaded with `model.canonical.load_dir`; a failure gives the `cache_error` of the pipeline.
- **Stages.** Without `--stages`, every stage of `DOCUMENT_STAGES` MUST be selected. An unknown or empty stage name MUST exit 2 with `FEN-2001` and a hint that lists `DOCUMENT_STAGES`.
- **Result.** `result.project` MUST hold `backend` (`altium`), `project` and `board` (names or `null`), `built`, `files` (the sorted document names), `documents` (objects `{name, kind, role}` sorted by name) and `skipped` (objects `{name, reason}` with reason `missing`). `result.stages` MUST hold one object per selected stage. `input` MUST describe the file that `PATH` names, or the project file for a folder, with its name relative to the root, its SHA-256 and its read kind.
- **Exit codes.** 0 without an issue of severity `error`, 5 (`FEN-5001`) with one, and never 6. When `CheckReport.read_error` is set, the command MUST exit 3 with that error's FEN code by raising `cmd_check.ReadRefusedError` with `issues = CheckReport.issues`, as for a KiCad board.
- **Read-only.** "Check is read-only" applies: the snapshot of the project folder MUST be equal before and after, no `.fenolite/` entry MUST be created, and no subprocess MUST run.
- **Determinism.** "Check output is deterministic" applies: two runs give the same stdout apart from `elapsed_ms`, with names relative to the root.

#### Scenario: Own project is clean
- **WHEN** `uv run fenolite check tests/data/altium/blink/blink.PrjPcb --json` runs
- **THEN** the exit code is 0, `result.project.backend` is `altium`, `result.project.board` is `blink.PcbDoc`, `result.project.built` is `false`, the stages `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0` and `roundtrip.rta1` have status `ok`, `copper.clearance` reports no short and no clearance finding, every count of `parity` is 0, the pair is (`schematic`, `pcb`) with 0 differences, and `roundtrip.rta2` is skipped with reason `native-input`

#### Scenario: One library alone
- **WHEN** `fenolite check tests/data/altium/blink/blink.PcbLib --json` runs
- **THEN** the exit code is 0, `roundtrip.rta0` and `roundtrip.rta1` have status `ok`, `model.validate` reports no issue and is skipped with reason `not-judged` (a library gives no reading to judge), `erc.lite` and `parity` are skipped with the reason `no-schematic`, and `copper.clearance` and `netlist.assignment_compare` with `single-source`

#### Scenario: Unreadable single document
- **GIVEN** a copy of `blink.PcbDoc` in `tmp_path` cut to 100 bytes
- **WHEN** `fenolite check <copy> --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the envelope on stdout has `ok` false and `issues` holding one `check.read-refused`

#### Scenario: Project with one unreadable document
- **GIVEN** a copy of the blink project whose `blink.PcbDoc` is cut to 100 bytes
- **WHEN** `fenolite check <folder> --json` runs
- **THEN** the exit code is 5, the first issue is `check.read-refused` with a `where` that starts with `blink.PcbDoc`, and `netlist.assignment_compare` is skipped with reason `single-source`

#### Scenario: Read-only and without tools
- **GIVEN** a copy of the built blink project, with `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_check_readonly.py -k altium` runs `check` and `inspect` on it
- **THEN** each snapshot of the folder is equal before and after, and no subprocess ran

#### Scenario: Two runs are equal
- **WHEN** `fenolite check tests/data/altium/blink --json` runs twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`, and hold no absolute path

### Requirement: Altium check stage evidence
Each stage of an Altium check SHALL carry its own evidence, and the envelope SHALL combine them as "Document check pipeline" says.

| stage | evidence |
|---|---|
| `model.validate`, native | `Evidence.combine` of the readings judged |
| `model.validate`, built | `INFERRED` (Fenolite's structural rules) |
| `erc.lite`, native | `Evidence.combine(erc_lite.EVIDENCE, <schematic reading>, stage_evidence()["erc.lite"])`, which adds `H-A-VER-ERC` |
| `erc.lite`, built | `erc_lite.EVIDENCE` |
| `copper.clearance` | `Evidence.combine` of the PCB reading, of `checks.copper.EVIDENCE`, of `DesignRules.evidence` and of `stage_evidence()["copper.clearance"]`, which adds `H-A-DRC-SAME`; `UNVERIFIED` when the stage reports `copper.rules-incomplete` or `copper.item-unsupported` |
| `parity` | `Evidence.combine(parity.EVIDENCE, SideOutcome.evidence, <both readings>, stage_evidence()["parity"])`, which adds `H-A-DRC-PARITY` |
| `netlist.assignment_compare` | `Evidence.combine` of the readings compared and of `stage_evidence()["netlist.assignment_compare"]`, with `INFERRED` on built input; its hypotheses hold c0043's `H-A-IMP-NETLIST` |
| `roundtrip.rta0` | the evidence of the judged verdicts, `EVIDENCE_RT_A0`; `UNVERIFIED` when the stage reports `check.rta0-failed` |
| `roundtrip.rta1` | the evidence of the judged verdicts, `EVIDENCE_RT_A1` of their kinds, combined; `UNVERIFIED` when the stage reports `check.rta1-failed` |
| `roundtrip.rta2` | `INFERRED` with `H-A-VER-RTA2-2`, combined with the readings |

No stage MAY carry `ORACLE-VERIFIED`, `KICAD-VERIFIED` or `ALTIUM-VERIFIED`: no tool other than Fenolite reads the files in this command. The evidence comes from the backend, with each verdict (`ContainerRoundTrip.evidence`) and through `DocumentValidator.stage_evidence()`, so `checks` names no hypothesis of a backend.

#### Scenario: Levels on the own project
- **WHEN** `fenolite check tests/data/altium/blink/blink.PrjPcb --json` runs
- **THEN** no stage has a level above `CORPUS-VERIFIED`, `roundtrip.rta0` names `H-A-VER-RTA0` until that row is confirmed, and the envelope level is the lowest level of the stages that ran

#### Scenario: Failed copy lowers the stage
- **GIVEN** `cfb.write_compound` patched to drop one stream
- **WHEN** `fenolite check tests/data/altium/blink/blink.PcbDoc --stages roundtrip.rta0 --json` runs
- **THEN** the exit code is 5 and the stage level is `UNVERIFIED`

## ADDED Requirements

### Requirement: Document stage order
`checks.documents.DOCUMENT_STAGES` SHALL be `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0`, `roundtrip.rta1`, `roundtrip.rta2`, in this order, and every stage SHALL be a default stage that runs no external tool. `copper.clearance` and `parity` keep the relative order they have in `STAGE_ORDER`.

#### Scenario: Order
- **WHEN** `uv run pytest tests/unit/checks/test_document_copper.py -k stage_order` reads the tuple
- **THEN** it equals the list above

### Requirement: Copper check on Altium boards
On document input that holds a PCB document, the stage `copper.clearance` SHALL run `checks.copper.copper_stage` on the PCB reading with the rules that the backend gives for that document (`DesignRulesSource`) and its pads (`BoardFrame`), built and native input alike, through `checks.documents.document_copper`. The copper check judges shorts, clearance and zone-outline overlaps; it judges no board-edge clearance on any backend.
- The stage MUST be skipped with `single-source` when the documents hold no PCB document, and with `read-refused` when it could not be read.
- The findings MUST use the codes and severities of "Copper stage issue codes" of `verification-loop`, unchanged, and `summary` MUST hold the keys of that stage and two more counts, `unpoured` and `zones_unjudged`.
- **Rules.** Enabled `Clearance` records of the document that the rule table does not map MUST be counted in `summary.rules.opaque_clearance_rules` and MUST give `copper.rules-incomplete` (warning). Rule kinds that the copper check does not read (every kind but `Clearance`) MUST NOT give an issue of this stage: the import reports them.
- **Polygons.** A polygon with poured regions MUST be checked as a filled zone. A zone without a fill MUST be counted in `summary.unpoured`; when the count is not zero the stage MUST add one `copper.item-unsupported` (warning) with the count.
- **No invented clearance.** A polygon holds no clearance of its own, so the model's default zone clearance MUST NOT be judged. A filled zone for which no clearance is in force whatever the other item is (no rule, class or board minimum applies to copper of its net on a layer of its fills) MUST be counted in `summary.zones_unjudged`; when the count is not zero the stage MUST add one `copper.rules-incomplete` (warning, `where` = `zone`) with the count. Such a zone is still judged for shorts.
- **Planes.** What the rules source left out (`DesignRules.left_out`) MUST give one `copper.item-unsupported` (warning) per kind, `where` = the kind.
- The stage's evidence MUST be `UNVERIFIED` when it reports `copper.rules-incomplete` or `copper.item-unsupported`.

#### Scenario: A short on an Altium board
- **GIVEN** the routed blink whose script holds one more track of `LED_A` that crosses the track of `LED_DRV` on `F.Cu`, built for Altium with `--copper-check warn`
- **WHEN** `fenolite check <dir> --stages copper.clearance --json` runs
- **THEN** the exit code is 5 and one `copper.short` names the two nets

#### Scenario: Unpoured polygons are said
- **WHEN** `fenolite check tests/data/altium/routed --stages copper.clearance --json` runs (a built board with two unpoured polygons and no other fault)
- **THEN** the exit code is 0, it reports one `copper.item-unsupported` with the count 2, `summary.unpoured` is 2, and its evidence level is `UNVERIFIED`

#### Scenario: A pour without a clearance rule
- **GIVEN** a board model with one filled zone, no clearance rule, and a track of another net 0.3 mm from the fill
- **WHEN** `uv run pytest tests/unit/checks/test_document_copper.py -k default` runs the stage
- **THEN** it reports no `copper.clearance`, one `copper.rules-incomplete` that counts 1 zone, `summary.zones_unjudged` is 1, and the level is `UNVERIFIED`

#### Scenario: Same board, two backends
- **WHEN** `uv run pytest tests/kicad/altium/test_copper_same.py` checks the routed blink built for KiCad and for Altium, as built and with a planted short, a planted clearance fault and both
- **THEN** the copper findings of the two readings are equal by kind, net pair and place within 2 nm

#### Scenario: Public documents
- **WHEN** `uv run pytest tests/corpus/test_altium_copper.py -k copper` runs the stage on every public PCB document
- **THEN** no finding has the source `zone`, a document without a mapped `Clearance` rule has no clearance finding, and every finding that the 5 nm slack removes is short by 5 nm at most

### Requirement: Board frame of an imported board
`AltiumBackend` SHALL satisfy `BoardFrame` (`backend-protocol`), through `fenolite.backends.altium.frame`: `board_pads(design)` gives one `BoardPad` per pad of every footprint of an imported board, and `placed_extents(design)` one `PlacedExtent` per footprint.
- A pad's position MUST be the footprint's position plus the pad's own position turned by the footprint's angle, with no further mirror, and its rotation the sum of the two angles. The copper of a layer of a stack MUST lie at the pad's position plus that layer's offset.
- A circle, an oval, a rectangle and a rounded rectangle with its corner percentage (the pair `corner_percent` of the pad's `altium` bag; the radius is that share of half the shorter side) MUST give exact entries. Any other shape MUST give the rectangle of its size with `exact` false. A non-plated hole MUST give no copper.
- An extent MUST be the hull of its footprint's pad copper on the face of its side, with `source` = `pads` and `exact` false, or `source` = `none` without pad copper.
- The module MUST declare its evidence (`backend-protocol`, "Backend modules declare their evidence") and MUST NOT import `fenolite.backends.kicad` or `fenolite.checks`.

#### Scenario: Pads of the routed sample
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k frame` reads `tests/data/altium/routed/routed.PcbDoc`
- **THEN** `board_pads` gives 36 pads, every entry is exact, each through-hole pad has an entry on each of the four copper layers, and each surface pad one entry on `F.Cu`

### Requirement: Clearance rules of a PCB document
`AltiumBackend` SHALL satisfy `DesignRulesSource` (`backend-protocol`): `design_rules(design, project)` gives the clearance in force for the import `design` of the PCB document `project.board`.
- `DesignRules.design` MUST be `design` with the clearance of every zone at 0, with every `clearance` rule lowered by `UNIT_SLACK_NM` = 5 nm (`docs/formats/altium/import.md`, "Clearance of the copper check"), and without the tracks and arcs that have no net and lie on the layer of an internal plane.
- `opaque_clearance_rules` MUST count the enabled `Clearance` records of `Rules6/Data` that `read.rules.map_rules` does not map; a disabled record MUST NOT count. `min_clearance` MUST be `None`, `rules_over_classes` true and `floor_over_rules` false.
- `left_out` MUST hold one entry of kind `plane` with the number of internal plane layers when the board has any, and be empty otherwise.
- A document that cannot be read MUST be named in `unread` and MUST NOT raise.

#### Scenario: Rules of a built sample
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k rules_source` asks for the rules of `routed.PcbDoc`
- **THEN** both zones have the clearance 0, the two clearance rules are 199 995 nm, no rule is opaque, and a missing document is named in `unread`

### Requirement: Parity on Altium projects
On document input that holds a PCB document and schematic documents, the stage `parity` SHALL compare the two readings with `checks.parity.compare`, with the schematic side that the backend builds from them (`DocumentParity` of `backend-protocol`; for Altium `adapter.parity.side_of(schematic, board)`): components by designator, the value from the comment, the footprint from the current footprint model, the pads that the pins name (the pad of a pin's own designator, or those of `Component.pin_pad_map` when the component holds one), the nodes from the imported nets.
- **Two spellings are read as one**, because they differ between the two documents of a project without being a difference of the design: a footprint whose name (the text after the last `:`) equals the name of the footprint of the same designator on the board is given in the board's spelling; and a net whose pads, over the pads both sides hold on a net, are exactly the pads of one board net is given that net's name. Any other footprint and any other net MUST keep the schematic's spelling, so a split, joined or open net stays a finding.
- `fold` and `single_prefix` of the side MUST be empty, and no component MUST carry an attribute.
- The stage MUST be skipped with `no-schematic` without a schematic document, with `single-source` without a PCB document, with `read-refused` when a side was refused, and with `netlist-unavailable` when the backend gives no side.
- Every finding MUST become an issue with the codes of the parity comparison (`checks.parity.PARITY_ISSUE_CODES`); `summary` MUST hold `netlist` = `own`, `compared` = `false`, `differences` = 0 and the counts of `ParityReport.summary`.
- `fenolite parity PATH` MUST accept an Altium project file, a project folder, or a PCB document beside the one project file whose board it is, with the result keys of the KiCad branch (`board`, `schematic`, `netlist`, `summary`, `findings`); `--netlist kicad` on such input MUST exit 2 with `FEN-2001`, and a set without a PCB document or without a schematic document MUST exit 3 with `FEN-3001`.

#### Scenario: Renamed designator
- **GIVEN** the routed blink built for Altium, with the PCB document of a build of the same script in which `R1` is `R99`
- **WHEN** `fenolite check <dir> --stages parity --json` runs
- **THEN** the exit code is 5, and the issues hold `parity.missing-footprint` at `R1` and `parity.extra-footprint` at `R99`

#### Scenario: Agreeing project
- **WHEN** `fenolite parity tests/data/altium/blink --json` runs
- **THEN** the exit code is 0 and every summary count is 0

#### Scenario: Committed samples agree
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_parity_side.py -k committed` compares the samples `blink`, `routed` and `board6` with their own boards
- **THEN** no sample gives a finding

#### Scenario: Public project sets
- **WHEN** `uv run pytest tests/corpus/test_altium_copper.py -k parity` compares each public project set
- **THEN** every `parity.net-conflict` names a pad that the pad-net comparison of the two readings flags
