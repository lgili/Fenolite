# Resolve same-sheet local labels against global power names

## Why

The read-only native 10.0.6 corpus owner037 preserves all 647 pins and its lowered-native partition, but Fenolite splits one native net into two groups. Original and lowered native exports agree exactly (155 groups); the resolver has 156. The source contains a local label and a global power name of the same spelling on disconnected wire islands within one sheet. The KiCad policy already aliases local labels to same-sheet global/hierarchical labels; power declarations do not currently take that path.

Independently authored 10.0.6 controls established this rule before production changes: the positive retained all 34 pins but had 34 own groups versus 33 native groups. No public source body, component name or geometry is proposed as a fixture.

## What changes

After native proof, make the KiCad-only same-sheet scalar alias policy include an actually global power declaration. Keep other-sheet locals isolated without a local declaration, unequal names separate, and generic/Altium policy unchanged. Preserve every pin, drawn/model field, raw input, warning and source/lowered native comparison. No loss acceptance or count baseline changes.
