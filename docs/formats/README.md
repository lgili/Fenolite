# docs/formats

One page per file-format topic, per backend (`kicad/`, `altium/`, …). Every fact on a page cites a
public source listed in `../evidence/sources.md` and carries an evidence label
(`KICAD-VERIFIED`, `ORACLE-VERIFIED(<tool>)`, `CORPUS-VERIFIED`, `INFERRED`, `UNKNOWN`).
Code is written from these pages, never from third-party source code (see `LEGAL.md`).

## Altium import pages (c0043)

- `altium/connectivity.md`: the rules by which the import derives nets from schematic sheets.
- `altium/import.md`: the mapping of PCB records into the model, the id table and the extension-bag keys.
- `altium/pcb-bodies.md`: the component-body record and its typed keys.
