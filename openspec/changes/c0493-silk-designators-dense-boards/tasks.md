# Tasks: c0493-silk-designators-dense-boards

Rules for every task:

- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test boards are authored for Fenolite.
- Run each touched test file alone with `-n 0`.

- [x] 1.1 Reproduce on an authored dense bench (scenario "A dense grid of small parts"): today most
  designators are `silk.no-place`. Record the blocker kinds in the test.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/silk/test_dense_c0493.py -q -n 0`
  - Before the change 0 of the 16 designators of the bench (`_silkbench.dense`) were placed; every cheapest place met
    a neighbour's courtyard (kind `courtyard`). After it all 16 are placed in both models.
- [x] 1.2 Rings, over-body places and height steps in `silk/layout.py` and `looks_of` (design D1); tests for
  the scenario and for determinism.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/silk/test_layout.py tests/unit/silk/test_dense_c0493.py -q -n 0`
- [x] 1.3 The two clearance models in `gather` and `check_designators` (design D2); tests for "A text over
  its own outline" and "Each pad's own mask expansion". Record `H-A-SILK-DRC-MODEL` in
  `docs/formats/altium/` with its label.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/silk/test_designators.py tests/unit/silk/test_dense_c0493.py -q -n 0`
- [x] 1.4 The unplaced report (design D3) and the clip rows (design D4); tests for "A part with no room" and
  "Clip then place"; time the dense bench.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/silk/test_clip.py tests/unit/silk/test_dense_c0493.py -q -n 0`
  - `result.unplaced` changes type from a count to `{kind: count}` (the spec's `result.unplaced.pad`); the
    clip already ran first. The dense bench takes about 2 s (asserted under 30 s). In `test_clip.py` the part
    inside another's courtyard (`TP1`) is now placed: a courtyard only adds cost.
- [x] 2.1 KiCad oracle: designators placed with `--model kicad` on the dense bench give KiCad no new
  silkscreen finding.
  - Proof: `uv run --extra dev pytest tests/kicad/silk/test_designators_oracle.py -q -n 0` (needs `kicad-cli`)
  - 3 passed with local kicad-cli 10.0.6 (2026-11-13), the bench `dense` added.
- [x] 2.2 Teach the new options on the silk page of the agent guide, then regenerate the command pages.
  - Proof: `uv run python tools/gen_agent_guide.py --check && uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [x] 2.3 Regenerate the schemas for the new result keys.
  - Proof: `uv run python tools/gen_schemas.py --check`
  - `SilkSettings`, `SilkClip.footprints` and `SilkResult.unplaced` declared; `fenolite.silk.v0.json` and its
    hash in `schemas/frozen-v0.json` regenerated, as changes c0477 and c0495 did.
- [x] 3.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast` (25196 passed, 76 skipped, 2026-11-13)
- [x] 3.2 Maintainer board (private, codes only): with `--model altium` every designator is placed or has an unplaced kind, and
  Altium 24's DRC reports no silk-to-silk or silk-to-mask violation for the placed ones.

  Result (maintainer board, 2026-11-16): Fenolite part passes, 256 of 256 designators placed (233) or with an unplaced kind (23); the command exits 5 with 23 `silk.check-failed` on designators left below the minimum size, so nothing is written: follow-up. Altium DRC part not run (VM).

  Decision (maintainer, 2026-11-17): the 23 `silk.check-failed` were placed designators that kept their own
  height, already below the board's minimum, not unplaced ones; such a text is now `silk.below-minimum`
  (warning) and the board is written (design D5). Test `test_texts_already_below_the_minimum`.

  Result (maintainer board, 2026-11-17): `--model altium` exits 0 and writes the board: 233 placed, 23
  unplaced (text 13, hole 4, mask 3, silk 3), 23 `silk.no-place`, 23 `silk.below-minimum`, 0
  `silk.check-failed` (were 23, exit 5, nothing written). Altium DRC part still not run (VM).

  Result (Altium 24.5, 2026-11-17): FAIL. The written board, converted to Altium (exit 0, equivalence
  level 5), Repour All, then DRC: 237 violations (149 silk-to-mask, 88 silk-to-silk), against 24 for the
  same board before the command; 227 of the texts named are designators the command placed. The board's
  rules are 0.15 mm for both checks; the command ran with gap 0.10 mm and mask clearance 0.10 mm, which
  explains 31 findings between 0.10 and 0.15 mm. The other findings are under 0.10 mm or collisions
  (80 with a placed designator: 40 on pads, 39 on silk tracks, the rest text on text). KiCad 10.0.6 on the
  KiCad board before conversion agrees: 122 `silk_overlap` name a placed designator. So the command's own
  overlap model misses real overlaps, and it does not take the clearances from the board's rules.
  Follow-up change needed; 3.2 stays open.

  Decision (maintainer, 2026-11-17): the clearances come from the board's rules. `--clearance` and
  `--mask-clearance` default to the largest `silk_clearance` rule of the `.kicad_dru` (KiCad judges
  silkscreen to a mask opening by the same constraint), else the project's `min_silk_clearance` above 0,
  else 0.15 mm and 0.1 mm; `result.settings.sources` names each source (design D6).

  Decision (maintainer, 2026-11-17): the overlap model follows what both tools measured. A text is judged by
  its whole ink, and in the `altium` model also by the box Altium measures from the corner the writer
  stores (`text_box`, `altium_box`; the old box less half a stroke was smaller than both); the `altium`
  model judges a text against its own footprint's silkscreen (Altium reported 46 of 63 text-to-track
  violations against the text's own component); an unplated pad that opens the mask is an opening.
  Tests `test_each_pads_own_mask_expansion`, `test_a_text_over_its_own_outline`,
  `test_the_altium_box_starts_at_the_written_corner`, `test_an_unplated_pad_opens_the_mask`.

  Decision (maintainer, 2026-11-17): KiCad's courtyard findings come from the board's rule: a
  `silk_clearance` rule with no condition and no layer clause reaches every item of the side
  (`H-K-SILK-REACH`). With such a rule every courtyard, the part's own too, is kept that far and `--gap`
  defaults to at least it, counted from the courtyard's ink. Copper (tracks, zones, vias) and visible
  fabrication-layer fields, which the same rule reaches in KiCad only, stay out of the search; narrowing
  the translated rule is a follow-up. Tests `test_clearances_from_the_board_rules`,
  `test_courtyards_kept_when_the_rule_reaches_them`.

  Result (maintainer board, 2026-11-17, after fix): `--model altium` exits 0 and writes the board; settings
  0.15 mm for clearance, mask clearance, gap and courtyard, all from `rule`. 212 placed, 44 unplaced
  (text 17, courtyard 13, hole 11, silk 2, mask 1), 44 `silk.no-place`, 17 `silk.below-minimum`, 0
  `silk.check-failed` (before: 233 placed, 23 unplaced). `kicad-cli` 10.0.6 DRC (`--severity-all`), counted
  in runs split by item type because each type stops at 199: findings naming a placed designator against
  silkscreen, another text, a courtyard, a pad or mask opening, or the edge: 0 (before, same counting: at
  least 290: courtyard 191, silkscreen 88, designator 10, edge 1). Against what only the rule's KiCad reach
  judges: tracks at least 133, zones 74, vias 0, fabrication fields at least 81 (the same designators where
  they were before the command: at least 148, 78, 30 and 123). Unplaced designators keep their findings
  (courtyard 40, silkscreen 10, one `silk_over_copper`). Fenolite's `silk.clearance` judge on the converted
  document at 0.15 mm: 0 silk-to-silk and 0 silk-to-mask findings name a placed designator. Converted to
  Altium (exit 0, equivalence level 5) for the maintainer's Altium DRC; that part is still open.

  Result (Altium 24.5, 2026-11-17, after fix): the converted board opened in Altium, Repour All, then DRC:
  22 violations (12 silk-to-mask, 10 silk-to-silk), against 24 before the command and 237 before the fix;
  none names a designator the command placed. The 12 left are pad-to-silk tracks (10) and texts the command
  did not place (2 on pads, 10 on silk). The fitted Altium text box is confirmed on this board. 3.2 passes.

- [x] 3.3 Narrow the translated silkscreen rules (`H-K-SILK-REACH`, design D7): Altium's silk-to-silk rule
  becomes a KiCad check of silkscreen against silkscreen only, silk-to-mask one of silkscreen against pads,
  and `fenolite silk` stays coherent on converted boards.
  - Proof: `uv run pytest tests/kicad/rules/test_silk_reach.py tests/kicad/rules/test_rule_kinds_new.py tests/unit/backends/kicad/test_rulemap_kinds.py tests/unit/convert/test_altium_rule_fates.py tests/unit/silk/test_dense_c0493.py -q`
  - `tests/kicad/rules` and `tests/kicad/silk` pass with local `kicad-cli` 10.0.6 (138 passed) and with
    9.0.9 in the pinned image (127 passed, 11 skipped for 10.x only), 2026-11-17.

  Decision (maintainer, 2026-11-17): `silk_clearance` is written with the condition
  `A.Layer == '?.Silkscreen' && B.Layer == '?.Silkscreen'` and `silk_mask_clearance`, until now left out, as
  a `silk_clearance` rule with `A.Layer == '?.Silkscreen' && B.Type == 'Pad'`, on KiCad 9 and 10
  (`rulemap.SILK_CONDITIONS`); not the board-setup value, which judges no pad and cannot be read back as a
  rule. A rule read from KiCad with no condition is written back with none (`rulemap.reaches_every_item`);
  `fenolite silk` keeps courtyards only under such a rule and takes the mask clearance from the pad rule.
  Tests `test_silk_rules_judge_silkscreen_only`, `test_a_native_silk_rule_keeps_its_reach`,
  `test_clearances_from_the_board_rules`, `test_translated_silk_rules_judge_silkscreen_and_pads_only`.

  Result (maintainer board, private, codes and counts only, 2026-11-17): the source folder named for the check no
  longer exists, so the Altium project written back from the earlier KiCad conversion (equivalence level 5)
  was converted again (exit 0) into a new private folder. `kicad-cli` 10.0.6 DRC (`--severity-all`): `silk_overlap` 98, of which 60 name a Reference
  field, all silkscreen against silkscreen; `silk_over_copper` 18, all naming a Reference field. The same board
  with the rule's condition removed (the old translation): `silk_overlap` 199 (the report limit; 94 name a
  courtyard), 103 naming a Reference field; `silk_over_copper` 30, all Reference. The board's Altium
  Silk To Solder Mask Clearance record is not mapped (its keys), so no pad rule is written for it and the 18
  `silk_over_copper` are ink over pad copper, which KiCad reports at any clearance.
