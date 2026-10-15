## Outcome in one paragraph

**The bytes that make a via padless on a layer were found, and the 29 false findings are gone without leaving anything unjudged.** The long via record of `altium-third-party-pcbdoc-08` differs from the ordinary one in two places: a table of thirty-two bytes at offset 209, which is zero in every other via record of the eight public documents and holds 1 for some inner layers in all 123 long records, and a block of nine constant bytes with its count and its length before it. The table agrees with the copper of the document at every place that can be tested, and with what Altium's documentation says of removed pad shapes; the nine bytes stay unexplained and are not read. The import keeps the layers in the via's bag; the Altium backend's view for the copper check gives such a via its drill as diameter on those layers. KiCad's importer does not read the bytes: it writes all 1 770 vias as plain through vias.

## Context

- c0088 gave Altium boards the tool-free copper check; c0130 put the heavy document into it and found the class ("Known false findings"), pinned by `test_known_false_findings_of_padless_vias_c0132`.
- `model.board.Via` holds `position`, `diameter`, `drill`, `layers` (the two ends), `net_id` and `via_type`: one diameter, no per-layer statement. `checks/copper.py` draws a via as one disc of its diameter on every copper layer of its span (`_Items._vias`, `span`).
- Another session's change edits `checks/copper.py`; this change must not.

## Measured before (2026-10-07, macOS, local corpus cache, throwaway scripts outside the repository)

### The forms of the via record over the eight public PCB documents

Lengths are those of the one subrecord (the record is 5 bytes longer: the type byte and the 32-bit length).

| row | vias | 299 | 321 | 330 | 351 |
|---|---|---|---|---|---|
| `-01` | 646 | 646 | | | |
| `-02` | 242 | | 160 | | 82 |
| `-03` | 47 | | 47 | | |
| `-04` | 67 | | 67 | | |
| `-05` | 59 | | 59 | | |
| `-06` | 42 | | 42 | | |
| `-07` | 60 | | 60 | | |
| `-08` | 1 770 | | 1 647 | 123 | |
| all | 2 933 | 646 | 2 082 | 123 | 82 |

Every one of the 2 933 has the stack mode 0 at 74 and, from 203 bytes on, thirty-two equal layer diameters; every one spans 1 to 32. So neither "Top-Middle-Bottom" nor "Full Stack" is in the corpus, and a per-layer diameter does not explain the class: **that hypothesis is refuted for these records.**

### What differs between the 321-byte and the 330-byte form (document `-08`)

| offset (330 form) | 321 form | 330 form |
|---|---|---|
| 209 to 240 | thirty-two bytes, all 0 (in all 2 164 records of 321 and of 351 bytes of the eight documents) | byte 209 is 0; bytes 210 to 213 are 1, a, b, 1; bytes 214 to 240 are 0. (a, b) is (0, 1) in 70 records, (1, 1) in 51, (0, 0) in 1 and (1, 0) in 1 |
| 246 | 32-bit 0 | 32-bit 1 |
| 250 | 32-bit 0 | 32-bit 9 |
| 254 to 262 | not there | nine bytes, the same in all 123: `04 00 80 01 00 71 02 00 00` |
| 263 on | the bytes that the 321 form has from 254 on (`2A`, the two ids, the tolerances, the polygon-connect count) | the same bytes, nine later |

Within the 123 long records only the net index, the position and the bytes 211 and 212 vary. All 123 are 16 mil vias with an 8 mil hole.

### The table against the copper of the document

The copper layers of `-08` are the layer ids 1, 2, 3, 4, 5 and 32 (`F.Cu`, `In1.Cu` to `In4.Cu`, `B.Cu`), so byte 208 + id belongs to the layer id. For every via and every inner layer, the nearest edge of the poured copper of another net was measured from the via's centre, and whether a track of the via's own net ends inside the via's pad on that layer. The generic clearance is 4 mil (101 600 nm); "at the hole" is the drill radius plus the clearance within 30 nm, "at the pad" the pad radius plus the clearance within 30 nm.

