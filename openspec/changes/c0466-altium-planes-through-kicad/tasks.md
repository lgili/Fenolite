# Tasks: c0466

## 1. Diagnosis

- [x] 1.1 Census of the planes of the public rows: the chain, the plane nets, the pull-backs and the Split
  Plane polygons (S-2250).
- [x] 1.2 Round trip of rows `-01` and `-02` before the change: the chain, the plane nets and the read-back
  rules (S-2251).

## 2. To KiCad

- [x] 2.1 `map_layers` types each internal plane `power` and names it. Proof:
  `uv run pytest tests/unit/convert/test_altium_planes_c0466.py -n 0 -k kicad`.
- [x] 2.2 `convert/altium_planes.py`: the carrier, written by `to_kicad`. Proof: the same file, `-k carrier`.

## 3. Back to Altium

- [x] 3.1 The writer: plane splits, `(Multiple Nets)`, pull-backs and plane names. Proof:
  `uv run pytest tests/unit/convert/test_altium_planes_c0466.py -n 0 -k writer`.
- [x] 3.2 `to_altium` restores the carried planes and counts the rest lost. Proof: the same file,
  `-k "back or edited"`.
- [x] 3.3 Rows `-01` and `-02` round trip with their planes and their rule census. Proof: the same file,
  `-k row` (corpus rows, skipped without the cache).

## 4. Evidence and docs

- [x] 4.1 Rows in `pcb-copper.md` and `board.md`, S-2250 to S-2252, and the CHANGELOG.
- [ ] 4.2 Kit: Altium opens the round trip of rows `-01` and `-02` with their planes and splits, and Plane
  Connect finds the pads of the planes' nets connected.
