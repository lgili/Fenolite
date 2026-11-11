# Design: c0474-altium-carried-harness-stream

## Context
An Altium schematic document holds harness records in a second CFB stream named `Additional`, with its
own header record; `FileHeader` never names them and they never name FileHeader records. The import
(`read.sch.document`) exposes both streams merged through `all_records()`, so the drawn carrier carries
them as opaque subtree items (`|RECORD=215|…` roots with `|RECORD=216|…|OWNERINDEX=@0` children) and
c0471 wrote them back wherever ordinary opaque records go: the `FileHeader` stream. This can produce
"Missing child-sheet in Symbol …" compiler errors.

## Root cause
The public format evidence in `docs/formats/altium/schematic-binary.md` describes harness records in
the `Additional` stream and their ownership conventions. Treating carried harness records as ordinary
`FileHeader` records puts them in the wrong index space.

## Decision
Route at the writer, not the reader: the drawn reader keeps carrying harness subtrees as opaque items
(KiCad cannot draw them), and the Altium writer decides where each record belongs.

- `drawn._Sheet` gains `carried_additional`; in the opaque loop, a root line whose `RECORD` is in
  `_ADDITIONAL_ROOTS = {215, 218}` sends the whole item to that list: each line's carried-relative owner
  index is remembered in an `additional[line]` map, children resolve their `@<line>` owner through it,
  and `natives` gets a `-1` sentinel so later siblings cannot name into the item. The item's own
  `OWNERINDEX`-like ownership validation still applies (`_OWNERS`).
- `SheetPlan.carried_additional` holds the tuples; `schdoc.additional_records` appends them after its
  own blocks, lines and polylines, shifting every `OWNERINDEX` behind the base count captured once
  before the carried loop, and omitting a final owner of 0 (native convention).
- `write_schdoc` (ASCII) refuses a plan with `carried_additional`: the ASCII form has no Additional
  section, as it has no harness records at all.
- `harness_blocks` occupancy counts `self.records` plus `self.carried_additional`, so a block is not
  placed over a carried connector.

## Alternatives rejected
- Writing an `Additional`-like section into ASCII: undocumented, and the ASCII form already refuses
  every drawn harness.
- Teaching the reader to drop harness records: loses carried connectors on a round trip.
- Emitting carried records with global FileHeader owner indexes (c0471's behaviour): exactly the defect.

## Consequences
- Written documents match the native stream layout; Altium's compiler accepts them.
- A carried connector keeps its original geometry, colours, entries and type text.
- Sheets whose source `Additional` stream holds only the header record (no records) now write no
  `Additional` stream at all.
