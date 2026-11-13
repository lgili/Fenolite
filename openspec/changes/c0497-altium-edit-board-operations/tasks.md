# Tasks: c0497-altium-edit-board-operations

Rules for every task:

- The field board is private. Nothing from it (names, nets, designators, coordinates, files) goes into tests,
  fixtures, commits or messages. Test boards are authored for Fenolite (design, "Test boards").
- Each written field cites its row in `docs/formats/altium/` with its label. A fact without a row gets one first.
- Run each touched test file alone with `-n 0`.

## 1. Facts and test boards

- [x] 1.1 Census of the public corpus, counts only: the `Components6` keys of a designator's and a comment's
  position mode and their values; whether any `Board6` outline also holds a hole of a free cut-out. Record the
  rows in `pcb-records.md` as `CORPUS-VERIFIED`, or `UNKNOWN` when no row holds a key.
  - Proof: `uv run --extra dev pytest tests/unit/test_format_facts.py -q -n 0`
- [x] 1.2 Add `H-A-EDIT-TEXT`, `H-A-EDIT-CUTOUT`, `H-A-EDIT-TENT` and `H-A-EDIT-DRAWING` to `docs/hypotheses.md`
  (`INFERRED`), each with its sources.
  - Proof: `uv run --extra dev pytest tests/unit/test_hypotheses_register.py -q -n 0`
- [x] 1.3 Test board builders `tests/unit/backends/altium/edit/board_ops.py`: `drawn`, `vias` and `texts`, built
  from the Part J kit board (design, "Test boards"). Add a manifest entry for any file under `tests/data`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_board_ops_c0497.py -q -n 0` (each board
    reads back strictly, and `altium.integrity` finds nothing)
  - Proof: `uv run --extra dev pytest tests/corpus/test_manifest.py -q -n 0`

## 2. Operations

- [x] 2.1 Gates `text`, `cutout`, `tenting` and `board_drawing`, with their `ROWS`, in `edit/session.py`. Add
  `Board6` and `BoardRegions` to `session._records`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_session.py -q -n 0`
- [x] 2.2 (F32) `set_outline` of a `Region` (design D7).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_shapes.py -k region_outline -q -n 0`
- [x] 2.3 (F27) `Designator`, `Comment` and the narrowed `Text`; `move` and `rotate` of a text; the
  position-mode key after 1.1 (design D2).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_texts_c0497.py -q -n 0`
- [x] 2.4 (F31) `edit/drawing.py` (`board_shape`, `compare`); `draw_board_shape` with its post-condition in
  `verify`; the stage `altium.board-drawing` and its two codes (design D6).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_drawing_c0497.py -q -n 0`
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_stage.py -q -n 0`
- [x] 2.5 (F28) `add_board_cutout`: the inner ring, the refusal of a crossing ring, the notch through `Board6` and
  `BoardRegions`, `drawing=` (design D3).
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/edit/test_cutouts_c0497.py -k "inner or notch or crossing" -q -n 0`
- [x] 2.6 (F29) `add_polygon_cutout`, which drops the pour of the polygons it meets (design D4).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_cutouts_c0497.py -k polygon_cutout -q -n 0`
- [x] 2.7 (F30) `Vias` and `set_via_mask` (design D5).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_vias_c0497.py -q -n 0`
- [x] 2.8 Run every test file that reads the session's output, not only the new ones.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/edit -q -n 0`

## 3. CLI

- [x] 3.1 The `.PcbDoc` mode of `fenolite edit`: `--ops-file`, the item objects, `--gate` and
  `altium.edit.gate-opened` (design D1). Coordinate with c0502 if it has landed a `.PcbDoc` mode.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_edit_pcbdoc_c0497.py tests/unit/cli/test_edit_cmd.py -q -n 0`
- [x] 3.2 Regenerate the schemas and the generated guide sections.
  - Proof: `uv run python tools/gen_schemas.py --check && uv run python tools/gen_agent_guide.py --check`

## 4. Kit, docs and changelog

- [x] 4.1 Part J cases `J-text`, `J-cutout`, `J-tent`, `J-drawing` and `J-region` in `docs/evidence/altium-edit.md`,
  numbered after the last case on dev (c0499 holds J34), each with its expected outcome and the hypotheses it names.
  - Proof: `uv run --extra dev pytest tests/unit/test_altium_verification_docs.py -k part_j -q -n 0`
- [x] 4.2 Explain every new code (`altium.edit.gate-opened`, `altium.board-drawing.mismatch`,
  `altium.board-drawing.none`) in `cli/data/explain.toml`.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_explain_cmd.py -q -n 0`
- [x] 4.3 Agent guide page `altium.md`: one tested `fenolite edit … --ops-file` example and the new codes; update
  "edit" in `docs/cli-contract.md`.
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [x] 4.4 `CHANGELOG.md` under `## [Unreleased]`; `tools/model_review.py --check`; `make check-fast`.
  - Proof: `uv run python tools/model_review.py --check && make check-fast`

## Implementation notes (2026-11-13)

- 1.1: the census (S-2325) names `NAMEAUTOPOSITION` (values 1, 2, 5, 8) and `COMMENTAUTOPOSITION` (value 3), and
  no row holds a value for a text placed by hand. A moved or turned text is written with its key left out, the
  form of most records (`INFERRED`, J35 decides). The census also found that each row's `BoardRegions` record is a
  plain region record of the outline with arcs as chords, so a notch writes that ring with
  `records.region_outline` (`CORPUS-VERIFIED` form, `INFERRED` edit).
- 2.4: the `drawn` board draws its outline with 5 tracks and 1 arc and its board cut-out with 4 tracks, so its
  `old_count` is 10 (the scenario's 6 counts the outline alone). The post-condition runs in `Session.apply`
  through `State.post`, after every queued operation.
- 2.5: a notch keeps each outline arc whose chords survive whole; an arc the notch cuts becomes chords of at most
  5° (`drawing.CHORD_DEGREES`), not the board's arc resolution.
- 2.7: untenting without `expansion` leaves the cache state byte as it is.
- 3.1: c0502 has not landed a `.PcbDoc` mode; this change adds it (`cli/edit_pcbdoc.py`).
- 4.1: the cases are J35 to J39 (J34 stays c0499's); the files come from
  `tests/unit/backends/altium/edit/test_part_j_c0497.py`. Running them in Altium Designer is the maintainer's.

