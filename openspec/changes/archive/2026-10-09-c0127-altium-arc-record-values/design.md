## Context

- **Today.** `adapter/copper.arcs` reads a free arc record of `Arcs6` (centre, radius, start and end angle) and gives the model three points: `adapter.units.arc_points` puts start, middle and end on the circle and rounds each to a nanometre. On copper the result is an `Arc`, elsewhere a `Graphic` of kind `arc`. The bag holds `u` and `deg` only for a value whose conversion was inexact. The writers go the other way: `pcbrecords.arc_from_points` computes the circle through three points and rounds its centre and radius to a unit of 2.54 nm.
- **What it costs.** Measured on 2026-10-06 on the base commit `ba21a109` (`FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rta3.py -q`: 15 passed, with `altium-third-party-pcbdoc-08` listed in `NOT_EQUAL`): of the 529 copper arcs of that document 517 are written, 7 of them differ inside the scope (14 changes), and 12 are refused because their three points lie on one line. The 23 written arcs of the two other public documents with arcs come back within 2 nm. A short arc is the hard case: three points that are a few nanometres apart say little about a circle.
- **Decision of the maintainer** (design of c0090, 2026-10-06, decision 2): the record's own centre, radius and angles are kept for an arc that was read; "until it lands the 2 nm claim excludes arcs".
- **Constraints.** No change of the model. A build from a script keeps its bytes. A bag is data of the backend that read the file (`docs/design-model.md`): another backend does not read it, and an edit of the model does not update it, so a writer that uses it must check it.

## Goals / Non-Goals

**Goals:**
- An arc that was read and not changed is written with the record it was read from.
- An arc that was changed in the model is written from its points, as before, without a message.
- The heavy public document is equal inside the written scope.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **One pair, the whole record.** `("arc", "<cx>,<cy>,<radius>,<start>,<end>")`: three integers of 1/10 000 mil in the document's frame and two doubles as `float.hex()`. The pairs `u` and `deg` already hold some of these values, but only the inexact ones and under field names; a writer would have to recover the exact ones from the model's points, which is the conversion that does not close. One pair that is always there is read with one split. It is placed after `via_layers` in `EXT_KEYS`.
2. **Which entities get it.** Every entity that `adapter/copper.arcs` makes from an arc record that is not a full circle: the `Arc` on copper and the `arc` graphic elsewhere. They take the same import function and the same two conversions, so the graphic gets the same treatment, although RT-A3 does not compare graphics.
3. **The check before use.** `lower.kept_arc(entity, points, frame)` converts the pair with the import's own `adapter.units.arc_points` and compares the three points with the entity's points in the frame of the written document, per axis, within `ARC_TOLERANCE` = 2 nm (the length tolerance of `RT_A2_SCOPE`). An untouched arc gives exactly its points. A moved, reshaped or reversed arc, and a board that is written in another frame than the document's (a build frame), fail the check: the pair is stale, and the arc is written from its points. A stale pair is no issue: the model is the truth, and the bag is a hint.
4. **Inside the tolerance the record wins.** An arc that was moved by 2 nm or less is written with its first record. That is inside what the scope calls equal, and it keeps the check free of a second rule.
5. **Collinear points.** `pcbrecords.arc_from_points` refuses three points on one line, and `lower` counted such an arc as not written. With a kept record there is nothing to derive, so the arc is written. The refusal stays for an arc without a usable record.
6. **Where the writer takes it.** `PcbDocSpec.arc_records` maps an entity id to an `ArcGeometry`; `routed_arcs` and `free_records` use it when the id is there. `pcbdoc` reads no bag and imports nothing of the adapter. The default is empty, and the build passes nothing.
7. **The pair is not checked against a width or a layer.** They come from the model, as before; only the geometry of the circle is taken from the record.
8. **`H-A-VER-RTA3` becomes `CORPUS-VERIFIED`** (decision of the maintainer, 2026-10-07). The reason: with this change `altium-third-party-pcbdoc-08` is equal, so the row's criterion holds, equal on the eight listed documents, the seven that are not heavy from six repositories; the proposal of c0090 names this level for this case. The evidence of a stage must carry its row's level (`tests/unit/backends/altium/test_roundtrip.py::test_scope_holds_the_required_fields`), and c0090's requirements "Round-trip level RT-A3" and "Altium check stage evidence" said `INFERRED` for `roundtrip.EVIDENCE_RT_A3`; both are MODIFIED here and the constant follows. What does not move: `rta3.rt_a3` combines the constant with the import's evidence, which is `INFERRED`, so every verdict, stage and envelope still reports `INFERRED` (three tests that assert that are unchanged; the one that asserts the constant is changed); `lower.EVIDENCE` and the `write` cell of `altium_pcbdoc` stay `INFERRED` (they also name `H-A-VER-RTA2-3`); `claims.py` sets no `roundtrip_exact` cell (its rule asks for nothing unwritten); `capabilities` names no write kind. The level says that Fenolite reads its own rewrite of a public Altium PCB document back to an equal model inside the written scope; it says nothing about Altium opening a written file.
9. **Cut order.** First the graphics (decision 2), then the collinear arcs (decision 5); never the stale check and the corpus run.

