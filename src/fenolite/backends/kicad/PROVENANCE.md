# Provenance of `fenolite.backends.kicad`

Every fact this package relies on comes from a public source listed in `docs/evidence/sources.md`
or from running `kicad-cli` as an external program. No KiCad source code was read or copied. Code is
written from the pages under `docs/formats/kicad/`.

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| lexical grammar (lists, atoms, quoted strings, millimetres) | S-0001, S-0020 | not stated on the page; GPL-3.0-or-later tool run as a subprocess | 2026-10-01 | facts only |
| string escapes and number spelling | S-0020 | GPL-3.0-or-later tool run as a subprocess | 2026-10-01 | oracle |
| printer layout (indentation, `xy` packing) | S-0020, S-0024 | GPL-3.0-or-later tool run as a subprocess; API metadata | 2026-10-01 | facts only |
| legacy quoting of pre-6 files | S-0021 | not stated on the page | 2026-10-01 | facts only |
| `kicad-cli` commands (`pcb export svg`, `pcb export ipcd356`, `pcb upgrade`, `fp upgrade`) | S-0022 | GPL-3.0-or-later or CC-BY-3.0-or-later | 2026-10-01 | oracle |
| demo licences | S-0023, S-0025 | licence notice; per-folder licence files | 2026-10-01 | facts only |
| demo tags and commits | S-0026 | API metadata | 2026-10-01 | facts only |
| third-party boards | S-0027, S-0028 | Apache-2.0 | 2026-10-01 | facts only |
| Docker image (`kicad/kicad`) | S-0029 | GPL-3.0-or-later (OCI label) | 2026-10-01 | oracle |
| rotation direction and bottom-side placement (geometry, c0005) | S-0010, S-0019 | GPL-3.0-or-later or CC-BY-3.0-or-later; CC-BY-SA-4.0 | 2026-10-01 | oracle |
| three-point arcs, their written direction and arcs inside `pts` (geometry, c0005) | S-0001, S-0018 | not stated on the page; CC-BY-SA-4.0 with the library exception | 2026-10-01 | oracle |
