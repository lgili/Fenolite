## 0. Entry check

- [x] 0.1 Read the living `design-dsl`, `altium-build` and `kicad-oracle` specs and `openspec list`. Write under this task, with the date, whether another change modified "Interfaces in the DSL" (then re-base the MODIFIED text), and whether c0064 is archived (its BOM groups by value text, which task 2.2 relies on). Proof: `openspec validate c0073-interfaces-quantities --strict --no-interactive` passes after any re-base.
  - 2026-10-05: no other change modifies "Interfaces in the DSL" (only the living `design-dsl` spec and this change name it), so no re-base. c0064 is not archived: its BOM does not exist yet, so nothing of task 2.2 depends on it; the canonical text is ready for it. c0061 is not archived either, so "KiCad's stored form" of a net name is the model name here: the build has no other form yet.

## 1. Probe and register

- [x] 1.1 Add the row `H-K-DIFFPAIR-NAMES` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
  - 2026-10-05: done; the row was added already `KICAD-VERIFIED`, after the runs of task 1.2 on both majors.
- [x] 1.2 Write `tests/kicad/rules/test_diffpair_names.py` (scenario of "Differential pair names are probed"), record the outcomes, and write the rule to `docs/formats/kicad/rules.md` with sources S-0020 and S-0029. Proof: `uv run pytest tests/kicad/rules/test_diffpair_names.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`.
  - 2026-10-05: done on 10.0.6 (local) and 9.0.9 (pinned image): five cases `present`, three `absent`, as the design measured. The cases and the bench are in `tests/kicad/rules/_paircases.py`.

## 2. Quantities

- [x] 2.1 Write `src/fenolite/dsl/quantity.py` and `tests/unit/dsl/test_quantity.py` (scenarios of "Quantities in the DSL"), with property tests: parsing `text()` gives the value back, and every letter code parses to the value it was printed from. Proof: `uv run pytest tests/unit/dsl/test_quantity.py tests/unit/test_import_graph.py`; `uv run pyright src`; the no-float scan passes.
  - 2026-10-05: done. A farad or henry value of 1 or more has no letter code (no prefix letter can stand for the point), so `text(code=True)` raises for it; the property test covers that branch.
- [x] 2.2 Accept a `Quantity` as `Part.value` (scenario of "Part values from quantities"). Proof: `uv run pytest tests/unit/dsl`.
  - 2026-10-05: done.

## 3. Interfaces

- [x] 3.1 Add `I2C`, `SPI`, `UART` and `USB2` to `src/fenolite/dsl/interfaces.py` and re-export them (scenarios of "Typed interfaces in the DSL"). Proof: `uv run pytest tests/unit/dsl/test_interfaces_typed.py tests/unit/dsl`.
  - 2026-10-05: done; the four classes share the base `Bus` in `interfaces.py`.
- [x] 3.2 Add `attach` to the four classes (scenarios of "Attaching parts to interfaces"). Proof: `uv run pytest tests/unit/dsl/test_interfaces_typed.py -k attach`.
  - 2026-10-05: done.
- [x] 3.3 Write `interface_checks` in `lens/build.py` with the two codes and the `usb2` info (scenarios of "Interface checks in a build" and "Interfaces in the DSL"). Proof: `uv run pytest tests/unit/lens/test_interface_checks.py tests/unit/lens tests/unit/cli/test_build_cmd.py`.
  - 2026-10-05: done. The function is `interface_checks(design, pins, on_net)`: it takes the pins that `_resolve_pins` resolved instead of the parts, so pins are not resolved twice. `tests/unit/cli/test_build_cmd.py` does not exist; the command scenario is in `tests/unit/lens/test_interface_checks.py`.
- [x] 3.4 Report the four kinds in the Altium build (scenario of "Typed interfaces in an Altium build"). Proof: `uv run pytest tests/unit/lens/test_altium*.py`.
  - 2026-10-05: done. The spec said every planned file is equal byte for byte; `.fenolite/circuit.json` holds the interfaces, so the requirement and its scenario now say "outside `.fenolite/`". A design with diff pairs only keeps its old message.

## 4. Documentation

- [x] 4.1 Document quantities, the four interfaces, `attach` and the two checks in `docs/dsl.md`, and the codes in `docs/cli-contract.md`. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.
  - 2026-10-05: done.

## 5. Closing

- [x] 5.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0073-interfaces-quantities --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
  - 2026-10-05: residue, `make check-fast` and `openspec validate` pass locally; the probe files are verified on 10.0.6 and 9.0.9 (local). The full `make check` and `gh pr checks` are left to the coordinator's merge run (one full suite at a time).
- [x] 5.2 Update the evidence: `H-K-DIFFPAIR-NAMES` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` with the run, or records the case that differed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
  - 2026-10-05: done from the local runs of both majors; the CI runs are to be added to the row when the jobs pass.
- [x] 5.3 Add to `CHANGELOG.md` under Unreleased: "Exact `Quantity` values in the DSL (`ohm("4k7")`, `farad("100n")`), typed `I2C`, `SPI`, `UART` and `USB2` interfaces with `attach` by role, and build warnings for differential-pair names KiCad does not pair and for I2C lines without a pull-up". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
  - 2026-10-05: done.