## Files and public API

- `src/fenolite/backends/altium/adapter/ids.py`: `EXT_KEYS` gains `arc`. `adapter/copper.py`: `arcs` adds the pair.
- `src/fenolite/backends/altium/lower.py`: `ARC_KEY`, `ARC_TOLERANCE`, `kept_arc(entity, points, frame) -> pcbrecords.ArcGeometry | None`; `from_design` fills `PcbDocSpec.arc_records`.
- `src/fenolite/backends/altium/pcbdoc.py`: `PcbDocSpec.arc_records`, `routed_arcs(arcs, copper, records=None)`, `graphic_problem(graphic, *, arc_known=False)`.
- Tests: `tests/unit/backends/altium/adapter/test_copper.py`, `test_ext.py`, `tests/unit/backends/altium/test_lower.py`, `tests/unit/backends/altium/test_pcbdoc.py`, `tests/corpus/test_altium_rta3.py` (`NOT_EQUAL`).
- Pages: `docs/formats/altium/import.md`, `docs/formats/altium/pcb-document.md`, `docs/altium.md`, `docs/evidence/altium-roundtrip.md`.

## Other places that hold an arc

| place | what it is in the model | this change |
|---|---|---|
| free arc record on copper | `Arc` | the pair is kept and used |
| free arc record on another layer | `Graphic` of kind `arc` | the pair is kept and used; not compared by RT-A3 |
| free arc record of 360 degrees | `Graphic` of kind `circle` (centre and one point) | not changed: centre and radius close within the rounding of a unit |
| arc record of a component in a PCB document | nothing (`record:footprint-graphics`) | not changed: no model entity; c0126 |
| arc record of a poured polygon | nothing (`record:pour-primitives`) | not changed |
| arc of a library footprint (`PcbLib`) | a graphic of the footprint definition | not changed: the library writer is the build's path, and no round trip of a library goes through the model |
| arc vertex of the board outline | an `arc` graphic on `Edge.Cuts` | not changed: no arc record; a write gives two straight edges and counts them (`outline`) |
| arc vertex of a zone outline | `outline == ()` | not changed: the zone is counted as not written |

## Measured (2026-10-06, macOS, local corpus cache)

Counts only. Before: the base commit `ba21a109`. After: this change. `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rta3.py -q`.

| `altium-third-party-pcbdoc-08` (heavy) | before | after |
|---|---|---|
| verdict inside the scope | differs: 7 arcs (14 changes), first `/arc/0` | equal |
| copper arcs of the model | 529 | 529 |
| arcs written | 517 | 529 |
| arcs not written (three points on one line) | 12 | 0 |
| arcs written from a kept record | 0 | 529 |
| largest move of a point of a written arc, per axis | 3 nm | 0 nm |
| pads, tracks, vias, zones written and equal | 2115, 8355, 1770, 27 | 2115, 8355, 1770, 27 |

| the eight PCB documents | before | after |
|---|---|---|
| equal inside the scope | 7 | 8 |
| copper arcs written (documents 06, 07 and 08) | 3, 20, 517 | 3, 20, 529 |
| largest move of a point of a copper arc (06, 07, 08) | 2 nm, 2 nm, 3 nm | 0 nm on each |
| arc graphics off copper that are written (document 06), largest move | 8, 1 nm | 8, 0 nm |
| every other written and unwritten count of the eight documents and five sets | | not moved |

