## ADDED Requirements

### Requirement: Catalog-only design passes check
A design that names only catalog lib ids SHALL build into a project that `fenolite check` accepts, on a machine that has no KiCad library, and the suites SHALL prove it.
- `tests/_catalog_design.py::catalog_blink()` MUST return a `fenolite.dsl.Design` of a two-pin header (`Fenolite:Connector_2`, `Fenolite:Header_1x2_P2.5`), a resistor (`Fenolite:Resistor`, `Fenolite:Chip_0603`) and a LED (`Fenolite:LED`, `Fenolite:Chip_0805`), with three nets, every part placed, board minimums and one scripted track per net. The design is authored for Fenolite.
- **Hermetic.** `tests/unit/cli/test_catalog_only.py` MUST build it for targets 9 and 10 with no library table and with `subprocess.run` and `subprocess.Popen` patched to raise. On each project it MUST run `fenolite check --stages model.validate,copper.clearance` (both stages `ok`), and MUST compare the model with the re-read board through `checks.assignment_compare.compare(model_netlist(model), board_netlist(board)[0])`: no difference, six common elements, and the references of the board are `D1`, `J1` and `R1`.
- **Oracle.** `tests/kicad/build/test_catalog_only.py` MUST run the same projects through the whole `fenolite check` on the running `kicad-cli`: exit 0, no unconnected item, no `netlist.*` issue, and no design-rule item of type `lib_footprint_issues` or `lib_footprint_mismatch`. A target-10 project is skipped on 9.0.x, as in the acceptance suite.
- **Second backend.** `fenolite build --target altium` of the same design MUST plan the same bytes for every Altium file, and report the same issues, with and without the property step of `mod.prepare_authored_definition`: the Altium documents name each component from `Component.ref` and `Component.value` and MUST NOT change with this requirement. The hermetic test MUST prove it.
- The result of the oracle test settles `H-K-FP-FIELDS` in `docs/hypotheses.md`.

#### Scenario: Nets of the script and of the board agree
- **WHEN** `uv run pytest tests/unit/cli/test_catalog_only.py -k nets` runs
- **THEN** both targets build with exit 0 and every lib id reported as `builtin`, the two check stages are `ok`, and the comparison of the model with the board gives no difference over six common elements

#### Scenario: KiCad accepts the project
- **WHEN** `uv run pytest tests/kicad/build/test_catalog_only.py -rA` runs on `kicad-cli` 10.0.6 and on 9.0.9
- **THEN** `fenolite check` exits 0 on each project the running tool can read, with no unconnected item, no `netlist.assignment-differs`, and no `lib_footprint_issues` or `lib_footprint_mismatch`

#### Scenario: A regression is caught
- **GIVEN** `embed.default_fields` and the property step of `mod.prepare_authored_definition` patched in the test so that prepared definitions get no field
- **WHEN** the hermetic comparison runs on a project built that way
- **THEN** it gives at least one difference, and the board's references are all empty

#### Scenario: Altium documents are unchanged
- **GIVEN** the catalog blink built with `--target altium --dry-run`, once as the code is and once with the property step of `mod.prepare_authored_definition` patched in the test to add nothing
- **WHEN** `uv run pytest tests/unit/cli/test_catalog_only.py -k altium` compares the two plans
- **THEN** every planned file has the same SHA-256 in both, and both runs report the same issue codes
