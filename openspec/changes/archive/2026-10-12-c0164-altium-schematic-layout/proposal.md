## Why

Altium schematic presentation edits cannot currently be synchronised into the source tree. A rebuild refuses edited outputs, or replaces them when layout is discarded. Users need a reproducible way to retain the schematic they organised in Altium.

## What Changes

- Extend `sync --to-source` with `--target altium` to capture all generated schematic documents after checking their identities, symbols and connectivity against the last generated baseline.
- Store complete edited documents in `altium-schematic-layout.json` beside the design script, retaining native presentation and opaque content without reconstructing it.
- Keep generated baselines under the output's `.fenolite/` directory and replay saved sheets during Altium builds. Refuse changed source sheets; generate new sheets normally. Do not silently discard saved layout, even with `--discard-layout`.
- Document the workflow and its conservative conflict handling; test it using Fenolite-authored data only.

## Capabilities

### New Capabilities
- `altium-schematic-layout`: synchronising and replaying native schematic presentation.

### Modified Capabilities
None.

## Impact

The KiCad sync path stays unchanged. Altium builds gain generated baseline files, and only builds with a saved layout have replay or conflict handling. Evidence remains INFERRED: synthetic readback does not establish native Altium acceptance.
