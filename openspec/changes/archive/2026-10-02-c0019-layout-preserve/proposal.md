## Why

Plan item 0011, part 2: `build` must keep the work done in KiCad. Today c0011 refuses every output edited since the last build (`build.layout-exists`, FEN-7001), so a moved footprint or a routed track survives only a build that does not run. KiCad keeps the uuid of every item it keeps when it re-saves a board (`H-K-UUID-KEEP-2`, S-0022), and c0011 gives every footprint a hidden `fenolite.path` property (`H-K-BUILD-PATHPROP`), so a rebuild can find the user's footprints. Placement, routing and zone fill (c0022, c0016, c0015) write into the board before the agent loop rebuilds.

## What Changes

- `src/fenolite/lens/preserve.py` (new; imports `model` and `backends`, never `geometry`): `match_footprints` (KiCad uuid, then `fenolite.path`, then a `moved()` alias), `effective_placements` (locked `place()` > existing board > `place()` > staging), `merge_layout`, `zone_digest`, `fill_inputs_digest`, `merge_rules`, `PRESERVE_ISSUE_CODES`.
- A rebuild keeps the position, rotation, side, lock and node of matched footprints, with the script's user properties (c0027); tracks, arcs, vias and zones whose net still exists; graphics, rule areas, title block and other board content; and fills while both digests are unchanged, else `zone.fill-stale`.
- Removed parts leave the board with `layout.orphan`. Footprints added in KiCad without `fenolite.path` stay (`layout.board-only`), their pins on their pads' nets; `check` asks them for no symbol.
- `.kicad_pro` is merged through c0010's `update_project`. User custom rules stay after Fenolite's (c0018's `parse_rules`, `print_rules`, then `write_rules` for target gating).
- `lens/build.py` (c0011): every build merges with a board, the existing one or the one it would write, so rebuilds and a regenerated `.fenolite/` are byte-identical. `--discard-layout` builds from scratch; c0011's refusal stays only for `fp-lib-table` and vendored footprints.
- `fenolite.dsl`: `Design.moved(old, new)` and `moves(design)`.
- Oracle on `kicad-cli` 10.0.6 and 9.0.9, probes first: a footprint moved by token edit, re-saved by `pcb upgrade --force` on 10.0.6, survives a rebuild with its tracks intact. `docs/lens.md`; hypotheses `H-K-LENS-KEEP` and `H-K-LENS-FILL`. No new source.

Budget: 8.25 working days (roadmap: 5); cut order in the design.

## Capabilities

### New Capabilities
- `layout-lens`: matching, placement precedence, what a rebuild keeps or drops, fill staleness, project and rules merge, the normal form, issue codes and evidence.

### Modified Capabilities
- `design-dsl` (c0011): ADDED "Path aliases in the DSL"; MODIFIED, copied in full from c0027's text (four) or c0011's, "DSL package", "Build command", "Built project files", "Edited outputs are not overwritten", "Build issue codes" and "Build evidence".
- `kicad-oracle`: ADDED "Preserved layouts pass the oracle".
- `verification-loop` (c0013): MODIFIED "Model validation stage", copied in full.

## Non-goals

- Zone filling (c0015), routing (c0016, c0023), grid placement and `place` (c0022).
- A `check` stage comparing the board with `.fenolite/`; DRC findings and RT2 (c0020).
- The full lens: extract, adapt, sync, `placements.toml`, `lens/moved.py`, module and net renames (v0.2b).
- Pruning stale vendored files, merging `fp-lib-table` rows, refreshing kept footprints from changed libraries.
- DSL zones and sheet keywords (v0.2a).
- Any model, schema, FEN-code, board-writer or layering change.

## Evidence level required

- Matching, precedence, merging, digests and determinism: mechanical (hermetic tests).
- A moved footprint survives a rebuild with its tracks intact (`H-K-LENS-KEEP`): `KICAD-VERIFIED` on 10.0.6 (local and `kicad-10`; target 10 re-saved, target 9) and on 9.0.9 (`kicad-9`, target 9; 9.0 has no `pcb upgrade`, S-0037).
- Kept fills: `INFERRED` (`H-K-LENS-FILL`) until c0015 refills a rebuilt board on 10.0.6.
- `build` over an existing board: `INFERRED`, lowest wins.

## Impact

- New `lens/preserve.py`; extended `lens/build.py`, `cli/cmd_build.py`, `checks/validate.py` and `dsl`.
- Registers: `hypotheses.md`, `LEGAL-ANNEX.md`, probe files, `board.md` rows.
- No runtime dependency (see Non-goals); the `build` result gains `preserved`.
- Depends on c0011, c0027 and c0013, archived first; through them on c0010, c0018, c0017 and c0009.
