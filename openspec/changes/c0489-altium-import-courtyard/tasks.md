# Tasks: c0489-altium-import-courtyard

Rules for every task:

- Public sources only. Each format fact goes in `docs/formats/altium/` with an S- id and an evidence label.
- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages. Test documents are authored for Fenolite and written by Fenolite's own writer.
- Run each touched test file alone with `-n 0`.

- [x] 1.1 Look for a public source that states the kind of a mechanical layer (courtyard, assembly) in a PCB
  document; record the key, or record it as `UNKNOWN`, in `docs/formats/altium/pcb-records.md`; record
  `DERIVED_COURTYARD_MARGIN` and `H-A-IMP-COURTYARD` in `docs/formats/altium/import.md`.
  - Proof: `uv run --extra dev pytest tests/unit/test_format_facts.py tests/unit/test_docs_altium_read.py -q -n 0`
- [x] 1.2 Derive the courtyard on import (`adapter/courtyard.py`, called from `adapter/board.py` and
  `adapter/library.py`) and mark it; tests for "Body larger than the pads" and "A footprint without a body".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_derived_courtyard_c0489.py -q -n 0`
- [x] 1.3 Give `frame.placed_extents` the derived ring with `source == "derived"`, and add `derived` to
  `PlacedExtent.source`; test for "Two bodies that overlap".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_frame.py tests/unit/placement/test_legality.py -q -n 0`
- [x] 2.1 Skip a derived courtyard in the Altium writer, carry it through KiCad in
  `Fenolite.Altium.DerivedCourtyards`, and skip a matching one on the way back; tests for the two scenarios
  of "A derived courtyard is not written back to Altium".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_derived_courtyard_c0489.py -q -n 0`
- [x] 2.2 Run the conversion tests that count footprint drawings and Board6 mechanical layers.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_board6_settings_c0464.py tests/unit/convert/test_long_mechanical_c0450.py -q -n 0`
- [x] 2.3 Regenerate the schemas if `PlacedExtent` or a carrier schema changed.
  - Proof: `uv run python tools/gen_schemas.py --check`
- [x] 3.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [x] 3.2 Maintainer board (private, codes and counts only): after import, every footprint without its own
  courtyard has a derived one; `place` on the imported board reports `place.courtyard-overlap` for parts
  whose bodies overlap; Altium → KiCad → Altium writes no courtyard drawing that the source lacks, and the
  round-trip equivalence still exits 0. Left open: maintainer runs it (private board, and the round trip
  in the VM).
  Result (maintainer board, 2026-11-16): FAIL. 266 of 266 derived courtyards; the round trip writes no extra drawing; but `place` reports 107 `place.courtyard-overlap` (KiCad 102 `courtyards_overlap`) where Altium's DRC reports 0 component-clearance violations: the hull of bodies and pads is too large (a large part's courtyard covers parts under it). Follow-up.
  Result after the fix (maintainer board, 2026-11-16): PASS with a remainder. `place --dry-run` on a fresh
  KiCad conversion: 13 `place.courtyard-overlap` (was 107), 10 `place.outside-outline`; KiCad DRC 13
  `courtyards_overlap` (was 102); convert exit 0. Remainder: 9 pairs are overlaps of the bounding outline of
  one 3D model (repeated part, body through the board) with its neighbours, where Altium checks the model's
  real shape; 2 are the pad hull of a part without a body over another part's pads; 2 come from the convex
  hull of a sparse part. Each is on the safe side of `H-A-IMP-COURTYARD`; closer agreement needs 3D model
  shapes, which the import does not read. The Altium-side round trip is unchanged by the fix (derived
  courtyards are never written).

## Decisions

- Decision (maintainer, 2026-11-16): no public source read states a mechanical layer's kind (task 1.1), so
  `pcb-records.md` records it `UNKNOWN`, steps 1 and 2 of the order are off, and every footprint takes step 3.
