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
- [x] 4.2 Kit: Altium opens the round trip of rows `-01` and `-02` with their planes and splits, and Plane
  Connect finds the pads of the planes' nets connected.
  Deferred to v0.8 (coordinator, 2026-11-07): not run before the cut of 0.7.0; the code ships.

  Native follow-up, 2026-11-10: Altium 24.5.2.23 opened the originals and direct returns of both public
  rows. The source and return each reported five connected pads on the first plane. The second plane
  reported 2 to 1 on row `-01` (one 5 V pad lost) and 2 to 0 on row `-02` (two 3.3 V pads lost), using
  the native pad connection property before running a new DRC. The layer and split geometry record
  comparisons pass; native connection parity and Plane Connect DRC remain open. The four input
  hashes were unchanged. Native TSV SHA-256:
  `0636687e4217ef1a50f9e03073df28e6b80059be2a299205236cbae26cb82244`.

- [x] 4.3 Preserve the split boundaries that the native connection control isolated, keeping older
  carriers readable. Proof: `uv run pytest tests/unit/convert/test_altium_planes_c0466.py -n 0`,
  plus native pad connection comparison on rows `-01` and `-02`.
  The corrected direct returns preserve 74 and 43 boundary tracks. Altium 24.5.2.23 opened both
  sources and both returns and reported the same pad identities, five on plane 1 and two on plane 2
  in each pair, before running a new DRC. The input hashes were unchanged. Native TSV SHA-256:
  `b37413dafbdf20b1783dd27d3500e59ba652f44d23daf4e9f29596ec7ec02035`.
  Fresh native batch DRC (S-2293) ran on the original and corrected return of both public rows.
  The return used `--altium-pour outline`.
  All reported Power Plane Connect rules had zero violations, and no unrouted finding named the
  recovered pads. This is the plane-specific proof for task 4.2. The overall reports differ:
  row `-01` has 228 versus 256 unrouted findings and the return reached the 500-violation cap
  after reporting the plane rule. Row `-02` has 0 versus 31 unrouted findings. The same four
  inputs have 90 versus 50 polygon-linked region records for row `-01` and 91 versus 79 for
  row `-02`. These counts do not attribute individual findings or establish full DRC equivalence.

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
