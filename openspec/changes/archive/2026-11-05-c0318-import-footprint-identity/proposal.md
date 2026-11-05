## Why

An imported board may contain two physical geometries under one native footprint ID. Vendoring
correctly creates separate local definition files, but emitted parts currently use those local variant
names as their native identity. A shared schematic then appears to have inconsistent footprint text,
and public level-3 comparison sees a footprint-name change on the rebuilt PCB.

## What Changes

- Keep the original footprint identity separate from the internal definition lookup reference.
- Emit a definition override only when the vendored lookup name differs from the native ID.
- Resolve and place the correct physical definition while writing the original native PCB name.
- Preserve ordinary/default bytes and strict value, unit, pin and electrical guards.
- Add authored geometry variants, repeated-sheet and negative fidelity regressions.

## Capabilities

### New Capabilities
- `native-footprint-identity`: distinct native identity and internal geometry lookup for imported parts.

### Modified Capabilities
- None.

## Evidence level required

Mechanical: authored import/build/native readback, strict public comparisons and byte digests. No
oracle or new native-format claim; existing KiCad footprint-name projection facts suffice.

## Impact

Model `Component`, the optional DSL part keyword, model conversion, importer emission, footprint
resolution/placement, generated model schema and documentation. No comparator or drawn guard change.
