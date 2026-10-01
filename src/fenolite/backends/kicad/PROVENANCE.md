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
| format version constants (c0007) | S-0030, S-0031, S-0032, S-0010, S-0038 | GPL-3.0-or-later (facts only); GPL-3.0-or-later or CC-BY-3.0-or-later | 2026-10-01 | facts only |
| token names per tag (c0007) | S-0033, S-0034, S-0036 | GPL-3.0-or-later (single names only, never converted into data) | 2026-10-01 | facts only |
| worksheet vocabulary (c0007) | S-0035, S-0036 | not stated on the page; GPL-3.0-or-later (single names only) | 2026-10-01 | facts only |
| board documentation (c0007) | S-0001, S-0021 | not stated on the page | 2026-10-01 | facts only |
| custom rules syntax (c0007) | S-0010, S-0038 | GPL-3.0-or-later or CC-BY-3.0-or-later | 2026-10-01 | facts only |
| token placement (c0007) | S-0039 | GPL-3.0-or-later (KiCad-written files, facts only) | 2026-10-01 | facts only |
| CLI commands per major (c0007) | S-0022, S-0037 | GPL-3.0-or-later or CC-BY-3.0-or-later | 2026-10-01 | oracle |
| load behaviour of `kicad-cli` 9.0.9 and 10.0.6 (c0007) | S-0020, S-0029 | GPL-3.0-or-later tool and image, run as subprocesses | 2026-10-01 | oracle |
| footprint grammar (c0008) | S-0001, S-0040, S-0018, S-0042 | not stated on the page; CC-BY-SA-4.0 with the library exception (facts only) | 2026-10-01 | facts only |
| symbol grammar and the `~` empty-text rule (c0008) | S-0001, S-0041, S-0043, S-0031 | not stated on the page; CC-BY-SA-4.0 with the library exception; GPL-3.0-or-later (facts only) | 2026-10-01 | facts only |
| symbol folders and packing (c0008) | S-0043, S-0044 | CC-BY-SA-4.0 with the library exception (facts only) | 2026-10-01 | facts only |
| library tables and precedence (c0008) | S-0046, S-0047 | GPL-3.0-or-later or CC-BY-3.0-or-later; GPL-3.0-or-later (keyword names only) | 2026-10-01 | facts only |
| path variables and configuration folders (c0008) | S-0045, S-0049 | GPL-3.0-or-later or CC-BY-3.0-or-later | 2026-10-01 | facts only |
| library version constants (c0008, cited from c0007) | S-0030, S-0031 | GPL-3.0-or-later (facts only) | 2026-10-01 | facts only |
| official library licence (c0008) | S-0048 | CC-BY-SA-4.0 (licence text) | 2026-10-01 | facts only |
| library load and re-save behaviour of `kicad-cli` 9.0.9 and 10.0.6 (c0008) | S-0020, S-0029 | GPL-3.0-or-later tool and image, run as subprocesses | 2026-10-01 | oracle |
| board file structure and common syntax (c0009) | S-0001, S-0021 | not stated on the page | 2026-10-01 | facts only |
| board layer numbering, net reference forms and the zone island flag per format version (c0009) | S-0030, S-0033 | GPL-3.0-or-later (names and dated facts only, nothing copied) | 2026-10-01 | facts only |
| placement of tokens in KiCad-written boards (c0009) | S-0039 | GPL-3.0-or-later (KiCad-written files, facts only) | 2026-10-01 | facts only |
| footprint attributes, copper layer types and user names, rule areas (c0009) | S-0010, S-0038 | GPL-3.0-or-later or CC-BY-3.0-or-later | 2026-10-01 | facts only |
| board features introduced by 9.0 (c0009) | S-0050 | CC-BY-3.0-or-later or GPL-3.0-or-later (site notice) | 2026-10-01 | facts only |
| `pcb export pos`, `pcb export ipcd356` and `pcb upgrade --force` of `kicad-cli` 9.0.9 and 10.0.6 (c0009) | S-0019, S-0020, S-0022, S-0037 | GPL-3.0-or-later tool run as a subprocess; GPL-3.0-or-later or CC-BY-3.0-or-later; CC-BY-SA-4.0 | 2026-10-01 | oracle |
