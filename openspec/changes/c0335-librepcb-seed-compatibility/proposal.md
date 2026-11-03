# Public LibrePCB0.1 seed compatibility

The pinned public Base cannot supply reviewable items through the conservative
seed path: localized names, scalar zero drills and direct pad UUID bindings are
refused; declared prefixes are lost, numeric function names are not identifiers,
and signed cardinal pin angles fail canonical KiCad emission.

Repair those bounded representations. Preserve strict DevicePin.function,
explicitly normalize only numeric internal names with collision refusal, and
canonicalize only exact cardinal angles modulo360. Emit reversible source-bound
maps in warnings and existing provenance notices. Keep visible pin names,
numbers, mappings and geometry exact; unsupported geometry, near-cardinal input,
ambiguous names, nonzero legacy drill and licensing refusals remain visible.
No model fields or CLI arguments change. No evidence promotion, human acceptance
or full Base compatibility is implied. Public CAD remains external to core.
