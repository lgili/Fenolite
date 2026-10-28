## Why

Since c0085 every polygon is written with its outline only (roadmap, "Open decisions", row 23,
2026-10-06). After each build or conversion the maintainer runs Tools » Polygon Pours » Repour All in
Altium Designer, and a rewrite drops the pour Altium saved.

On 2026-10-26 the maintainer reversed row 23 (row 48): Fenolite computes the pour with Altium's rules and
algorithm, as public sources and kit runs describe them, and writes the regions.

The reason for row 23 still holds: a pour that removes a neck or an island where Altium does not can show
a net connected that Altium's repour leaves open, or the reverse. So no pour is written that cannot be
compared with Altium's repour, and a polygon whose inputs Fenolite cannot evaluate keeps today's form.

## What Changes

- **Decision.** Row 48 replaces row 23; `docs/altium.md` loses "Fenolite never writes poured copper".
- **Facts first.** Each input of a pour is a fact row with its source or an `H-A-POUR-*` hypothesis,
  measured on the public corpus before any engine code.
- **One source of truth.** The writer reads its own document back with Fenolite's reader, pours that
  reading (`backends/altium/pour.py`, `geo` extra) and writes one region per piece in `Regions6` and
  `ShapeBasedRegions6`, with net and polygon index. Only what the document holds enters a pour.
- **Refusal, never a guess.** A polygon with an input the engine cannot evaluate, or whose pour fails
  Fenolite's copper check, keeps its outline, with the later polygons of its layer that depend on it; each
  gets `altium.zone-unpoured` with its reason.
- **`--altium-pour outline|computed`** on `build`, `convert` and `panel`; `computed` is the default
  (the maintainer's decision of 2026-10-26).
- **Comparison with Altium's repour** (`backends/altium/pourcompare.py`): XOR area, islands, connectivity per net, and
  located differences where a neck or an island was removed differently. Kit group K6 gains the authored
  samples `pour` and `pour4`, repoured by the kit script (RunScriptFile) and once by hand; a corpus census
  compares saved pours.
- **Experimental** until one K6 round passes on Altium Designer 26.5.

## Capabilities

### New Capabilities
- `altium-pour`: pour inputs, the pour engine, refusals, the comparison.

### Modified Capabilities
- `altium-pcb-writer`: MODIFIED "Polygon pour records", "Unpoured polygons are a contract".
- `altium-build`: MODIFIED "Copper in an Altium build".
- `altium-verification`: ADDED "Kit group K6 for computed pours", "Pour census of the public corpus".
- `design-conversion`: MODIFIED "Changes of the Altium direction".

## Non-goals

- Hatched and `None` pours, planes and split planes, AdvancedPour's true arcs.
- Automatic relief conductors, per-object relief overrides, polygon cut-outs, shelved polygons, copper
  text in a pour, rule scopes that `read/scope.py` does not parse: each refuses its polygon.
- Repouring an existing document in place; keeping Altium's saved regions in a rewrite; repouring
  copies of public documents in Altium (decided 2026-10-26).
- Filling KiCad zones with this engine (KiCad stays the oracle of its fills, c0015).

## Evidence level required

- Fact rows `INFERRED` (S-0196, S-0287, S-0558, S-0833, S-0834, the corpus census).
- Read-back: Fenolite's reader within 1 unit; KiCad's importer `ORACLE-VERIFIED(kicad-cli)` (10.0.6).
- Public corpus: `CORPUS-VERIFIED` for the polygons that agree; it raises no write kind.
- Altium: `ALTIUM-VERIFIED(kit; AD 26.5; …)` only after a K6 round passes every criterion; until then each
  computed pour is reported as experimental.

## Impact

- New `backends/altium/pour.py`, `connectstyle.py`, `backends/altium/pourcompare.py`, kit samples `pour` and `pour4`;
  the writer, reader, build, convert, kit and docs change (design, "Files and public API").
- `computed` needs `fenolite[geo]`; without it the outline is written with a warning. `outline` gives
  today's files, byte for byte.
- Depends on c0122 and c0130.
