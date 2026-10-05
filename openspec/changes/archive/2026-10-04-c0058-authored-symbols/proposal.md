# Project-authored symbols

## Why
Fenolite designs need to resolve custom component pins without depending on an external KiCad symbol library or invoking KiCad tools.

## What changes
Add a small Python DSL builder for symbols and pins. Symbols are attached explicitly to a design, become `SymbolDef` values, and are used as an overlay when the KiCad build resolves `Part.lib_id`. Write the authored symbols as a project-local KiCad symbol library alongside the board build.

## Capabilities
- A design can author and attach symbols with pin numbers, names, electrical types, positions, rotations and lengths.
- A KiCad build resolves matching custom symbol IDs from the design and emits the symbol library and project table row.
- Invalid or conflicting authored symbol declarations fail before writing.

## Out of scope
Schematic authoring and reading third-party symbol files into the DSL.
