# Tasks: c0420

## 1. Connect styles and scopes

- [x] 1.1 B5: `IsNamedPolygon` scopes in `connectstyle` (`named_polygons`, named sides), zone names through
  `pour` and `altium_zones`, pad connections across every zone of the net (`PAD_DIFFERS`);
  `docs/formats/altium/pcb-pour.md`; S-1790.
- [x] 1.2 B5: the ledger entry of the Polygon Connect Style rules handed to c0424 (per-record fates).
- [x] 1.3 B7: `InAnyNet` in the scope grammar, and the Altium writer gives `NO_NET` back as `Not InAnyNet`;
  `docs/formats/altium/rule-file.md`.

## 2. Clearances

- [x] 2.1 B6: measure KiCad's fill gap (zone, custom rule, netclass) on KiCad 10.0.6; put the smallest
  governing clearance on each zone (`governing_clearance`), with a `zone` change when it differs from the
  clearance the zone was read with; `docs/formats/kicad/board.md`; S-1792; `H-K-ZONE-CLEARANCE`.
- [x] 2.2 N4: `copper.hole-clearance` lowers the limit by the clearance tolerance; KiCad boundary test;
  `docs/cli-contract.md`, `docs/formats/kicad/copper.md`.

## 3. Keep-outs, net ties, holes and parameters

- [x] 3.1 N2, N3: `keepout_restrictions` reads the restrictions of a Keep-Out-layer keep-out from its
  source record, and its rule area forbids those kinds alone; `docs/formats/altium/pcb-records.md`.
- [x] 3.2 N1: `COMPONENTKIND` 3 and 4 give a net-tie group; the KiCad writer writes `net_tie_pad_groups` on a
  created footprint; KiCad DRC test; `pcb-records.md` "Component kind", `board.md`; S-1791;
  `H-A-PCBX-NETTIE`.
- [x] 3.3 N1: the Altium writer writes a net tie as `COMPONENTKIND` 4 and counts other groups changed
  (`net_tie_differs`); the build carries the groups to the placed footprint.
- [x] 3.4 Every board hole written as a generated footprint is counted changed (`HOLE_REASON`).
- [x] 3.5 A TAB value of a converted part parameter is kept natively by the import (c0363's path); a
  parameter without its one field stays `property-tab`.

## 4. Proof

- [x] 4.1 Hand-offs: the level 7 pairing of footprint graphics, mechanical layers and board holes to c0421;
  B8 and the footprint texts to c0422.
- [x] 4.2 Focused and consumer tests, the KiCad tests on 10.0.6 and 9.0.9, `make check-fast`, schema, model
  review and evidence checks; `CHANGELOG.md`.
  Proof (2026-11-06): lote-28 CI run 42229338778 succeeded on abe1de83f (unit on 3.11 to 3.13 and three OSes, kicad-10 shards 0-3, kicad-9, coverage audit, ci-complete); dev fast-forwarded to it.
- [x] 4.3 Full CI on the batch (Master's next lote).
  Proof (2026-11-06): lote-28 CI run 42229338778 succeeded on abe1de83f (unit on 3.11 to 3.13 and three OSes, kicad-10 shards 0-3, kicad-9, coverage audit, ci-complete); dev fast-forwarded to it.