| form | byte | via-layers | pour at the hole | pour at the pad | own track ends on the via |
|---|---|---|---|---|---|
| 330 | 1 | 419 | 28 | 0 | 0 |
| 330 | 0 | 73 | 0 | 0 | 72 |
| 321 | 0 | 6 588 | 0 | 1 977 | 330 |

- The 28 places with the pour at the hole are the seven vias of the false findings on the four inner layers: all seven have the bytes 1, 1, 1, 1.
- **Not only those seven lack inner pads: all 123 long vias have at least two layers named**, 51 of them all four. The other 116 have no pour of another net near them on those layers (the nearest is beyond the pad radius plus the clearance), so they gave no finding.
- A byte of 0 in a long record is where the via is used: a track of its net ends on it on that layer in 72 of 73 cases. A byte of 1 is never where a track ends.
- No ordinary via has copper of another net nearer than its pad allows.

### What the public sources say

- Altium's documentation (S-0600): the tool "Remove Unused Pad Shapes" takes the pad shape of a pad or a via off each layer on which no other object touches it; polygons around it then keep the clearance to the hole and not to the edge of the removed shape; an option keeps the shapes on the start and end layers; the tool can restore the shapes. The page does not say how a document stores the state.
- KiCad 10.0.6, run as a subprocess on the document (S-0601; its source was not read): `kicad-cli pcb import --format altium` writes 1 770 vias, 1 735 of them of 0.4064 mm with a 0.2032 mm drill between `F.Cu` and `B.Cu`, and none with `remove_unused_layers`, `keep_end_layers` or `zone_layer_connections`. KiCad's import does not tell the 123 from the others.

### What is explained and what is not

- **Explained, with a field that is located:** the table at 209. The documentation states the behaviour (a removed pad shape, a pour at the clearance from the hole); the records and the copper of the one document agree at every place that can be tested (28 of 28, 72 of 73, 0 against).
- **Inferred, not proved:** that the index of the table is the layer id (as the table of diameters at 75 is read) and not the position in the stack. In `-08` the two are equal. Document `-07` has inner layers with the ids 3 and 5 and would tell, but holds no such via.
- **Not explained:** the 32-bit 1 at 246, the 32-bit 9 at 250 and the nine bytes. Their size reads as "one entry of nine bytes"; `00 71 02 00` inside them would be 160 000 units, the via's 16 mil, at an odd offset. No public source read says what they are. They are not read, not kept in the model and not written.

## Goals / Non-Goals

Goals: no false short from a pad that is not there; every via still judged on every layer; the fact on the facts page with its limits; no change of the model, of `checks/` or of a KiCad output.

Non-goals: the proposal lists them.

## Decisions

1. **Option (a), "the model already says it", is not available.** `Via` has no per-layer field, and the KiCad backend keeps `remove_unused_layers` of a via as an opaque child, not as a model field. Adding one is a model change with a KiCad writer consequence; it is out of scope here and listed below.
2. **Option (b) is taken: the bag and the view.** The import writes the pair `("pad_removed", "<id>,…")` into the via's `altium` bag, with the layer ids as the record holds them. The value is ids, as `via_layers` is, not model layer names: a bag says what the record says.
3. **What stands on a layer without a pad is the hole.** The via is drilled through every layer of its span; copper of another net inside the hole's radius would be cut by the drill and meet the plated barrel. So the honest copper of such a via on such a layer is a disc of the DRILL diameter, not nothing. The documentation says that a polygon keeps its clearance to the hole there, so the same clearance rules judge the disc. **A real short through such a via is still a finding;** option (c), leaving the via-layers out and reporting them unjudged, would have given that up and is not needed.
4. **How the view says it without touching the check.** `checks/copper.py` draws a via with one diameter on a contiguous range of layers: every copper layer for a through via, the range between its two layers otherwise. The view therefore replaces a via that has the pair by one via per run of alike layers, each with `layers=(first, last)` of its run, the type `buried` (so that the check takes the range and not the whole stack) and the diameter of the run. All parts keep the id, the provenance and the net, so a finding names the via that was read. Parts of one via lie on different layers and are never compared with each other. The type of a part is a property of the view, like the zone clearance of 0 in the same view; the imported design is not changed.
   - Cost, stated: `summary.items.via` of the stage counts parts, not vias (on `-08`: 2 160 for 1 770 vias), and two such vias that are too near to each other can be found once per pair of parts, where two ordinary vias are found once. The model extension of decision 1 would remove both.
