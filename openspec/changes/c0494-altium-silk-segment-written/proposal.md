# c0494: an Altium build writes no overlay segment the source lacks

Found on: reviewing a private maintainer board on 2026-11-11 (codes only; nothing from the board is in
this change).

## Why

After a build of an Altium document read by Fenolite and written back (Altium → Fenolite → Altium, c0480),
one footprint on the bottom side holds a bottom-overlay segment that the source does not have. It is an
extra track at one end of the footprint's outline. Altium's DRC then reports it against a nearby text. The
written document is no longer the source's design.

The cause is not known yet. A footprint graphic goes through `adapter/copper.py` (one `line` per track, one
`arc` per arc, in the footprint frame, mirrored on the bottom), then `lower.py` (`_library_graphic`, which
mirrors a bottom graphic back to the top and swaps its layer, and `kept_arc`), then `pcblib._graphic_records`
(a `rect` becomes four tracks, an `arc` is rebuilt from three points). Each step could add a stroke:

- **H1:** a bottom arc whose kept record is not found is rebuilt from three points in the mirrored frame. It
  is written with the other sweep, so it draws the rest of the circle or a stub at the outline's end.
- **H2:** a closed outline that the import or a KiCad trip turned into a `rect` or `polygon` is written
  with its closing edge, which the source never drew.
- **H3:** an item that Fenolite derives or carries (a clipped silkscreen piece, a KiCad fabrication or
  courtyard drawing) is mapped onto the bottom overlay.

## What Changes

- Task 1.1 reproduces the defect on authored data: a footprint with an overlay outline of tracks and an arc,
  placed on both sides at several angles, built through Fenolite. It compares the overlay tracks and arcs per
  footprint, source against written, and decides between H1, H2 and H3.
- The fix goes where the extra stroke is made, and the build then writes per footprint the overlay
  primitives the source holds: the same count, each within one file unit of the source's ends.
- A test keeps that comparison for every footprint of the authored document and of the public rows that
  the build already round-trips.

## Impact

- One of `src/fenolite/backends/altium/adapter/copper.py`, `src/fenolite/backends/altium/lower.py`
  (`_library_graphic`, `kept_arc`), `src/fenolite/backends/altium/pcblib.py` (`_graphic_records`), as task
  1.1 decides.
- No change to a footprint whose overlay already round-trips.
