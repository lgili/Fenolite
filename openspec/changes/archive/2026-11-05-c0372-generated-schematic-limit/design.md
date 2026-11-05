# Design notes: c0372

## Found on 2026-11-04: the public heavy document now gets its schematic

CI run 41947475460 on cac/lote-15: before this change the schematic generator refused the circuit of
`altium-third-party-pcbdoc-08` as one page (a `schematic` loss, "the schematic generator refused the
imported circuit"). Task 2.2 paginates a flat generated circuit, so the conversion now writes it ("positions
and wires are regenerated from the circuit", a `schematic` change). `CONVERTED_LOSSES` of
`tests/corpus/test_convert_altium_census.py` drops `schematic: 1` for that row. Row `-03` keeps its
schematic loss.
