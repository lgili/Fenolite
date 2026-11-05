# Design notes: c0375

## Found on 2026-11-04: repeated zone names of a public demo board are now written

CI run 41947475460 on cac/lote-15: KiCad demo board 18 (`vme-wren.kicad_pcb`) holds six zones whose name
repeats another zone's (`p3v3_sfp` six times, `p12v_vme` twice). Before this change they were the
unexpressed `zone-name 6`; the import now writes each name beside its key, so the row loses that entry.
`docs/evidence/import-coverage.json` and its table in `docs/evidence/import-corpus.md` were measured again
with `tools/measure_import_coverage.py` on 2026-11-04; the historical full-conversion table is unchanged.
