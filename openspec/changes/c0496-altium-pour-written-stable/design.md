# Design: c0496

## D1 Root cause, part 1: all or nothing

```python
for index, (zone_id, _layer) in enumerate(order):
    ...
    kept = carried.get((vertices, zone.net_id, layer)) if zone is not None else None
    if kept is None:
        return None
```

in `pcbdoc._carried_pour_records`. A document with one polygon more than the carrier gets no carried
regions at all, and `write_pcbdoc_result` computes every polygon.

`_carried_pour_records` becomes per polygon. It returns `{index: (records, kept)}` for the polygons it
matches, and a polygon index is kept when:

- it matches (vertices, net, layer) as today;
- no polygon of its layer is new or changed (unmatched) and has an outline, grown by `max(clearance of
  either)`, that meets its outline;
- no polygon before it on its layer (pour order) is unmatched, since an earlier polygon cuts later ones.

The others go to `pour_reading` with the kept ones as fixed copper, as the pour already treats a
polygon that pours before it. `check_pour` runs on the whole written document. A kept polygon it fails,
whose source did not fail (`source_failed`), is computed in the next round. That is the existing loop, per
polygon.

## D2 Root cause, part 2: the computed pour (task 1.1)

Task 1.1 writes an authored document twice, without and with a remote zone, carrier off
(`--altium-pour computed` path). It diffs the region records of each unrelated polygon. Candidates:

- the record prefix's polygon index, which is expected and is excluded from the comparison;
- vertex order or start vertex depending on a global sort (e.g. of all regions of the layer);
- thermal spokes or via grouping that iterate over all vias of the net rather than those in reach;
- the snap rounding of c0463 (`Integer realization by selective snap rounding`) working on a scene larger
  than the polygon.

Each cause found is fixed so the computation reads only the polygon's inputs (I-rows of `pcb-pour.md`).
`H-A-POUR-LOCAL` states the property, and the test of D3 checks it.

## D3 Tests

- An authored two-layer document with three polygons of three nets, vias and pads. Then the same document
  with a fourth polygon of a fourth net 20 mm from all of them. Through `convert --to altium` (carrier) and
  through a build (computed): the region records of the three polygons are byte-identical apart from the
  index bytes.
- A pour region and a pour track of zero length are counted by `pourrecord` and must be 0.
- The same with the fourth polygon overlapping one of the three: that one may change, and the other two
  must not.

## Hypotheses registered by this change

| id | statement |
|---|---|
| `H-A-POUR-LOCAL` | the poured regions of an Altium polygon depend only on its record, the rules that apply to it, the objects within its outline grown by its largest clearance and the polygons that pour before it on its layer |