5. **A layer id that is no copper layer of the via's span is ignored** by the view and kept in the bag. A via whose pair does not parse is left as it is.
6. **The reader gets a function, not a field.** `via_pad_removed(record)` reads `ViaRecord.tail`; the record class, its field table and the requirement that lists its fields are not changed. It reads the table in any subrecord of at least 321 bytes, not by the length 330: the table is in the 321 and 351 forms too (all zero there), and the nine bytes come after it.
7. **The rewrite does not write the long form.** A writer writes no byte it cannot name, and the nine bytes are not named. The written via has a pad on every layer; each such via is counted under the kind `via-pad-shape`, as the poured copper of a zone is counted under `zone-fill`: an information, not a loss kind, and the via stays in the comparison of RT-A3. The rewritten document also holds its polygons unpoured, so no written pour stands inside a written pad.
8. **Other readers of a via are not changed.** `analysis/views.py` and `checks/equivalence/routing.py` draw the via with its one diameter on every layer, as they do for KiCad boards; a via without a pad on a layer is not connected there, so its pad adds no connection of its own net. Level 5 of `equivalent` against KiCad's import compares the model, which is unchanged, and KiCad's import holds the same plain vias.

## Files and public API

- `backends/altium/read/pcbprims.py`: `via_pad_removed(record) -> tuple[int, ...]`, `VIA_PAD_TABLE = (209, 32)`, exported.
- `backends/altium/adapter/ids.py`: the key `pad_removed` after `via_layers`.
- `backends/altium/adapter/copper.py`: the pair, in `vias`.
- `backends/altium/backend.py`: `_with_removed_pads(design)`, first in the chain of `rules_from_bytes`.
- `backends/altium/lower.py`: the kind `via-pad-shape` in `MORE_KINDS`, counted in `_copper`.
- `backends/altium/import_evidence.py`: the hypothesis id.

## Sources registered by this change

| id | what |
|---|---|
| S-0600 | Altium's documentation page "Removing Unused Pads & Adding Teardrops" (read for facts, 2026-10-07) |
| S-0601 | the public document of S-0187 (corpus row `altium-third-party-pcbdoc-08`), read again with Fenolite's own reader and converted by `kicad-cli` 10.0.6 as a subprocess (2026-10-07) |

