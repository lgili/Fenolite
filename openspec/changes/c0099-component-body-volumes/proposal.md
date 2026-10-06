# Retain and analyse component body volumes

## Why

The legacy body model cannot describe an extrusion through the mounting plane. The current adapter rejects malformed body heights. Mechanical analysis needs signed bounds and
explicit unknown projection while import keeps the source body count.

## What Changes

- Add optional signed bounds and an explicit unknown-projection field to ComponentBody.
- Keep every component-body record passed to the adapter, including unsupported projection,
  model kind, reversed height or malformed height; issue a located finding instead of dropping it.
- Analyse known extrusions across board faces, material, allowed penetrations and obstacles.
- Retain native reader bytes and resource references without copying raw hex into model extensions.

## Capabilities

### New Capabilities

- `component-body-volumes`: signed volumes, conservative envelopes and unknown results.

### Modified Capabilities

- `design-model`: additive ComponentBody fields and validation.
- `altium-import`: component bodies are retained despite unknown projection.

## Non-goals

Native writer changes, parsing embedded model geometry, electrical readiness, inferred assembly
dimensions and qualification. Unassociated native primitives keep their existing import census.

## Evidence level required

INFERRED on authored probes. Public corpus counts and byte identity support retention, not native
Altium acceptance. See S-0303, S-0570 and S-0605 in docs/evidence/sources.md.

## Impact

Implementation will remain on a local branch from origin/dev for coordinator integration. No core
dependency is added. Legacy canonical body output stays identical when new fields use defaults.
