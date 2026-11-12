## ADDED Requirements

### Requirement: Silkscreen check on Altium boards
The opt-in document stage `silk.clearance` SHALL judge the silkscreen of a PCB document against the rules of
kinds `silk_clearance`, `silk_mask_clearance` and `silk_edge_clearance` that apply to it (change c0498).
- It MUST use the `altium` obstacle model of `silk.board` (capability silkscreen-layout): a stroke text is its
  box shrunk by half its stroke, a mask opening is each pad's copper grown by its own expansion, a text does
  not see its own component's silk, and hidden designators are left out.
- Findings MUST be `silk.clearance`, `silk.mask-clearance` and `silk.edge-clearance`. Each MUST name both
  items, the gap, the rule's value and its name.
- The stage MUST run only when `--stages` or `--compare-native` selects it. Its evidence MUST be `INFERRED`
  and name `H-A-SILK-DRC-MODEL` and `H-A-SILK-RULES`.
- A document without a silk rule MUST skip the stage with reason `not-judged`.

#### Scenario: Two texts too close
- **GIVEN** an authored PCB document with a `SilkToSilkClearance` of 0.15 mm and two designators whose boxes,
  shrunk by half their stroke, are 0.1 mm apart
- **WHEN** `fenolite check <doc> --stages silk.clearance --json` runs
- **THEN** it reports one `silk.clearance` naming both designators, 0.1 mm and 0.15 mm

#### Scenario: A text on a mask opening
- **GIVEN** the same document with a free text 0.02 mm from a pad's mask opening and a
  `SilkToSolderMaskClearance` of 0.05 mm
- **WHEN** the stage runs
- **THEN** it reports one `silk.mask-clearance` naming the text and the pad

#### Scenario: Silk over the edge
- **GIVEN** the same document with a silk line 0.1 mm from the board outline and a
  `SilkToBoardRegionClearance` of 0.2 mm
- **WHEN** the stage runs
- **THEN** it reports one `silk.edge-clearance` naming the line and `board`

### Requirement: Comparison with Altium's DRC
`fenolite check PATH --compare-native [REPORT]` SHALL compare the findings of the stages that ran with
Altium's own DRC results, on Altium input only (change c0498).
- **Source.** Without `REPORT`, the stored violations of the PCB document (`altium-pcb-reader`, "DRC
  violations stored in a PCB document"). With a `.drc` path, that report. Without stored violations and
  without `REPORT`, one `check.native-missing` warning and no comparison. On KiCad input, exit 2 with
  `FEN-2001`.
- **Stages.** The option MUST add the opt-in stages `altium.native-drc` and `silk.clearance` to the selected
  stages.
- **Pairing.** A native finding and a Fenolite finding MUST pair when the Fenolite code maps to the native
  kind (`rulemap.NATIVE_CODES`) and their item sets are equal. When the native finding has no items, they
  MUST pair when its location is within 0.1 mm of the Fenolite finding's place. Each finding pairs at most
  once. The result MUST NOT depend on the order of either list.
- **Result.** `result.native` MUST hold `source`, `file` (no folder), `matched`, `by_kind`
  (`{kind: {matched, fenolite_only, native_only}}`), `fenolite_only`, `native_only`, `unjudged` (native
  counts of kinds with no Fenolite code), `waived` and `stale`.
- **Issues.** One `check.fenolite-only` or `check.native-only` warning per unpaired finding of a judged
  kind. One `check.native-stale` warning with the count when any violation is stale. These warnings MUST NOT
  change the exit code.
- **Read-only.** It runs no tool and writes nothing. "Check on Altium inputs", "Read-only", applies.

#### Scenario: The kit board agrees
- **GIVEN** the authored kit board of change c0498, saved by Altium after its DRC
- **WHEN** `uv run pytest tests/kicad/altium/test_native_kit_c0498.py` runs `fenolite check <doc>
  --compare-native --json`
- **THEN** every planted fault is in `matched`, and `fenolite_only` and `native_only` are empty

#### Scenario: A fault Fenolite misses
- **GIVEN** an authored document with stored violations that hold one `Clearance` violation between two
  tracks that Fenolite's copper check passes
- **WHEN** `uv run pytest tests/unit/cli/test_check_native.py -k native_only` runs the comparison
- **THEN** `result.native.native_only` holds that violation, `by_kind.Clearance.native_only` is 1, there is
  one `check.native-only` warning, and the exit code is 0

#### Scenario: Without a stored DRC
- **WHEN** `fenolite check tests/data/altium/routed/routed.PcbDoc --compare-native --json` runs on a document
  with no violation storage
- **THEN** it reports one `check.native-missing` and `result.native` is absent

#### Scenario: On a KiCad board
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --compare-native` runs
- **THEN** the exit code is 2 with `FEN-2001`
