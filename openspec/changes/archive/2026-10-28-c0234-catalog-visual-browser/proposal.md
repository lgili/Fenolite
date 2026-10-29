## Why

The installed catalog can be searched and inspected as JSON, but its visual review sheets require repository-only scripts. Users need to inspect a symbol or land pattern before selecting its exact library ID, using the same geometry and inspection tools as the existing viewer.

## What Changes

- Add `fenolite catalog view --out FILE`, with the existing kind and text filters, to plan a deterministic standalone HTML catalog browser.
- Reuse the library viewer and its board/schematic renderers; show exact IDs, catalog metadata, pin roles and pad details without intermediate CAD files, network access or external tools.
- Keep list/show behavior unchanged and refuse invalid argument combinations or empty selections without writing.
- Teach the command and its evidence limits in the catalog guide, CLI contract and agent guide.

## Capabilities

### Modified Capabilities
- `fenolite-component-catalog`: visual inspection of installed definitions through the normal write protocol.

## Impact

Catalog CLI, in-memory scene composition and small reusable library-scene helpers. No catalog geometry, evidence upgrades, runtime dependency, file-format changes or publication is included. Complete validation stays in CI.
