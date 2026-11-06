# c0431: the copper of a net-tie footprint in an Altium conversion

## Why

`convert --to altium` of a KiCad board whose net-tie footprint (`net_tie_pad_groups`) holds a copper
graphic, such as an F.Cu line that joins its two pads, reports a refused `footprint-copper` loss ("a graphic
of a footprint on a copper layer has no record written: it would be copper"). With `--allow-lossy` the
PcbDoc is open between the tied nets. `equivalent` misses the open: each pad keeps its own net, so levels 2
and 5 are unchanged, and no level compares a footprint's copper.

## What Changes

- Altium writer: the copper graphics of a footprint with net-tie groups are written as primitives of the
  Net Tie component (`COMPONENTKIND` 4, change c0420) on their signal layer, without a net: a line as a
  track, an arc or circle as an arc, a filled rectangle or polygon as a region. Altium's DRC ignores the
  shorts inside a Net Tie component (S-1900). A copper graphic of any other footprint, one on a plane, and
  one that no record holds stay a `footprint-copper` loss.
- `equivalent`: the level 3 kind `net-tie-copper` (`equiv.net-tie-copper`) compares the copper of a
  footprint that is a net tie on a side, in the footprint's frame, piece by piece within the length
  tolerance. A lost `footprint-copper` row explains it in a conversion's verification.

## Impact

- `src/fenolite/backends/altium/lower.py`, `src/fenolite/checks/equivalence/levels.py` and `model.py`,
  `src/fenolite/convert/report.py`, `src/fenolite/cli/data/explain.toml`.
- Docs: `docs/equivalence.md`, `docs/cli-contract.md`, `docs/cli-surface.json`,
  `docs/formats/altium/pcb-records.md`, `docs/evidence/sources.md` (S-1900).
- An authored fixture `tests/data/kicad/convert/net_tie_copper.kicad_pcb`.
- An agent's run in Altium 24.5 opens the written tie with no message and finds no short on it (S-1901); evidence stays `INFERRED` until a kit case.
