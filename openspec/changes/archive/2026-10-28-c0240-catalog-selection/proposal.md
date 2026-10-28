## Why

The installed catalog is visually inspectable, but choosing a symbol and footprint still requires switching libraries, remembering geometry and manually assembling a pin map. Generic roles must not be mistaken for a verified device pinout.

## What Changes

- Add a catalog selection workspace to the existing standalone browser with symbol/footprint previews together, text and geometric filters, exact dimensions and original evidence/source IDs.
- Provide an explicit pin-to-pad mapping editor, validation of complete unambiguous electrical pad coverage, and a Python Part snippet after the user confirms their datasheet review.
- Reuse the existing scene renderer in isolated same-page preview frames; keep the standalone browser offline and deterministic. No new component definitions, automatic device-compatibility claims or layout reuse.

## Impact

Viewer-owned resolved model metadata, packaged page, catalog documentation and regression/browser tests. Existing catalog CLI arguments and writing protocol stay the entry point.
