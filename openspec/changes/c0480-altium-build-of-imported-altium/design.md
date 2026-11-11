# Design: c0480

## D1 The lens checks drawings with the writer's layer map

The PCB writer already knows the document's mechanical layers: `lower.built_mechanical(board)` maps
each used user layer named `Mech.<n>` or `Mechanical <n>` (`named_mechanical`) to its Altium id.
`lower_items` (texts, graphics) and `_document_holds` (footprint drawings) now check against the same
map, not the fixed `BOARD_LAYER_MAP` and `KICAD_MECHANICAL`. This avoids a second list of mechanical
layers that drifts from the writer's.

## D2 A script copper source does not report the script's items

A `script` source is the KiCad build of the same script. Its texts, graphics, keep-outs and holes carry
the ids of the design's board, from which the document writes them. `source_not_lowered(source, held)`
counts only the items whose id `held` does not hold. A `board` source (`--copper-from`) has its own ids,
so it is still reported in full.

## D3 Carried Altium boards build through the conversion writer

The carriers hold what the neutral model cannot: rule records as read, storages, union members and
names, embedded and stroke fonts, the frame and model ids. `convert.to_altium.write` already applies
all of them and verifies the result (c0434, c0450, c0460, c0466, c0467, c0470). Teaching the build lens
each carrier would duplicate that writer.

So `build --target altium` of a script with such carriers:
1. runs `_built` for `--target kicad`, with every `altium_*` option cleared, into a temporary folder;
2. writes the planned files there;
3. calls `api.conversion.convert(folder, to="altium", name=<design>, pour=--altium-pour,
   bodies=--altium-bodies, allow_lossy=--allow-lossy)`;
4. plans the conversion's files under `--out`.

- An error of the KiCad build refuses the Altium build with its issues.
- `--copper-from` keeps the old path, because the board it names is the copper source.
- The OutJob and the `.fenolite/` record of the old path are not written. The conversion's report
  stands in for them.

## D4 Not in scope

The two `equiv.route-vias` findings that F2 and F5 share are vias the source joins through its saved
polygon copper. Fenolite's computed pour leaves them as stubs; c0463 owns that.
