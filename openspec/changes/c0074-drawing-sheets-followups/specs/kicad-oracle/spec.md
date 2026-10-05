## ADDED Requirements

### Requirement: Follow-up facts are probed
`tests/kicad/followups/test_followup_probes.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PRO-WKS-SCH`, `H-K-OUTLINE-CHAIN`, `H-K-OUTLINE-FPEDGE`, `H-K-EXPORT-OPTIONS` and `H-K-STITCH-AVOID` on the running `kicad-cli`, through c0009's `KicadCli` on copies with an empty `KICAD_CONFIG_HOME`, judging DRC only from the JSON report.
- **Schematic frame.** A two-sheet project written by the test and a drawing sheet with one distinctive text: `wks-sch-key-relative` and `wks-sch-key-kiprjmod` MUST record `present` when `sch export svg` writes that text on both sheets with the schematic key set as named, and `wks-sch-key-absent` and `wks-sch-key-board-only` `absent` when it does not, without the key or with only the board key.
- **Outline gap.** A board of four edge lines whose last line stops short of the first corner by 9 999, 10 000 and 10 001 nm: `outline-gap-<nm>` MUST record whether `invalid_outline` is reported.
- **Footprint edges.** `outline-fp-edge-closes`: a board whose edge is closed only with a footprint's `fp_line` items gives no `invalid_outline`; `outline-fp-edge-cutout`: a footprint `fp_circle` on the edge layer inside the board gives `copper_edge_clearance` for a track crossing it.
- **Export options.** The help of `pcb export gerbers`, `drill` and `pos` MUST give a row `help-pcb-export-<kind>-<option>` for each option of the preset table, and one run per option on a corpus demo board MUST write files that differ from the default run.
- **Stitching.** A built board with a stitch fence across a rule area that forbids vias and along the board edge: `stitch-avoid` MUST record `equal` when its DRC report holds no `items_not_allowed` and no `copper_edge_clearance` entry for a stitch via, and the same fence built without Decision 7 of the design holds both.
- The outcomes MUST be recorded in both probe files, and the facts written to `docs/formats/kicad/worksheet.md`, `docs/formats/kicad/board.md` and `docs/formats/kicad/cli.md` with their sources and labels. `outline.CHAIN_GAP` MUST stay below the smallest gap that a major reports as open.

#### Scenario: Probes on both majors
- **WHEN** `uv run pytest tests/kicad/followups/test_followup_probes.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** the schematic-key probes record `present`, `present`, `absent` and `absent`; `outline-gap-9999` records no `invalid_outline` and `outline-gap-10001` records it; `outline-gap-10000` records none on 10.0.6 and one on 9.0.9; the footprint-edge, option and stitching probes record their expected outcomes

#### Scenario: Demo outlines close
- **WHEN** `uv run pytest tests/corpus/test_outline_corpus.py` runs over the 21 native demo boards
- **THEN** every board gives at least one ring, `kicad-demo-10-0-6-pcb-01` has `joined` 1, and `-14` and `-16` close with their footprints' edge items
