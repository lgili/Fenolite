## Why

Strict conversion preserves schematic poses but loses their fonts. An original CC0
one-resistor control imports and builds with identical field text and equal levels
1–7 and S, yet its 0.25 mm field becomes 1.27 mm and fails level 8. Native KiCad
9.0.2 SVG exports independently show enlarged text in a public conversion. Hidden
power-reference renaming leaves the comparison masks unchanged.

`DrawnField`, `DrawnLabel` and `DrawnPin` have no font carrier; the created-sheet
writer always uses `TEXT_SIZE`. Reusing a board entity or hiding style in an opaque
fragment would not represent this drawing faithfully.

## What Changes

- Add a shared, validated, optional `DrawnFont` value using integer nanometres for
  both size axes and thickness, optional bold/italic flags and a font-face name.
- Append optional fonts to drawn fields, labels and sheet pins; preserve explicit
  label/pin justification and sheet-name/file field poses. Keep references, values
  and footprint selection owned by code.
- Preserve supported native effects through extraction, `schematic.toml`, lowering,
  written-byte readback and level S. Refuse unsupported effects before staging.
- Keep every old default and all 75 existing example build maps byte-identical.
  Retain the old six-part private field-pose payload and add separately versioned
  font data only when requested.
- Test the complete text-bearing drawn surface, including power fields, local,
  global and hierarchical labels, sheet pins and sheet properties. Measure actual
  native output; keep comparison thresholds, junction checks and losses strict.

## Capabilities

Modified: `design-model`, `canonical-serialization`, `drawn-schematic`,
`kicad-schematic`, `board-to-code`, `design-equivalence` and
`altium-schematic-writer`.

## Non-goals

No generic text override, schematic editor, font-file distribution, new runtime
dependency, new CLI result shape or new Altium hypothesis stem. No filename-based
scene matching or correction of source PCB/schematic footprint-text disagreement.
Those independent findings remain visible. No accepted losses, comparator changes,
baseline refresh, GUI-save claim or unexecuted native-version claim.

## Evidence level required

Model, codec, default-byte and refusal controls are unit-tested `INFERRED` behavior.
Native font semantics need authored load/export probes on their actual version;
local 9.0.2 results do not replace required 9.0.9/10.0.6 CI. Existing public-format
facts are S-0001 and S-0367 in `docs/evidence/sources.md`; the existing board font
facts are not evidence of identical schematic serialization. Altium remains
`INFERRED`, with explicit unsupported-style reporting and no native claim.

## Impact

The model and active v0 drawn schema gain real optional fields. The immutable
`695dee0f` model-0 capture remains historical; after implementation and combined
proofs the final model-0 surface must be recaptured before c0218's 1.0 transition.
This checkpoint contains planning and diagnosis only. Implementation follows a
validated proposal/design/spec/tasks packet and the requested maintainer review.
