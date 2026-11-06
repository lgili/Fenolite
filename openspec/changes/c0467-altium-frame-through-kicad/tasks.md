# Tasks: c0467

## 1. Diagnosis

- [x] 1.1 Census of the origin and the outline's low corner of the public rows `-01` to `-07` (S-2260).
- [x] 1.2 The round trip and flow A of row `-04` before the change: KiCad keeps the absolute coordinates,
  the way back writes origin and corner at 1000 mil (S-2261; S-2191).

## 2. The frame through KiCad

- [x] 2.1 `convert/altium_frame.py`: the carrier, written by `to_kicad`. Proof:
  `uv run pytest tests/unit/convert/test_altium_frame_c0467.py -n 0 -k carrier`.
- [x] 2.2 `lower.write_design(frame_origin=…)` writes the document frame and the origin; `to_altium`
  restores the carried origin, moved with the edge's corner. Proof: the same file, `-k "back or moved"`.
- [x] 2.3 The guard: a board at a negative coordinate is anchored and reported under `outline`. Proof: the
  same file, `-k negative`.
- [x] 2.4 Rows `-01` to `-07` round trip with their origin and outline, and flow A on row `-04` keeps the
  origin, the outline and the component positions (S-2262). Proof: the same file, `-k "row or flow"`
  (corpus rows, skipped without the cache).

## 3. Evidence and docs

- [x] 3.1 Rows in `pcb-document.md` and `import.md`, the `fenolite.altium-frame.v0` format in
  `tools/schema_formats.py`, S-2260 to S-2262, and the CHANGELOG.

## 4. Kit

- [ ] 4.1 Altium opens the round trip of row `-04`: the outline box relative to the origin equals the
  source's (S-2263).
