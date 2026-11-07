## 1. Evidence

- [x] 1.1 `docs/evidence/sources.md`: S-1702, Altium's Object Type Checks page (the note under `IsPolygon`
  that names `InPolygon` for the copper of a pour in a clearance rule). `docs/formats/altium/rule-file.md`:
  the grammar row `InPolygon`, `InPoly` and the "Unmapped forms" note; `pcb-copper.md`: the written scope
  forms; `pcb-records.md`: copper regions and copper graphics with a net, and why no fill is written.
  Proof: `uv run pytest tests/unit/test_legal_docs.py tests/unit/test_format_facts.py tests/unit/test_docs_altium_read.py tests/unit/backends/altium/test_rulemap.py -q`.

## 2. Copper shapes (B12)

- [x] 2.1 `pcbrecords.region_record(..., net=)`; `lower._items` keeps copper graphics on signal layers with
  their net; `pcbdoc.free_records` writes them as regions or tracks and arcs with the copper layer id and
  net index; planes, filled circles, refused shapes and shapes on an unwritten net stay `copper-shape`.
  Proof: `uv run pytest tests/unit/backends/altium/test_copper_shapes.py -q`.
- [x] 2.2 KiCad oracle: KiCad's import of a converted board holds the copper shapes on their layers and
  nets. Proof: `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/altium/test_copper_shapes_oracle.py -q`.

## 3. Rule scopes (B14)

- [x] 3.1 `read.scope`: `InPolygon` and `InPoly` read as `item_kind zone`. Proof:
  `uv run pytest tests/unit/backends/altium/read/test_scope.py -q`.
- [x] 3.2 `rulemap`: write `ref`, `item_kind` (track, via, pad, zone), `or` and `not` with parentheses for
  nested operators, names from the scope; the value refusals are unchanged. Proof:
  `uv run pytest tests/unit/backends/altium/test_rulemap.py -q`.

## 4. Mechanical user layers (B13)

- [x] 4.1 `lower`: a `User.<k>` layer named `Mech.<n>` or `Mechanical <n>` maps to Mechanical n. Proof:
  `uv run pytest tests/unit/backends/altium/test_mech_user_layers.py -q`.

## 5. Imported designs in an Altium build (B15)

- [x] 5.1 `cmd_build`: the Altium build takes `footprint_definition` as the footprint link and reports
  `altium.footprint-definition` where the written name differs from the native one; explain entry and agent
  guide line. Proof: `uv run pytest tests/unit/importer/test_footprint_identity.py tests/unit/cli/test_explain_cmd.py tests/unit/agent/test_pages.py -q`.

## 6. Hand-over

- [x] 6.1 CHANGELOG, `docs/altium.md`; ruff check, ruff format --check, `pyright src`, `openspec validate
  c0412-kicad-altium-write-gaps --strict`, focused tests through `fenolite-heavy`. Proof: those commands. Run 2026-11-05: ruff, format, pyright 0 errors, validate valid; 418 passed, 1 failed
  (`test_ordinary_import_and_rebuild_keep_every_byte[9-…]`, which fails the same on `cac/lote-22` without c0412).
