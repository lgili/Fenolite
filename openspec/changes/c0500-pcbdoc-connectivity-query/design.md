# Design: c0500

## D1 One union, made public

There is already one union of touching copper: `geometry.touch_groups`, used by
`analysis.connectivity._groups` (islands and open connections), by `analysis.ties` (tie proofs) and by
`checks.equivalence.routing.pieces`. This change adds no union. `net_islands` already returns, per net,
the counted islands with pads, anchors, items and zones. What a script lacked was:

1. a name and layers for each item, so it can say "this track" back;
2. a way to compute the islands without some items;
3. a public, documented door.

`IslandItem(kind, id, where, layers)` is built from the `CopperShape`s that `_groups` already holds
(`kind`, `entity_id`, `where`, `layer`), one per item with its layers merged and sorted.
`NetIsland.members` is the sorted tuple. `NetIsland.items` stays for `roles.proposals`. Fill-only islands
stay out of the result, as in `connectivity` (`COUNTED`).

## D2 Removal by name

`ties._names(design)` becomes the public `ties.item_names(design) -> dict[str, set[str]]`. It maps each
track, arc, via and zone id to its model id, native ids and locator. `net_islands(..., without=names)`:

1. resolves each name through `item_names`. A name that matches nothing raises `KeyError(name)`, and the
   CLI turns that into `FEN-2001` with the three closest names;
2. drops every `CopperShape` whose `entity_id` is a resolved id (a zone drops all its fill polygons);
3. groups as before.

Pads are not removable. Removing a pad is removing a part, and `analyze --kinds ties --tie REF` already
proves that case. `without` is for copper the user would cut.

Why not run `analyze_ties`: a tie proof asks whether removing the items splits the copper that touches
them, and reports `tie-parallel` or `tie-dangling` findings. A what-if asks for the islands of a whole net
after the cut, findings or not. Both use one name resolver and one union. Only the question differs.

## D3 No repour

On a `.PcbDoc` the zones are their saved fills (`altium-pour`). After a removal, a fill keeps its saved
shape. It does not grow into the freed space, and a thermal or spoke stays where it was saved. So a cut
can show an island that a repour in Altium would join again. Making the pour engine part of the query
(`analysis.pour.PourCopper`, as `connectivity(..., pour=)` takes it) is possible later, but it needs the
`geo` extra and is not exact (`POUR_EVIDENCE`). Recorded in code as
`shortcut: saved fills are not repoured after a cut; pass pour= when the pour engine is wanted`, and said
in `result.net.cut.note` when the net has a zone.

## D4 CLI

`fenolite net PATH NAME --islands [--without A,B] [--without C]`:

```json
{"net": {"...": "the existing view",
  "island_list": [{"pads": ["R1-1", "R2-2"],
               "members": [{"kind": "track", "id": "…", "where": "Tracks6/Data#12", "layers": ["F.Cu"]}],
               "zones": ["…"]}],
  "cut": {"removed": ["Tracks6/Data#12"], "islands_before": 1, "islands_after": 2, "split": true,
          "note": "saved fills are not repoured"}}}
```

The list is `island_list`: `islands` already is the island count of the view (an int), and the
existing keys stay unchanged (decided 2026-11-13 by the implementer, under the maintainer's delegation).
`--islands` needs `NAME`, because islands of every net would be a page of thousands of items. Without
`NAME` it exits 2 (`FEN-2001`). `--without` implies `--islands`. `paged` gains `net.island_list`. The view's
existing keys are unchanged.

## D5 Frames and units

Three frames, all named in `docs/api.md`, "Frames and units":

| frame | unit | Y | origin | who uses it |
|---|---|---|---|---|
| native | 1/10 000 mil | up | Altium's absolute zero | the raw records (`read.pcb`) |
| model | nm | down | the native zero | `Design`, `check`, `net`, `analyze` |
| board | nm | up | the board origin (`ORIGINX`, `ORIGINY`) | the Altium editor, `edit` sessions |

```python
@dataclass(frozen=True, slots=True)
class Frame:
    origin: Point   # the board origin in the model frame
    y_up: bool      # the board frame's Y points up
    def from_native(self, x: int, y: int) -> Point      # native units -> model (adapter.units.pcb_point)
    def to_native(self, p: Point) -> tuple[int, int]    # model -> native units (nm_to_u, Y negated)
    def to_board(self, p: Point) -> Point               # model -> board
    def from_board(self, p: Point) -> Point             # board -> model

def board_frame(board: Board | PathInput) -> Frame
```

For an Altium board, `origin` comes from `backends.altium.frame.board_origin(design)`. It reads the
`origin` pair the import keeps in the board's bag (`import.md`: "`ORIGINX,ORIGINY` as written") and
converts the mil text with `adapter.units.text_length` and the Y flip. `y_up` is true. A board of any other
backend has `origin` (0, 0) and `y_up` false, so `to_board` is the identity. `from_native` and `to_native`
raise `SideUsageError` on a non-Altium board, since there is no native unit to convert.

`altium_to_nm` and `nm_to_altium` are `core.units.u_to_nm` and `nm_to_u` (half to even). `format_length`
and `parse_length` are those of `core.units`. All four are re-exported, not rewritten. Floats appear
nowhere. `format_length(nm, "mm")` is the display.

The edit session reads the origin from the record (`edit.ops.View`). The test of task 3.2 asserts that
`board_frame(read_board(doc)).to_board(p)` equals the point the session expects for the same record, on
the authored documents, so the two cannot drift.

## Alternatives

- **A new `fenolite islands` command.** Rejected: `net` already describes one net and already counts its
  islands. A second command would split one view.
- **Public raw-record helpers** (`RawPrimitive` with mm properties). Rejected: they would freeze the raw
  reader as API. Scripts should read the model through `read_board` and convert with `Frame`.

## Risks

- `members` makes the `net` reply large on a ground pour with thousands of track pieces. Mitigation:
  `--islands` needs one net and `paged` covers `net.island_list`. `--fields` already trims.
- Locators are `<Storage>/Data#<index>`, which an edit renumbers. A name from one read is valid for that
  read only, and the docs say so.
