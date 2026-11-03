# Preserve native-only custom-rule programs without silent projection loss

## Why

The public author OpenAir project has17 rule items, but the current typed
reader/emitter represents only one. Import silently loses the remaining native
program. L6 already reports custom DRU rules unjudged; equal supported levels
alone do not prove that the original program survived.

## What changes

For native rule items left opaque by the existing reader, preserve the entire
original DRU and verify the bounded explicit selector attributes against the
first output. Bind the complete actual lowered model and final emitted PCB/pro
bytes so subsequent edits/unknown contexts refuse before staging. A two-build
private bootstrap and a closed internal receipt add no public API or canonical
field. Fully modelled programs retain their old editable DSL path and bytes.
No cache-equality, DRC-clean, global rule-judgment or publication claim is added.
