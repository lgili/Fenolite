# Tasks: c0464

## 1. Diagnosis

- [x] 1.1 Census of the `Board6` keys, display units, mechanical names and super classes of public rows
  `-01` to `-08` (S-2231). Proof: the scratch scripts' key census.
- [x] 1.2 The writer's `Board6` lines follow Altium's one for one; the mechanical ids come back right and
  their names are the KiCad layer names. Proof: `docboard.board_records` against row `-01`.

## 2. Carrier

- [x] 2.1 `altium_storages` carries `Board6.Settings` (anchored runs of the keys `docboard.OWNED_KEY` does
  not name, and the mechanical names). Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k carries`.

## 3. Writer

- [x] 3.1 `docboard.with_settings` merges the carried fields; `pcbdoc` takes `Board6.Settings` from the kept
  storages. Proof: `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k merge`.
- [x] 3.2 Mechanical names by layer: `lower.named_mechanical`, `PcbDocSpec.named_layers`. Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k mechanical`.

## 4. Flow A

- [x] 4.1 Authored reproductions through flow A (import, build, convert back): the metric document with a
  0.025 mm rule, the document with Altium's default mechanical names, and the black solder mask (S-2232,
  S-2234). Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k flow`.

## 6. Empty mechanical slots

- [x] 6.1 Carry the enabled flags of mechanical layers 1 to 16 with their names; a slot that nothing lies on
  takes the source's flag, and a slot no primitive lies on its name (S-2235, S-2236). Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k empty_slots`.
- [x] 6.2 A drawing on the KiCad row `Altium.DrillDrawing` or `Altium.DrillGuide` goes back to layer 73 or
  55 (`lower.drill_rows`). Proof: `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k drill`.
- [x] 6.3 Rows `-02`, `-04` and `-06` through flow A give every slot's name and flag back, and row `-02`'s
  drill drawing text on layer 73 (S-2236). Proof: the scratch slot census against the cached corpus.
- [x] 6.4 A model body, and a footprint's generated model whose bodies share a layer, goes back on its source
  body's mechanical layer (`models.read_layers`), so row `-05`'s Mechanical 13 and row `-01`'s Mechanical 14
  stay disabled (S-2284). Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k "layer_of_model or body_layer"`.

## 5. Evidence and docs

- [x] 5.1 Row in `pcb-records.md`, H-A-CONV-BOARD6, S-2230 to S-2233, CHANGELOG.
- [x] 5.2 Kit: Altium opens the flow A round trips of the authored regression control and row `-04` with
  metric units, the source's mechanical names and enabled flags, and row `-05` with its black mask.
  Save and reopen the control and report whether the superclasses come back (S-2233, S-2297).
  Deferred to v0.8 (coordinator, 2026-11-07): not run before the cut of 0.7.0; the code ships.

  Public flow A follow-up, 2026-11-10: all three steps ran on rows `-04` and `-05` using reviewed
  plans. Altium 24.5.2.23 opened both originals and both returns. It reported metric for both copies
  of row `-04`, imperial for both copies of row `-05`, and matching names and enabled flags for all
  sixteen mechanical slots of each pair. Native TSV SHA-256:
  `a07fda29f89a07cca0417e835a0833e6199140792a16a6d55b1c7c10e4664d5e`.
  The pre-save record comparison confirmed both black solder-mask fields in row `-05` and found no
  serialized built-in superclasses in the returns.
  Native save-as follow-up (S-2292): Altium opened and saved both returns to separate files. Each
  saved file has all ten built-in superclasses with the same names and kinds as the source. The
  saved row `-05` has zero for both solder-mask colour fields. Native 3D inspection (S-2294)
  showed black solder mask on the visible front areas of both the original and the return. The
  source and return captures have SHA-256
  `0e7f97f38e967e4f896b035f98bc53376ea7856029a3e99413a6b8291893d10c` and
  `353077618fb3955018ab1d5fede04c6b23cb4a5139aa8ba3e1c52f8ef2750a4a`, respectively.
  The historical maintainer board from S-2235 could not be located. For acceptance, an independently
  authored control substitutes for that board and reproduces its reported counts on the same baseline
  commit `332b79837`: two renamed mechanical slots and four changed enabled flags. This records the
  tested substitute and leaves S-2235 as a historical author report.

  Altium 24.5.2.23 opened, saved to separate files, and reopened the authored source and both returns.
  The baseline changed names on slots 3 and 4 and flags on 3, 4, 5 and 7. The corrected flow A return at
  `b25af4641` preserved all sixteen names and flags, metric display, both drill tracks (layers 55 and
  73), and both black mask fields. The native source and corrected saves each have the same ten
  built-in superclasses. All staged inputs retained their hashes. Native TSV SHA-256:
  `d43b42f1a11dc513f85fc3e08419b497ebccfdc637d527a38d07867fe12f39b4` (S-2297).
