# Bounded resolver correction

## Hypothesis and proof order

The existing `_local_scalar_aliases` policy joins local scalar nodes with explicit same-sheet global/hierarchical labels. A global power declaration should provide the same local alias in its own sheet. First measure an original Fenolite flat drawing with disconnected wire/pin islands and equal/unequal local and power names. Include a hierarchy with the same local name elsewhere but no same-sheet power declaration. Native `sch export netlist` is an independent subprocess oracle; the code resolver must not prevent construction of the native test input.

Only if native controls establish the rule, join the local name node for the current sheet to the existing global power node when both `_local_scalar_aliases` and the existing `global_net` test hold. Do not alter global-net detection, hidden pin handling, bus port aliases, generic/default policy or native text. No model/DSL/schema/dependency changes are needed.

## Validation

Prove the original authored disagreement before the fix and complete pin equality afterward, with unequal-name, no-power, other-sheet and generic-policy negatives. Retest existing native bus/scalar/repeated-owner controls. Rerun the actual owner037 rows with original input hashes and complete original/own/lowered/native partitions. Keep any remaining naming differences/warnings separate. Record the actual tool/version and evidence scope; exact required 9/10 CI remains a root-owned gate.

No original public CAD, third-party parser code or grammar enters the repository. Only authored controls and value-free observations may be committed. Document a new native observation only after proof, with a registered public-tool source and conservative evidence label.
