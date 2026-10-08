## Why

A design that names parts of the built-in catalog (library `Fenolite`) and declares a `Power(...)` interface does not build for KiCad:

```
build.vendor-unsafe-name (error, where: fenolite)
symbol libraries 'Fenolite' and 'fenolite' differ only in letter case
```

The power flag of a generated sheet lies in a library `fenolite` (`symembed.FLAG_LIBRARY`, change c0061), the catalog's symbols lie in `Fenolite`, and two library files whose names differ only in case cannot lie in one `lib/` folder on every file system, so the build refuses them. Without the `Power` interface the design builds and KiCad's ERC then reports `power_pin_not_driven` for every power input fed from a connector. So a catalog part with a `power_in` pin (`Linear_Regulator`, `Comparator`, `Operational_Amplifier`, `Offline_Power_Controller`) fed from a connector cannot pass ERC, and any catalog part beside a `Power` interface with an undriven net stops the build.

**The defect is in the releases 0.2.0 and 0.2.1.** Measured on 2026-10-08 on the tag `v0.2.1` (`fde27c9f`) with a 12-line script (design, Context): exit 5 with the message above. Read in the source of `v0.2.0`: the same two names and the same check. Whether the fix is backported to a 0.2.x patch release is the maintainer's decision; the commit is written so that its code and its core test apply on `v0.2.1` (design, Decision 4).

## What Changes

- **The flag joins a library of the design named like its own.** When a symbol library of the design (a library of a part's symbol, or one the design authors, the catalog's among them) has a name that differs from `fenolite` in letter case only, the power flag is `PWR_FLAG` of that library: `Fenolite:PWR_FLAG` in `lib/Fenolite.kicad_sym` for the catalog. Every other design keeps `fenolite:PWR_FLAG` in `lib/fenolite.kicad_sym`.
- **A design that builds today moves zero bytes.** Only designs that were refused gain output.
- **A taken name is refused.** A design that needs a flag and holds a symbol `PWR_FLAG` in that library gives `build.reserved-library` at the symbol's lib id. No new issue code.
- **The own netlist** treats `PWR_FLAG` of a library named `fenolite` in any letter case as the flag.
- The Altium build writes no flag and does not change.

Size: 0.25 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-schematic`: MODIFIED "Generated sheet content", "Embedded symbols of a generated sheet", "Generated schematic issue codes", "Netlist grammar check".
- `design-dsl`: MODIFIED "Symbols of a built project".

## Non-goals

- Renaming the flag library for every design (`Fenolite` everywhere): nowhere, because it moves the bytes of every built design with a power flag and leaves a file of the old case on case-insensitive file systems (design, Decision 1).
- A power-output pin on a catalog connector, or a "power source" part in the catalog: nowhere in this change; the `Power` interface is the way a design states a supply.
- The patch release itself: the maintainer's decision.
