# c0500: islands of a net, cut what-ifs, and frame helpers for board scripts

Found on: editing a private maintainer board, a dense two-layer power board, in November 2026 (codes only;
nothing from the board is in this change).

## Why

Scripts that edited an Altium PCB document had to answer two questions again and again: "is this net one
piece, and which pads are on which island?" and "what happens if I cut this track?". No public call
answers either with the members of each island, so they reached for private readers and units:

- **F39: no island query with members.** `analysis.connectivity.net_islands` already groups a net's copper
  into islands with their pads, items and zones (change c0280). It is not public, and `fenolite net` shows
  only the pads of each island. Its items are `(kind, entity_id)` pairs with no locator or layer, so a
  script cannot name them back. `analysis.ties` removes items by id and regroups (`Tie.of_items`), but only
  to prove a tie. It answers "is this the only joint", not "what are the islands after the cut". The
  scripts rebuilt the union four times on `read.pcb.read_pcbdoc` and `pcbprims.RawPrimitive`.
- **F43: no units or frame helpers.** The raw reader gives 1/10 000 mil units in Altium's frame (Y up,
  absolute). The model is nanometres with Y down and no origin subtracted (`import.md`, "Units and frame").
  The edit session takes nanometres from the board origin, Y up (`edit.ops`). Three frames, and the
  conversions live in private places: `adapter.units.pcb_point`, `edit.ops.View.units`, the `origin` pair
  of the board's bag. Every script carried its own lambda, such as `mm = v*2.54e-6 - 25.4`, and its own
  origin offset.

Change c0495 (b) makes `fenolite net` and `region` read a `.PcbDoc`. This change builds on it and does not
repeat it.

## What Changes

- **Islands with members.** `net_islands` gains `without` and every `NetIsland` gains `members`: one
  `IslandItem(kind, id, where, layers)` per pad, track, arc, via and fill of the island, sorted. `where` is
  `REF-PIN` for a pad and the provenance locator otherwise, the names `check` and `analyze` use.
- **Cut what-if.** `without` is a collection of item names: model id, native id or locator, as
  `--tie-item` takes them, resolved by the same function, which `analysis.ties` makes public as
  `item_names`. Tracks, arcs, vias and whole zones may be removed. The islands are computed on the copper
  that remains. Saved fills are not poured again (design D3). An unknown name is an error, never a silent
  no-op.
- **CLI.** `fenolite net PATH NAME --islands [--without ITEM[,ITEM…]]` adds `result.net.islands` (pads,
  members, zones per island) and, with `--without`, `result.net.cut` (`removed`, `islands_before`,
  `islands_after`, `split`). It reads a `.PcbDoc` through c0495 (b). Read-only, runs no tool.
- **Python API.** `fenolite.api.islands(board, *, nets=None, without=())` returns the `NetIsland`s per net.
  `fenolite.api.board_frame(board)` returns a `Frame` with `origin` and `y_up` and the conversions
  `from_native`, `to_native`, `to_board` and `from_board`. Also `altium_to_nm`, `nm_to_altium`,
  `format_length` and `parse_length`. All are listed on `docs/api.md` with an example that replaces the
  lambdas.
- One origin parser, `backends.altium.frame.board_origin(design)`, which `board_frame` uses. The edit
  session's own origin reading stays where it is (it reads records, not the model). A test asserts the two
  agree on the authored documents.

## Impact

- `src/fenolite/analysis/connectivity.py` (`net_islands`, `NetIsland.members`, `IslandItem`),
  `src/fenolite/analysis/ties.py` (`_names` becomes `item_names`).
- `src/fenolite/cli/cmd_net.py` (`--islands`, `--without`).
- `src/fenolite/api/__init__.py`, new `src/fenolite/api/frames.py`, `src/fenolite/api/board.py` (`islands`),
  `src/fenolite/backends/altium/frame.py` (`board_origin`).
- `docs/api.md`, `docs/analyses.md` ("Open connections"), `docs/cli-contract.md` ("net"), the agent guide
  pages `board-grounds.md` and `altium.md` and the generated command pages, `CHANGELOG.md`.
- `roles.proposals` calls `net_islands`. It keeps its arguments, and `members` is an added field.
- Nothing is written to any board. No model or schema of a saved file changes. The `fenolite net` result
  gains keys only with the new options.
