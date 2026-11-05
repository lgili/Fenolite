# Keep a pin in one net when the PCB disagrees with the sheets

## Why

When a PCB document holds a net that no sheet holds, the Altium project adapter
(`backends/altium/adapter/project.py:215`) adds that net to the circuit with every pad it covers, even
for pins that a sheet net already holds. The pin is then a member of two nets; the KiCad direction keeps
the last one and declares a `pin-net` loss (`convert/altium_to_kicad.py:607`). The cause in the input is
a schematic and a PCB out of sync, which the read should report instead of encoding a contradiction.

## What Changes

- A PCB-only net does not take pins that a sheet net holds; the circuit keeps the sheet's net and the
  board keeps the pad's own net.
- A new warning names each pin whose PCB net differs from its sheet net (the disagreement `parity`
  would report), with both names.
- The `pin-net` loss of the conversion no longer arises from this case.

## Impact

`backends/altium/adapter/project.py`, issue codes and explain entries, docs, authored tests.
