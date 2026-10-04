# Proposal: DSL pin to pad maps and slotted drills

## Why
The DSL currently requires a symbol pin number to equal its footprint pad number, and authored through-hole pads accept only round drills. This prevents describing common packages whose physical pad numbering differs from the schematic and footprints with oblong plated holes.

## What Changes
- Add per-component pin-to-pad mapping with identity as the default.
- Model and author slot drills, serialize supported horizontal and vertical forms to KiCad, and refuse unsupported target lowering.
- Keep nets and no-connects keyed by schematic pin number.

## Non-goals
- Importing, copying, or deriving any private project footprint or mapping.
- Changing automatic identity mapping for existing designs.
- Supporting arbitrary per-layer pad geometry or drill offsets.
- Extending Altium PCB slot serialization without public format evidence.

## Evidence level required
The API, validation, model round-trip, and KiCad serialization must be covered by deterministic unit tests. KiCad format output remains `INFERRED` unless independently checked by the existing KiCad oracle workflow; Altium must continue to refuse unsupported slot geometry explicitly.
