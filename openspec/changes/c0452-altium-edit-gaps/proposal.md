# c0452: altium-edit-gaps

## Why

An edit session run on the maintainer's own board (S-2110: a generic report of what failed, no layout, value
or name taken from it) found five gaps in the Altium in-place edit session of c0241:

1. A move of a free region raises `ValueError` inside `_twins`: the region's record is replaced before its
   twin in `ShapeBasedRegions6` is looked up by the old bytes. A deletion works.
2. There is no arc item: an arc can be neither moved, deleted nor created.
3. A polygon move is refused, and a polygon cannot be created or given another outline.
4. A fill or a region cannot be created.
5. A track is named by its ends, net and layer, not its width, and its ends must lie within 2 units
   (5 nm) of the stated points: two coincident tracks of different widths cannot be deleted one at a time,
   and a track named from coordinates rounded to the micrometre, as `fenolite inspect` shows them, is not
   found when it lies more than 2 units from them (twins less than 0.002 mm apart, for one).

1 and 5 are bugs; 2 to 4 are missing operations.

## What changes

- The twins of a region are found before its record changes (1).
- An item is the nearest record within 0.002 mm of what it states; a second record as near is a second
  match. `Track` and the new `Arc` take an optional `width`; a region's twin is the nearest record of
  `ShapeBasedRegions6` whose box lies within 0.002 mm (5).
- New items `Arc` and `Fill`, moved and deleted like a track (2, 4).
- `move` takes a polygon: its outline keys and its poured primitives move together (3).
- New operation `set_outline` gives a polygon a new outline of straight edges and removes its pour (3).
- New operation `create`: `add_arc`, `add_fill`, `add_region` and `add_polygon`, each cloned from a record of
  its kind that the document holds (2, 3, 4).
- Hypothesis rows `H-A-EDIT-SHAPE` and `H-A-EDIT-CREATE`; gates `create` and `set_outline`, off like every
  other; phase B of Part J gains the documents `shapes`, `create` and `set_outline`.

## Not in this change

- A polygon outline with arcs given by `set_outline` or `add_polygon` (a move keeps arcs).
- A record of a kind the document does not hold: still `altium.edit.no-template`.
- A repour: a polygon whose outline changed, or a new one, is left without its pour, as a build with
  `--altium-pour outline` writes it, and Altium Designer pours it on its own command.
