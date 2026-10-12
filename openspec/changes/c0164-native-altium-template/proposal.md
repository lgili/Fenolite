## Why

Converting an Altium sheet template to a neutral drawing sheet and drawing it again changes fonts,
page settings and special strings, and drops embedded images. An Altium build needs an opt-in native
template path that does not use the neutral drawing-sheet model.

## What Changes

- Add `build --altium-template FILE.SchDot` for binary Altium builds.
- Copy the supplied template unchanged and apply its native records, fonts, page settings and storage
  to every generated schematic. Preserve template ownership and rebase generated owners and fonts.
- Track the template as a reviewed-plan input; refuse conflicting drawing sheets and incompatible
  formats rather than silently converting.
- Report the template digest and applied sheets. Native application remains INFERRED until checked
  in Altium; no private template or project data enters the repository.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-build`: native sheet template option and atomic writes.

## Impact

Altium schematic composition, build command, focused tests, agent guide and template documentation.
Existing builds without the option keep their bytes. No merge or release is part of this change.
