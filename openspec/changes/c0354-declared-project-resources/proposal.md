# Preserve declared native project worksheet resources

The Interf public replay has a PCB-only worksheet reference. The project carrier
correctly refuses an unresolved resource; emitting design.sheet instead would
also change the schematic's independent empty frame scope. Preserve the actual
checked worksheet as a transitive declared input and planned output, with exact
bytes and native pointer scopes. No canonical field or public DSL argument is added.
