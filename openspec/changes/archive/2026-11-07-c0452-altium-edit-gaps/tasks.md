# Tasks: c0452

- [x] 1.1 Spec: altium-edit "Edit session on an Altium document", "Asserted edits", "Records cloned from the
  document", "Operations gated by their hypotheses"; new "Arcs, fills, regions and polygons".
- [x] 2.1 Region move: twins taken before the record changes (`test_shapes.py -k region_move`).
- [x] 2.2 Matching: nearest record within `REACH`; `Track.width`; region twins within `REACH`
  (`test_shapes.py -k "width or rounded or twin"`).
- [x] 3.1 `Arc` and `Fill` items: move and delete (`test_shapes.py -k "arc or fill"`).
- [x] 3.2 Polygon move and `set_outline` (`test_shapes.py -k polygon`).
- [x] 3.3 `create`: `add_arc`, `add_fill`, `add_region`, `add_polygon` (`test_shapes.py -k add`).
- [x] 4.1 Rows `H-A-EDIT-SHAPE` and `H-A-EDIT-CREATE`, case J23, gates; phase B writes `shapes`, `create`
  and `set_outline` (`test_part_j.py -k phase_b`, `test_altium_verification_docs.py -k part_j`).
- [x] 4.2 Altium Designer opens the written documents of 3.1 to 3.3 and a fill created on a document it saved
  with one, with no message, and saves them (agent run through the maintainer's VM; S-2111 onward).
- [x] 5.1 `CHANGELOG.md`; light checks; the touched test files alone.
