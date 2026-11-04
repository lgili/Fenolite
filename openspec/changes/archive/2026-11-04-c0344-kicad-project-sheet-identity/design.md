# Design
After root and child schematics have been emitted, derive the actual root UUID
and sheet reference UUID/name pairs from their native bytes. Rewrite only
schematic.top_level_sheets and the sheets identity index in the project JSON.
For this single-root generated project, these managed caches describe that root
and its emitted hierarchy; do not copy empty-template identifiers. All other
JSON keys remain untouched. Do nothing if the build does not emit a schematic.

An authored failing regression first asserts project root UUID/filename equality
with the emitted root, every child instance path starts with that root UUID, and
repeated contexts retain distinct references. Flat/hierarchical target9/10 and
rebuild controls cover the binder; skip/no-emission must preserve unrelated caches.
The source model and canonical JSON schemas are unchanged.

Preserve the original v1 failure artifact. Build a fresh pipeline-generated v4
with the runtime fix and explicitly bidirectional GND labels, prove strict all
levels and native pre-GUI partition, then root performs a fresh real GUI save.
Only after post-GUI partition/strict proof may the five allowed fixture files
be captured; local settings/history/locks never enter core.

## Accumulated fast follow-up

Coordinator review authorizes refreshing derived examples and independent digest
ledgers only for measured identity-cache effects. The authored two-sheet source
was deliberately refreshed previously; regenerate its published Python example
with the existing authored helper, review exact provenance/source-hash changes,
and retain physical/electrical content. Sync minimal must change only its project
identity cache. Schematic skip still leaves the template untouched; tests compare
all other project JSON and verify emitted caches against actual schematic UUIDs.
