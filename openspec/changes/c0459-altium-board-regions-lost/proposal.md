# c0459: the source's board regions and custom mask shapes are not carried through KiCad

## Why

Change c0450 copies the `BoardRegions` storage of an Altium document into the KiCad board and writes it
back byte for byte. Each public row holds one record there, `Layer Stack Region 1`
(`OBJECTKIND=BoardRegion`), with its vertices in the source's frame and the id of the source's layer stack
(`LAYERSTACKID`; S-2181). The round trip moves the origin (row `-04` by about 11 700 mil, row `-08` by about
5 200 mil) and writes a layer stack of its own, so the copied region names a stack the document lacks and
lies away from the board. In Altium Designer 24.5 the round trips of rows `-04` and `-08` then report a
Board Outline Clearance collision on almost every object inside the board (310 and 13 552), and Repour All
leaves every polygon empty (9 of 9, 33 of 33). The round trip of row `-04` before c0450 poured and held 4
such collisions (S-2180).

## What

- `BoardRegions` leaves the storages a conversion carries. One that holds data is counted lost under
  `altium-storage` as frame-bound; Altium makes the board's region again from its outline, as it did before
  c0450.
- `CustomMaskShapes` leaves them too, as the conservative choice. No public row holds data in it (S-2181),
  so nothing shows whether it holds coordinates in the source's frame. One that holds data is counted lost
  with its own reason: what it holds is not known.
- A KiCad board converted before this change may still hold `Fenolite.Altium.BoardRegions` or
  `Fenolite.Altium.CustomMaskShapes`: the conversion back ignores both.

## Impact

- Spec: `design-conversion` (frame-bound storages are counted lost); c0450's storage list loses
  `BoardRegions`.
- Code: `convert/altium_storages.py`, `convert/to_kicad.py`.
- Docs: `pcb-records.md`, `docs/hypotheses.md` (`H-A-CONV-STORAGE`), `docs/evidence/sources.md` (S-2180,
  S-2181), CHANGELOG.