- **The test run**: 15 passed before (with the heavy document listed in `NOT_EQUAL`) and 15 passed after (with `NOT_EQUAL` empty). The project set `altium-set:01`, which holds the heavy document, stays not judged for its schematic; its PCB document now counts 529 arcs written and none unwritten.
- **The largest moves** are measured by pairing each written arc of the first reading with the nearest arc of the second reading; the verdict of the level is `checks.diff.diff_designs` under `RT_A3_SCOPE`.
- **KiCad's importer on the rewrites** (`tests/kicad/altium/test_rta3_oracle.py`, `kicad-cli` 10.0.6): 11 passed, no difference and no exclusion on the two own documents and the seven public documents that are not heavy, as before; the documents 06 and 07 are now written with their arcs' own records. The heavy document is not part of that test.
- **Own samples**: `tests/data/altium/routed/routed.PcbDoc` holds one free arc. Its rewrite now holds the record of the sample to the last bit of the angles; derived from the three points, the angles were other doubles (89.99997… instead of 89.99995… degrees), inside 2 nm. No committed file changes: a rewrite is written to a temporary folder.

## Sources registered by this change

- None. The arc record is a row of `docs/formats/altium/pcb-read.md` (c0041) and of `pcb-copper.md` (c0038); the change stores values that the reader already reads. The ids S-0560 to S-0564 that were reserved for this change stay unused.

## Hypotheses registered by this change

None. The change is settled by the existing row `H-A-VER-RTA3` (c0090), whose criterion it lets the heavy document meet, and by unit tests. No id is added to `docs/hypotheses.md`; the level of that row changes (decision 8).

## Size (design-days)

| group | dd |
|---|---|
| entry, measurement before | 0.25 |
| the pair in the import | 0.25 |
| the writer option and the check in the lowering | 0.25 |
| corpus run, pages, closing | 0.25 |

Total: 1. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-import`, MODIFIED "Extension bags": copied from the living text of `openspec/specs/altium-import/spec.md`; the list of keys gains `arc`, one bullet says what the pair holds, one scenario is added. No active change holds a delta for this requirement (checked 2026-10-06 over `openspec/changes/*/specs`).
- `altium-pcb-writer`, MODIFIED "Imported boards are written from the model" and "Writer options for a model that was read": both are ADDED by c0090, which is implemented and not archived, so the living spec does not hold them. The text is copied from the delta of c0090 (`openspec/changes/c0090-altium-roundtrip-write/specs/altium-pcb-writer/spec.md`) with one bullet and two scenarios added to the first, one clause added to its list of items that are not lowered, and one bullet added to the second.
- `altium-verification`, MODIFIED "Round-trip level RT-A3" and "Altium check stage evidence": the first is ADDED and the second MODIFIED by c0090 (which copied it from c0088's delta), so the text is copied from the delta of c0090 (`openspec/changes/c0090-altium-roundtrip-write/specs/altium-verification/spec.md`); in each, the level of `EVIDENCE_RT_A3` changes from `INFERRED` to `CORPUS-VERIFIED`, with what the level means in the first.
- Archive order: after c0090 (else the MODIFIED requirements have no base), before c0128, whose deltas start from the text of this change.

## Risks / Trade-offs

- [The bag and the points disagree after an edit] → the check of decision 3; a test moves an arc and reads the written record.
- [The content of imported boards with arcs changes] → one more pair per arc; the changelog says so. No id changes, because a content id is built from model fields.
- [A hand-written pair with values that no record holds] → the parse accepts three integers of 32 bits and two finite doubles only, and the result must still give the entity's points.
- [A design that is read, moved as a whole and written] → every pair is stale and every arc is written from its points, as before this change.

## Migration Plan

- None for callers: no signature of a public function loses an argument. A stored model of an imported board that was written before this change holds no pair and is written as before.
- Rollback: `from_design` passes no `arc_records`.

## Open Questions

- **Should a stale pair be removed or reported?** Default: no. A write does not change the model, and a pair that no longer fits is ignored silently; a command that edits imported boards may drop it when it moves an arc.
