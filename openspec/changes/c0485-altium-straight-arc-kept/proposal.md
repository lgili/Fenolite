# c0485: a straight Altium arc is kept

## Why

An Altium arc record whose three points lie on one line (a very short arc) has no centre and radius in
the model. The Altium writer writes it as the straight track it draws (c0435, `convert.changed` "an arc
whose three points lie on one line is written as the straight track it draws"), and `import --to python`
holds it as a track (`import.arc-as-track`). On the maintainer's board (private; codes and counts only) the
source holds 1 arc and 1508 tracks; F2 (Altium → KiCad → Altium) and F5 (`import --to python`, then
`build --target altium`, which since c0480 goes through the same conversion writer) write 0 arcs and 1509
tracks.

## What Changes

- A conversion to KiCad carries, in the board property `Fenolite.Altium.StraightArcs`, each such arc's
  pair `arc` as the import keeps it (centre, radius and angles as read), with its layer, width and net name.
- The Altium writer of a conversion writes that arc record, not a track, for a track or straight arc of the
  same layer, width and net whose ends are the record's in the written document's frame.
- The record is found by content, not by uuid: a script's build gives its items other uuids.
- An arc written back this way is not counted as changed.
- The KiCad side is unchanged.

## Impact

- `src/fenolite/convert/straightarcs.py` (new), `convert/to_kicad.py`, `convert/to_altium.py`,
  `backends/altium/lower.py`.
- `docs/formats/altium/pcb-copper.md`.
- No change for a document without such an arc, or for an edited track.
