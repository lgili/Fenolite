## Context

- **Scope.** Plan, v0.2b deliverables: "`parity` (sch ↔ pcb and symbol ↔ footprint)"; commands by milestone: "v0.2b: `sync`, `parity`". The plan's acceptance asks that parity reproduce counts of disconnected nets, missing connections and references on one side only that were measured outside this project; those counts are not used (`AGENTS.md`, clean-room). The categories stay; the reference becomes KiCad's own parity test on public demos and authored edits.
- **What v0.2a proposes (not archived).**
  - c0060: `sch.read_schematic`, `sch.sheet_files`, `sch.components(sheets, *, project, on_board_only=False)`; embedded symbol definitions with their pins; the demo schematics of both tags join the corpus.
  - c0062: `drc.kicad` passes `--schematic-parity` when the project has a schematic, and maps every parity entry to an issue `kicad.drc.<type>` with `where` (`R1-2` for a pad); `summary.parity_judged`; `H-K-PARITY-RUN`.
  - c0063: `sch_netlist.own_netlist` for generated sheets, `netlist.read_netlist` and `KicadCli.export_netlist`, the schematic netlist oracle protocol in `backend-protocol`.
  - c0070 (v0.2b): the own netlist over a sheet tree.
- **What exists.** `read_board`; footprint attributes including `board_only` (KiCad's "not in schematic"); `checks` imports only `core`, `model`, `geometry` and `backends.base`, and reaches KiCad through injected oracles; `STAGE_ORDER` may gain stages through ADDED requirements.
- **Measured on 2026-10-05** (scratch probe, `kicad-cli` 10.0.6, the `pic_programmer` demo board of the corpus with the tag's schematics, `pcb drc --schematic-parity --format json --severity-all`; 9.0.9 is measured by task 1.2):
  - unedited: no parity entry;
  - a footprint's reference renamed: `missing_footprint` ("Missing footprint R18 (220)", no item) and `extra_footprint` (item "Footprint R999");
  - a value changed: `footprint_symbol_mismatch` ("Value (…) doesn't match symbol value (…)");
  - a footprint's library id changed: `footprint_symbol_mismatch` ("… doesn't match footprint given by symbol (…)");
  - one pad moved to another net: `net_conflict` ("Pad net (…) doesn't match net given by schematic (…)", item "PTH pad 1 […] of C1");
  - a reference given to a second footprint: `duplicate_footprints` (both footprints as items), `missing_footprint` for the reference that lost its footprint, and one `net_conflict` on a pad of the duplicated pair;
  - a copied footprint with a new reference: `extra_footprint`.
- **Constraints.** Stdlib only. Read-only. No tool for a generated project. KiCad's answer wins whenever it exists.

## Goals / Non-Goals

**Goals:**
- One comparison, backend-free, that an agent can run with or without KiCad and whose categories it can act on.
- The comparison agrees with KiCad's parity test wherever both run, and the agreement is tested.
- Pins that can never be routed are found before routing.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **A backend-free comparison.** `checks.parity.compare(side, board, *, issues=None) -> ParityReport` takes a `SchematicSide`: components by reference (value, footprint library id, the pin numbers of all its units in body style 1 and the common pins) and nodes (reference, pin number → net name in KiCad's stored form). The board is a `Design` read by `read_board`. The KiCad adapter `backends/kicad/parity_inputs.py` builds the side; the v0.3 Altium adapter will build the same type.

2. **KiCad's categories, one code each.**

   | code | KiCad type | severity | key |
   |---|---|---|---|
   | `parity.missing-footprint` | `missing_footprint` | error | reference |
   | `parity.extra-footprint` | `extra_footprint` | error | reference |
   | `parity.duplicate-footprints` | `duplicate_footprints` | error | reference |
   | `parity.footprint-mismatch` | `footprint_symbol_mismatch` | warning | reference and field (`value`, `footprint`) |
   | `parity.net-conflict` | `net_conflict` | error | `REF-PAD` |

   - Components are matched by reference, as KiCad's test does (`H-K-SCH-PARITY`); paths never take part.
   - A footprint with the attribute `board_only` is never extra. A reference that starts with `#` is not a component.
   - A duplicated reference gives one `parity.duplicate-footprints`. The schematic component is matched with the first of its footprints in board order, so the others are judged as KiCad judges them in the measured case; the oracle test checks this choice (Decision 7).
   - A value and a footprint that both differ give two findings, one per field; the oracle test checks KiCad's count for that case.

3. **Symbol ↔ footprint.** For each matched pair:
   - `parity.pin-without-pad`: a pin number that names no pad of the footprint. Error when the pin's net has another node, so the connection can never be routed; warning otherwise.
   - `parity.pad-without-pin`: a numbered copper pad (not `np_thru_hole`) whose number no pin names. Info: mounting tabs and shields are often like that.
   - Pin numbers are the embedded symbol's, so a generated symbol with a pin-pad map already carries pad numbers (c0061).

4. **The plan's categories as a summary.** `ParityReport.summary` holds the count of each code and three derived counts: `refs_one_side` (missing plus extra footprints), `connections_missing` (net conflicts whose pad has no net while the schematic gives one) and `nets_split` (schematic nets whose pads carry more than one board net name, or one other than the schematic's).

5. **Nodes: own netlist first.** `--netlist auto` (default) uses `own_netlist` when `grammar_issues` of the sheet tree is empty, so a generated project needs no tool; otherwise it uses `kicad-cli sch export netlist` through `KicadCli.export_netlist` (exit 6 without the tool). `own` refuses a tree outside the grammar (exit 3, `FEN-3004`, with the grammar issues); `kicad` always runs the tool.

6. **The `check` stage.** Stage `parity`, after `drc.kicad`:
   - skipped with `no-schematic` without `<stem>.kicad_sch`, and with `netlist-unavailable` when the tree is outside the grammar and no netlist oracle is injected;
   - symbol ↔ footprint findings are always reported;
   - when `drc.kicad` judged parity in the same run, Fenolite's schematic ↔ board findings are compared with KiCad's entries by type and key and are not reported again; each difference gives one `parity.oracle-differs` (warning) naming the type, the key and the side that has it. Otherwise Fenolite's findings are reported.
   - Rejected: reporting both lists (every finding twice); dropping Fenolite's comparison when KiCad runs (it would never be verified in use).

7. **Oracle agreement.** On both majors, for every demo of the corpus with a board and a schematic at one tag, and for the six edits of the measured probe applied to `pic_programmer` and to a built example: the counts per KiCad type of Fenolite's comparison (with `--netlist kicad` for the demos) equal those of KiCad's report. A mismatch fails the test, naming the demo, the type and both counts. Where KiCad's choice for duplicated references differs from Decision 2's, the rule is changed to KiCad's, not the test.

8. **Cut order.** First the `check` stage's comparison with KiCad (report Fenolite's findings only when KiCad's parity did not run), then the derived summary counts, never the command and the oracle agreement.

## Measured on 2026-10-06 (tasks 1.2 and 4.1), and what changed

The probes and the agreement test ran on 9.0.9 and 10.0.6. Where KiCad differs from the decisions above, the rule follows KiCad:

- **Decision 1.** `SchematicSide` and `SideComponent` live in `backends/base.py`, because a backend package may not import `checks`; `checks.parity` re-exports them. The side also carries `fold` (spellings of a net name that are one: `{slash}` and `/`) and `single_prefix` (`unconnected-(`), and a component carries the flags `dnp` and `exclude_from_bom`.
- **Decision 2.** A duplicated reference gives one finding per further footprint, not one per reference, and footprints without a reference count. A `board_only` footprint is never extra and never a duplicate, and it still stands for the component of its reference, so the component is not missing. `parity.footprint-mismatch` has a third field, `attributes`.
- **Decision 3.** KiCad does report a pin without a pad, as a `net_conflict` of the footprint, and a pad on a net that no pin names, as a `net_conflict` of the pad. So `parity.pin-without-pad` maps to `net_conflict` in `KICAD_TYPES`, a pad on a net without a pin is a `parity.net-conflict`, and `parity.pad-without-pin` is left for a pad on no net. A pin without a number is not compared.
- **Decision 5.** `--netlist own` refuses with `FEN-7001` (exit 7), as `netlist --source fenolite` does (c0063), not with `FEN-3004`.
- **Decision 6.** The stage is not an oracle stage. It gets the side from the validator (`ParityInputs`) and the netlist of a schematic outside the grammar from the oracle that another stage built. The key of a KiCad entry is its first item's location; a missing footprint has no item, so its reference is read from the text, and missing footprints are compared by number when the text gives none.
- **Decision 7.** The probes run on the built blink, so they need no corpus; `pic_programmer` and the other demos are `needs_corpus` tests. The demo of tag 9.0.9.1 disagrees with its schematic as published (61 mismatches), so a demo probe counts what an edit adds. 10.0.6 has one more type, `footprint_symbol_field_mismatch`, which Fenolite does not compare.
- **Hypothesis H-K-PARITY-TYPES.** A duplicated reference gives `duplicate_footprints` and `missing_footprint`; a `net_conflict` comes only when the footprint that took the reference is the first of that reference on the board.

## Files and public API

- `src/fenolite/checks/parity.py`: `SideComponent(value, footprint, pins)`, `SchematicSide(components, nodes)`, `ParityFinding(code, severity, key, field, schematic, board)`, `ParityReport(findings, summary, evidence)`, `compare`, `PARITY_ISSUE_CODES`, `KICAD_TYPES` (code → KiCad type), `EVIDENCE`.
- `src/fenolite/backends/kicad/parity_inputs.py`: `schematic_side(root_file, *, project, netlist) -> SchematicSide`.
- `src/fenolite/checks/stages.py`: `parity` in `STAGE_ORDER`; `checks/parity_stage.py`.
- `src/fenolite/cli/cmd_parity.py`.
- Tests: `tests/unit/checks/test_parity.py`, `tests/unit/cli/test_parity_cmd.py`, `tests/unit/checks/test_parity_stage.py`; `tests/kicad/check/test_parity_probes.py`, `test_parity_agreement.py`; fixtures under `tests/data/kicad/parity/` authored for Fenolite.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PARITY-TYPES | `pcb drc --schematic-parity` gives, for a renamed reference, `missing_footprint` and `extra_footprint`; for a changed value or library id, `footprint_symbol_mismatch`; for a pad on another net, `net_conflict`; for a duplicated reference, `duplicate_footprints`, `missing_footprint` and `net_conflict`; for an added footprint, `extra_footprint`; and nothing for an unedited demo (S-0020, S-0029) | `tests/kicad/check/test_parity_probes.py` | probes `parity-type-<edit>` `equal` on 9.0.9 and 10.0.6 |
| H-K-PARITY-OWN | On every corpus demo with a board and a schematic, and on the six edits, the counts per KiCad type of `checks.parity.compare` equal those of `kicad-cli`'s parity report (S-0020, S-0029) | `tests/kicad/check/test_parity_agreement.py` | probe `parity-own-agreement` `equal` on both majors |

Ids used without changing their level: `H-K-SCH-PARITY` (c0061), `H-K-PARITY-RUN` (c0062), `H-K-NETLIST-OWN` (c0063).

## Risks / Trade-offs

- [KiCad's matching of duplicated references differs from Decision 2] → the agreement test catches it, and the rule follows KiCad.
- [A demo outside the own grammar needs the tool] → `--netlist kicad` in the oracle test; without the tool the stage is skipped with a reason.
- [Net names in stored form] → compared in the stored form on both sides, as c0061's parity relies on (`H-K-SCH-SLASH`).
- [`pad-without-pin` noise] → info only.

## Migration Plan

- Additive: one command, one stage, new codes. `--stages` without `parity` gives the same output as before.
- Rollback: remove the stage from `STAGE_ORDER`; the command stays read-only.

## Open Questions

- **Should `parity` default to `--netlist kicad` when the tool is present?** Default: no, `auto`: the own netlist is proved equal to KiCad's on generated sheets (c0063) and needs no subprocess.
- **Should `parity.footprint-mismatch` be an error?** Default: warning, as a changed value does not break connectivity.
