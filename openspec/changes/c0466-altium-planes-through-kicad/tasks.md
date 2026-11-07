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

## 5. Signal layer names (S-2254 to S-2256)

- [x] 5.1 `copper_rows` gives a copper row that a signal layer reaches its Altium name as KiCad user name
  when the writer would write another (`written_name`); the writer names each signal layer after its
  row's user name (`PcbDocSpec.copper_names`, formerly `plane_names`), leaving out a name a record cannot
  hold, one of another Altium layer and one two layers take. The round trip of row `-04` wrote
  `Internal Layer 1/2` as `Mid-Layer 1/2` (S-2191). Proof:
  `uv run pytest tests/unit/convert/test_altium_planes_c0466.py -n 0 -k "copper_names or user_name"`.
- [x] 5.2 Evidence: census of the copper names of the public rows (S-2254), their round trips (S-2255) and
  KiCad 10.0.6 on the named signal rows (S-2256); rows in `pcb-copper.md` and `board.md`; CHANGELOG.
- [x] 5.3 Inner signal layer ids (VM at bbe4c452b: row `-07`'s Mid-Layer 2 and 4, ids 3 and 5, came back
  as 2 and 3). `altium_planes` carries the ids by KiCad row (`signals`) when one is not its position's,
  restores them as the layers' `layer_id`, and `pcbrecords.copper_stack` keeps a source's rising ids; a
  board read from Altium keeps them on a direct write too. Proof:
  `uv run pytest tests/unit/convert/test_altium_planes_c0466.py -n 0 -k "keep_their_ids or copper_names"`.
- [x] 5.4 Flow A planes (VM at 60687e26d: row `-01`'s planes written as Mid-Layers). The build types the rows
  of the script's carried planes `power` (`boardcarrier.plane_rows`), and the carrier holds the copper
  rows' user names (`names`), which the way back gives a row that lost its own. Rows `-01` and `-07` come
  back from flow A with the source's chain, names, plane nets and splits. Proof:
  `uv run pytest tests/unit/convert/test_altium_planes_c0466.py -n 0 -k flow_a`.
