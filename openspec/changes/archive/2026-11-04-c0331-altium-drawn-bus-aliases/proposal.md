## Why

Actual Altium Designer 22.2.1 compilation rejects the authored full drawn
fixture's `{BUSA}` label as a wire label placed on a bus. Native pin partitions
alone did not reveal this invalid identifier. The alias means exactly B0 and B1.

## What Changes

Lower bus-only group/alias identifiers with exactly representable sequential
members to native vector names, including matching ports and sheet entries.
Report every changed identifier using the existing informational loss code.
Refuse groups that need an unimplemented signal harness, with their source
locator, before planning bytes. Keep literal scalar labels and ordinary vector
bytes unchanged. Preserve the independent native compiler findings and save
observations without declaring the full native acceptance gate passed.

## Impact

Altium drawn writer, focused authored controls, registered format knowledge and
source-bound native evidence. No model, CLI, runtime dependency or gate change.
