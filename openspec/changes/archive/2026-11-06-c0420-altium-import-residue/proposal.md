# c0420: Altium import residue (B5, B6, B7, N1 to N4, holes, TAB parameters)

## Why

A conversion of a private Altium board to KiCad, after c0409 and c0411, still left findings that came from
the import and not from the board. Zones whose connect style could not be read (`connect-scope`) left
starved thermals. A Clearance rule was refused for its scope. Zones carried the widest clearance of a
high-voltage class against every item. `items_not_allowed` showed at mounting holes and at the pads of a
part under a keep-out. KiCad reported `shorting_items`, `clearance` and `solder_mask_bridge` round a
net-tie footprint. Gaps within a rounding of the minimum gave `copper.hole-clearance` findings.

The maintainer wants that board to convert without loss. Everything KiCad or the Fenolite model can hold
must arrive. What KiCad cannot represent stays in the model, so a write back to Altium keeps it, and is
declared as a format limit. No change of meaning goes unreported. No board data enters the repository:
every case below is authored for Fenolite from public format facts.

## What

- **B5, named polygons.** A Polygon Connect Style scope `IsNamedPolygon('n')` (or such terms joined by
  `Or`) names the pour object (S-1790) and governs the pours of those names alone. Each zone takes its
  connect style by its name.
  - A pad whose records give it one other style for every zone of its net gets its own connection.
  - A pad whose records differ between zones keeps its setting, with a `pad` change.
  - How the conversion ledger counts the Polygon Connect Style records is c0424's (per-record fates).
- **B7, `Not InAnyNet`.** `InAnyNet` reads as `net *`, so `Not InAnyNet` is `NO_NET` (S-1680) and
  `IsPad And (Not InAnyNet)` maps. The Altium writer gives `NO_NET` back as `Not InAnyNet`.
- **B6, zone clearance.** Measured on KiCad 10.0.6:
  - a matching custom rule decides a fill's gap, above or below the zone's clearance;
  - against a netclass, the larger of the two holds.

  A converted zone therefore carries the smallest clearance of the Altium rules that govern a pair of its
  polygon, up to and with the first rule against any item. The DRU rules carry every wider value. A zone
  whose written clearance differs from the one it was read with gets a `zone` change.
- **N2, N3, keep-out restrictions.** The rule area of a keep-out of the Keep-Out layer forbids only the
  kinds that its record's restrictions value forbids (S-1711). The value is read again from the source
  document by the drawing's locator, as `zone_outlines` reads a polygon, so no extension key is added. A
  region of value 7 no longer forbids pads, so the holes and pads inside it are allowed.
- **N1, net ties, in both paths.**
  - Import: a component of `COMPONENTKIND` 3 or 4 (net tie in or out of the BOM; S-1791, S-0188) gets one
    net-tie group of its pad numbers.
  - KiCad writer: writes `net_tie_pad_groups` after `attr` on a created footprint instead of refusing it.
  - Altium writer: writes a footprint with groups as a component of `COMPONENTKIND` 4. Groups other than
    one group of every pad number are counted `changed`, because Altium marks the whole component.
- **N4, hole clearance tolerance.** `copper.hole-clearance` lowers the limit by the clearance tolerance
  (500 nm with KiCad rules), as `copper.clearance` does and as KiCad's hole clearance test does.
- **Holes keep their meaning.** KiCad holds no hole outside a footprint (c0167), so a conversion still
  writes a board hole as a board-only `Fenolite_Holes` footprint (c0170). Every such hole is now counted
  `changed` (`HOLE_REASON`; a plated one keeps `PLATED_REASON`) instead of being written silently.
- **TAB in a part parameter.** `import --to python` of an Altium project reads the board of its in-memory
  KiCad conversion. There each parameter is one footprint field, so a value with a TAB is kept natively in
  the vendored footprint, as c0363 keeps a KiCad one. The import needs no `--allow-lossy`. A parameter
  without that one field stays the declared loss `property-tab` of c0379. The public `Part.properties`
  contract does not change.

## Not in this change

- The level 7 pairing of footprint graphics, of `Mech.n` against `User.m`, and of board holes written as
  NPTH footprints with board holes (c0421). That pairing also settles the L1 `ref-ambiguous` of the
  holes' empty references.
- B8 and the footprint texts that a created footprint does not write (c0422).
- Polygon queries other than `IsNamedPolygon` (`InNamedPolygon`, `InPolygonClass`) stay `connect-scope`.
- Losses of the measured board outside this list (3D bodies and models, Altium rule kinds without a KiCad
  counterpart, the `opt` limit of a via drill rule, a Clearance rule scoped to the Keep-Out layer): they
  are reported to the coordinator.
- Thermals where a single spoke fits, a mask bridge of a fine-pitch part and a via pair just inside a
  rule on the measured board: they belong to the source.

## Impact

- Altium backend: `connectstyle.py`, `pour.py`, `read/scope.py`, `rulemap.py`, `adapter/board.py`,
  `adapter/copper.py`, `adapter/rules.py`, `lower.py`, `pcbdoc.py`.
- KiCad backend: `pcb.py`.
- Other code: `checks/copper.py`, `convert/altium_to_kicad.py`, `convert/altium_zones.py`,
  `convert/to_kicad.py`, `lens/altium.py`, `importer/emit/design.py`.
- Docs:
  - `docs/formats/altium/{rule-file,pcb-pour,pcb-records}.md`
  - `docs/formats/kicad/{board,copper}.md`
  - `docs/cli-contract.md`, `docs/hypotheses.md`
  - `docs/evidence/sources.md` (S-1790 to S-1792)