S-0602 to S-0604 are reserved and not used.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-IMP-VIA-PADLESS | The thirty-two bytes at offset 209 of a via subrecord of at least 321 bytes are indexed by layer id from 1, and a non-zero byte says that the via has no pad shape on that layer (Altium's "Remove Unused Pad Shapes"); copper around the via is then held at the clearance from its hole | author report: a four-layer board whose inner layers have the ids 3 and 5 (as `altium-third-party-pcbdoc-07`), one via with tracks on the top and bottom only, "Remove Unused Pad Shapes" run for vias, saved; and the corpus test `test_vias_without_inner_pads` | the saved record holds 1 at 211 and at 213 and 0 elsewhere in the table (index by id; 210 and 211 would be an index by position); on the public document every pour of another net on a named layer stands at the hole and none at the pad |

Starts `INFERRED`. The layout rows of the page are `CORPUS-VERIFIED`. The id has the stem of the import (`H-A-IMP-`) and is declared in `import_evidence.HYPOTHESES`: the stem `H-A-PCBX-` names claims of the build, which writes no such via (found on 2026-10-07 by `tests/unit/lens/test_altium_build.py::test_evidence`, which the first name failed). The id is in no other active change (checked 2026-10-07).

## Tests

- Unit, on authored records: the function on a long, an ordinary and a short subrecord; the pair of the import and the unchanged id; the view's parts and the three cases of the spec's scenario (no finding with the bytes, one short without, one short through the hole); the write's count.
- Corpus: `test_via_record_forms` (the table above), `test_vias_without_inner_pads` (replaces the pinned test: 0 shorts on `-08`, no finding with one of the 123 vias on a layer it names, and every finding that remains is of a class the evidence page names), `test_copper` on all eight rows, RT-A3 and the rule kinds.
- Oracle: `tests/kicad/altium` and `tests/kicad/equivalence`, unchanged and passing.

## Measured after (2026-10-07, same machine)

| `-08` | before | after |
|---|---|---|
| `copper.short` | 28 | 0 |
| `copper.clearance` | 17 | 16 |
| pairs judged | 60 253 | 59 571 |
| via items of the stage | 1 770 | 2 160 (1 647 vias and the 513 parts of the 123) |
| findings the unit's slack removes | 4 628 | 4 664 |
| RT-A3 | equal; 1 770 vias written | equal; 1 770 vias written; `via-pad-shape` 123 |

- The 29 findings that are gone are exactly the findings of the run before that name one of the 123 vias on a layer its record names; every finding that remains was there before, with the same gap. The 16 are 8 to 13 nm short of their rule, none with a pour (6 track to track, 8 track to via, 1 pad to track, 1 via to via): the class of c0131's open decision.
- Of the 36 more findings that the slack removes, 28 are the pours of another net against the holes of the seven vias, 1 to 3 nm short of the generic clearance: the pour stands at the clearance from the hole, to the rounding of its points. 9 more are pairs of two vias counted per pair of parts, and 1 fewer is a track beside a pad that is not there.
- The other seven documents: every count of their rows is unchanged (no via of them names a layer).
- KiCad's import of the samples and level 5 of `equivalent` do not move (the model is unchanged).

## Out of scope, with what each would need

- **A model field for a via without a pad on some layers** (and its KiCad form, `remove_unused_layers` with the layers that keep a pad): a change of `design-model`, of the KiCad reader and writer and of `checks/copper.py`, which would then count such a via once. Owner: the coordinator, with the session that edits `checks/copper.py`.
- **Writing the long form:** needs the meaning of the nine bytes (an author report: the same via saved before and after the tool ran, and after the option for the end layers is changed).
- **Pads of components** have the same tool in Altium. No pad record of the corpus was examined for it here; the 29 findings are vias only.
- **`analysis` and `equivalent`** keep the full pad on every layer (decision 8).

## Size (design-days)

| group | dd |
|---|---|
| measurement, sources, proposal | 0.5 |
| reader function, import pair, view, write count, tests | 0.25 |
| corpus tests, pages, measurement after | 0.25 |

Total: 1. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-pcb-reader`: ADDED "Removed pad shapes of a via record". It supersedes nothing: "Track, arc, via and fill records" lists the fields of `ViaRecord`, which do not change.
- `altium-import`, "Extension bags": MODIFIED from the text of c0127's delta (this branch). "Tracks, arcs and vias": MODIFIED from the text of c0124's delta (this branch).
- `altium-verification`, "Clearance rules of a PCB document": MODIFIED from the text of c0131's delta (this branch), which follows c0130's, c0125's and c0088's.
- `altium-pcb-writer`: ADDED "Removed pad shapes are counted, not written". It supersedes nothing: "Via records" states the 321-byte record, which is what is written.
- Archive order: c0088, c0124, c0125, c0127, c0130, c0131, then this change.
