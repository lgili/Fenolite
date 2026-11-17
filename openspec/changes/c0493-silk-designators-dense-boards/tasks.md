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
- [ ] 3.2 Maintainer board (private, codes only): with `--model altium` every designator is placed or has an unplaced kind, and
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

