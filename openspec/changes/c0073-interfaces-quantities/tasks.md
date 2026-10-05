## 0. Entry check

- [ ] 0.1 Read the living `design-dsl`, `altium-build` and `kicad-oracle` specs and `openspec list`. Write under this task, with the date, whether another change modified "Interfaces in the DSL" (then re-base the MODIFIED text), and whether c0064 is archived (its BOM groups by value text, which task 2.2 relies on). Proof: `openspec validate c0073-interfaces-quantities --strict --no-interactive` passes after any re-base.

## 1. Probe and register

- [ ] 1.1 Add the row `H-K-DIFFPAIR-NAMES` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Write `tests/kicad/rules/test_diffpair_names.py` (scenario of "Differential pair names are probed"), record the outcomes, and write the rule to `docs/formats/kicad/rules.md` with sources S-0020 and S-0029. Proof: `uv run pytest tests/kicad/rules/test_diffpair_names.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`.

## 2. Quantities

- [ ] 2.1 Write `src/fenolite/dsl/quantity.py` and `tests/unit/dsl/test_quantity.py` (scenarios of "Quantities in the DSL"), with property tests: parsing `text()` gives the value back, and every letter code parses to the value it was printed from. Proof: `uv run pytest tests/unit/dsl/test_quantity.py tests/unit/test_import_graph.py`; `uv run pyright src`; the no-float scan passes.
- [ ] 2.2 Accept a `Quantity` as `Part.value` (scenario of "Part values from quantities"). Proof: `uv run pytest tests/unit/dsl`.

## 3. Interfaces

- [ ] 3.1 Add `I2C`, `SPI`, `UART` and `USB2` to `src/fenolite/dsl/interfaces.py` and re-export them (scenarios of "Typed interfaces in the DSL"). Proof: `uv run pytest tests/unit/dsl/test_interfaces_typed.py tests/unit/dsl`.
- [ ] 3.2 Add `attach` to the four classes (scenarios of "Attaching parts to interfaces"). Proof: `uv run pytest tests/unit/dsl/test_interfaces_typed.py -k attach`.
- [ ] 3.3 Write `interface_checks` in `lens/build.py` with the two codes and the `usb2` info (scenarios of "Interface checks in a build" and "Interfaces in the DSL"). Proof: `uv run pytest tests/unit/lens/test_interface_checks.py tests/unit/lens tests/unit/cli/test_build_cmd.py`.
- [ ] 3.4 Report the four kinds in the Altium build (scenario of "Typed interfaces in an Altium build"). Proof: `uv run pytest tests/unit/lens/test_altium*.py`.

## 4. Documentation

- [ ] 4.1 Document quantities, the four interfaces, `attach` and the two checks in `docs/dsl.md`, and the codes in `docs/cli-contract.md`. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 5. Closing

- [ ] 5.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0073-interfaces-quantities --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 5.2 Update the evidence: `H-K-DIFFPAIR-NAMES` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` with the run, or records the case that differed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [ ] 5.3 Add to `CHANGELOG.md` under Unreleased: "Exact `Quantity` values in the DSL (`ohm("4k7")`, `farad("100n")`), typed `I2C`, `SPI`, `UART` and `USB2` interfaces with `attach` by role, and build warnings for differential-pair names KiCad does not pair and for I2C lines without a pull-up". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