- Decision (maintainer, 2026-11-16): the adapter may not import `backends.altium.frame`
  (`test_package.py`), so `adapter.courtyard.pad_corners` bounds each pad's copper by the rectangle of its
  size (and of each stack layer's size at its offset) turned by the pad's angle. It holds every pad shape,
  the same superset the frame uses for a shape it does not resolve.
- Decision (maintainer, 2026-11-16): the growth is the Minkowski sum with the octagon circumscribing the
  circle of the margin (integers, ceil of m·√2), so the polygon holds the hull grown by 0.25 mm; the stroke
  of the drawn polygon is 0.05 mm and is no part of the extent.
- Decision (maintainer, 2026-11-16): bodies whose projection or heights are unknown (c0099) are left out,
  as D2 says; a library definition takes the top side (`F.CrtYd`).
- Decision (maintainer, 2026-11-16): the carrier holds each courtyard's footprint reference, layer and points
  in the footprint frame, not the footprint position: the footprint frame is the same in the KiCad board and
  the Altium import whatever origin the conversion chooses, so a match within 1 nm needs no frame shift.
- Decision (maintainer, 2026-11-16): the derived courtyard is stripped once at the top of
  `lower.from_design`, so no writer path and no report row sees it; the way back strips matching polygons in
  `to_altium` before lowering.
- Decision (maintainer, 2026-11-16): `place.keepout-no-courtyard` covers `derived` too, worded "the derived
  courtyard of X"; the height check notes "(approximate extent)" for it as for `pads`.
- Decision (maintainer, 2026-11-16): the scenario "Two bodies that overlap" is tested on
  `placement.legality.check` over `frame.placed_extents`, what `fenolite place` judges, without the CLI.
- Decision (maintainer, 2026-11-16): `checks.diff` leaves derived courtyards out of `footprint_graphic`:
  they are no source item, so a model round trip (rta3, `test_lower.py::test_build_agrees`) compares the
  source's drawings only. Tests that count a footprint's source drawings filter them with
  `adapter.courtyard.is_derived`; a conversion to KiCad counts and writes them (`footprint-graphic` rows
  grow by one per footprint).
- Decision (maintainer, 2026-11-16): the board view names the courtyard layers of an Altium board "Derived
  Top Courtyard" and "Derived Bottom Courtyard", with tabs after every Altium layer, so no layer shows its
  model name (`test_altium_layer_names.py`).
- Decision (maintainer, 2026-11-16): the view's overlap notes on the public boards grow
  (`test_board_annotations_public.py`, census of 2026-11-16: -01 5 → 241, -02 0 → 2, -04 1 → 9, -05 0 → 2,
  -06 0 → 4, -07 0 → 11). That is the change's purpose: body outlines now count. The hull and 0.25 mm margin
  overstate dense parts (each pair closer than 0.5 mm overlaps); the maintainer judges the -01 count in 3.2.
- Decision (maintainer, 2026-11-16): task 3.2 fix. A body raised above the board (`standoff > 0`) is left
  out of the derived courtyard: Altium's Component Clearance in its Specified vertical mode accepts one
  component overhanging another (S-0461). Measured on the maintainer board: 107 → 90 at the old margin.
- Decision (maintainer, 2026-11-16): `DERIVED_COURTYARD_MARGIN` is 0 (was 0.25 mm). Altium measures the
  clearance between the bodies themselves with the rule's horizontal clearance, which the import carries as
  `courtyard_clearance` from `GAP`; a margin on each courtyard counted it twice (every pair closer than
  0.5 mm overlapped). No public page read gives the rule's default clearance, so the row is `INFERRED`.
  Measured: 107 → 24 alone, 13 with the raised bodies left out.
- Decision (maintainer, 2026-11-16): the union of per-element hulls (pads, each body) instead of one convex
  hull is not taken: measured on the maintainer board it changes 107 → 105 at the old margin and nothing
  (13 → 13) with the two choices above, and it would need several rings per footprint in the carrier and the
  frame. The L-shaped test records that the hull covers a notch (safe side).
- Decision (maintainer, 2026-11-16): the public boards' overlap notes after the fix
  (`test_board_annotations_public.py`, census of 2026-11-16): -01 241 → 9, -02 2 → 0, -04 9 → 2, -05 2 → 0,
  -06 4 → 0, -07 11 → 1, -08 528 → 6 (heavy item, local `FENOLITE_HEAVY=1` run).
- Decision (maintainer, 2026-11-16): the new extension-bag key `altium:derived` is approved in
  `model0-approved.json` (as c0450 and c0460 did), and `fenolite inspect` of `blink.PcbLib` counts 30
  graphics (27 drawn, 3 derived).
