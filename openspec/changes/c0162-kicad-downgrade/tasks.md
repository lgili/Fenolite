## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living `kicad-version-gating`, `backend-protocol` and `cli-contract` specs, and the deltas of c0159 and c0161. Write under this task, with the date: that c0159 is archived or its KiCad to KiCad direction is on the branch (else stop); whether "Targets and downgrade refusal", "Write capability fields" or "Library errors map to registered codes" changed since `f802b60` (then regenerate the MODIFIED block from the living text with only this change's edits); whether `tokens.toml` gained rows since `f802b60` (the table of task 2.1 covers them); the maintainer's answers to the open questions (given on 2026-10-09: every recommended answer, `docs/roadmap.md` Open decisions row 40). Proof: `openspec validate c0162-kicad-downgrade --strict --no-interactive` passes.

## 1. Measure and register

- [ ] 1.1 Write `tests/corpus/test_downgrade_census.py` from the design's measurements 1 and 2: the two boards of major 10 with their too-new token counts per row, today's slot-level drop (746 and 134 nodes, `setup` among them), level 5 equal after the drop; the ten schematic sheets with their counts per row. Proof: `uv run pytest tests/corpus/test_downgrade_census.py -rA` with the corpus cached.
- [ ] 1.2 On 9.0.9 and 10.0.6, record the absent default of `covering`, `plugging`, `capping` and `filling`, and the form in which 9.0.9 reads a buried via (a bench saved by 10.0.6, the via written in 9's blind-and-buried form, loaded and checked by 9.0.9). Write the results under this task. Proof: `uv run pytest tests/kicad/downgrade/test_rows.py -k "protection or buried" -rA` in both pinned images.
- [ ] 1.3 Add the rows `H-K-DOWN-ROWS` and `H-K-DOWN-DEMOS` to `docs/hypotheses.md` (level `INFERRED`, tests and criteria of the design, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 2. The resolver

- [ ] 2.1 Write `data/downgrade.toml` with the actions of the design's table and `resolver.load()` with its closure (scenario "Table is closed"); add the column `downgrade` to `tools/gen_token_docs.py` and regenerate `docs/formats/kicad/tokens.md`. Proof: `uv run pytest tests/unit/backends/kicad/test_resolver.py -k closed -q`; `uv run python tools/gen_token_docs.py --check`.
- [ ] 2.2 Write `resolver.resolve` (edits at the node) and `downgrade=` on `check_target`, `write_board`, `mod.write_footprint` and `mod.write_pretty` (scenarios "Downgrade on request", "Setup kept", "Design loss needs consent"); every write without `downgrade` keeps its bytes. Proof: `uv run pytest tests/unit/backends/kicad -q`; `uv run pytest tests/corpus/test_downgrade_census.py -rA`.
- [ ] 2.3 Write `sch.retarget_schematic` and `downgrade=` on `sym.write_symbol_library` (the RT1 of a re-targeted sheet: the model of the source minus the reported rows). First item of the cut order. Proof: `uv run pytest tests/unit/backends/kicad/test_sch_retarget.py -q`.
- [ ] 2.4 Write `downgrade=` on `pro.update_project` and `dru.write_rules` (the `project:` rows; a 10-only rules row is `design`). Proof: `uv run pytest tests/unit/backends/kicad/test_pro.py tests/unit/backends/kicad/test_dru.py -q`.

## 3. Direction, capabilities, codes

- [ ] 3.1 Extend c0159's KiCad to KiCad direction to an older target, with the report rows per resolver id and the profile `kicad-downgrade` (scenario "Demo project for KiCad 9" without the tool). Proof: `uv run pytest tests/unit/convert/test_to_kicad.py -k downgrade tests/unit/cli/test_convert_cmd.py -k downgrade -q`.
- [ ] 3.2 Report `downgrade == "supported"` and list the downgrade in `capabilities.conversions`; change the meaning and hint of `FEN-7002` in the registry and in `docs/cli-contract.md` (scenarios "KiCad write fields in capabilities", "Downgrade maps to exit 7", "Build keeps refusing"). Proof: `uv run pytest tests/unit/cli/test_library_errors.py tests/unit/cli/test_capabilities_backends.py tests/unit/backends/test_base_types.py tests/consistency -q`.

## 4. Benches

- [ ] 4.1 Write `tests/kicad/downgrade/_benches.py` (one minimal authored file per resolver row of a board, footprint, schematic or symbol kind, saved by 10.0.6) and `test_rows.py`, register the probes `down-row-<id>`; a row whose bench differs moves to `design`, written under this task (scenario "Each row proved on 9.0.9"). The `rewrite` rows beyond `tenting`, `island`, `power` and `net-by-name` that fail are the second item of the cut order. Proof: `uv run pytest tests/kicad/downgrade/test_rows.py -rA` in the pinned 9.0.9 and 10.0.6 images; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py`.
- [ ] 4.2 Write `tests/kicad/downgrade/test_demos.py` and record `down-demos` (scenario "Demo project for KiCad 9", and `CM5_MINIMA_3`). Proof: `uv run pytest tests/kicad/downgrade/test_demos.py -rA` in both pinned images with the corpus cached; `uv run pytest tests/kicad/test_probe_results.py`.

## 5. Closing

- [ ] 5.1 Replace "Downgrade stays refused until a capability resolver exists" in `docs/formats/kicad/versions.md` by a section "Downgrade" (the table, the actions, the edits, the benches); document the direction in `docs/conversion.md` and the census in `docs/evidence/conversion.md`; update `docs/adr/0002-kicad-file-backend.md`'s sentence on downgrade with a dated note. Proof: `uv run pytest tests/unit/test_adrs.py tests/unit/test_format_facts.py tests/unit/convert/test_docs.py -q`.
- [ ] 5.2 Update the evidence labels: the two rows hold their measured levels and results; `resolver.EVIDENCE` names them and each row's level is shown in the token page's new column. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_capability_evidence.py -q`.
- [ ] 5.3 Add to `CHANGELOG.md` under Unreleased: the controlled downgrade through `fenolite convert --to kicad --kicad-version 9`, the resolver table, `downgrade: "supported"`, the new meaning and hint of `FEN-7002`, and the correction change c0163 for opaque net references (decided by the maintainer on 2026-10-09). Proof: `grep -n "downgrade" CHANGELOG.md`.
- [ ] 5.4 Run the residue scan and the fast suite. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes; `openspec validate c0162-kicad-downgrade --strict --no-interactive` passes.
