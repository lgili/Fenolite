## Why

Native KiCad 9.0.2 exports of two fetched public schematics agree with their PCB
pin partitions, while the drawn resolver splits those same pins and reports
unknown bus members. Complete pin coverage rules out a missing-symbol shortcut.
The resolver needs a bounded correction backed by authored native controls.

## What Changes

Audit the bus member, label-scope and hierarchical joins responsible for the
measured differences. Repair only reproduced semantics; preserve raw label text,
drawn geometry, strict refusals, generic/Altium behavior and comparison rules.
Add entirely authored bus controls and record actual native version/proof scope.

## Capabilities

- Modified: `drawn-schematic`.

## Impact

No model field, schema/package/CLI version, runtime dependency, accepted loss or
ratchet change is planned. Public CAD stays in its fetched cache, outside the
repository. Native KiCad runs only as a subprocess; no vendor parser is read or
copied. Final model0 freeze work remains independently prioritised.
