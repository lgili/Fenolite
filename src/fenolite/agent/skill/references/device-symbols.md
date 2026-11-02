---
topic: device-symbols
title: Device symbols from pin tables
summary: Bind device pin tables to package-specific drawings.
---

# Device symbols from pin tables

In a project library, a device record's `symbol` names a `fenolite.pins.v0` record. That record may hold
an explicit drawing, an imported `symbol_file`, or a pin table with optional generator settings.
The example in `docs/symbols.md` shows the table format; `docs/library-records.md` describes the envelope.

With a pin table, the build generates a drawing under the device's own id. It sets `Footprint` to the
device's package id and `ki_fp_filters` to the package name. Two devices sharing a table keep separate
package properties. Stacked numbers, buses, units and per-table layout settings still apply.

```fenolite-cmd
fenolite build design.py --out build --dry-run --json
fenolite library symbol pins/example.toml --out lib/Example.kicad_sym --dry-run --json
```

The first command previews a whole project, including device bindings. The second previews the table's
standalone symbol. Review the plan and confirm its `plan_id` to write the reviewed bytes.

An explicit drawing or imported symbol keeps precedence. Generation changes no authored device record,
provenance stamp or evidence label; an `UNVERIFIED` pin fact still needs review against the datasheet.
Changing a package or pin table changes the build input and requires another preview.

Read next: `parts`, `footprints`, `library-review`.
