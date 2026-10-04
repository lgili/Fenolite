# Tasks

- [x] 1. Add per-part pin-to-pad mapping to the DSL and canonical component, resolve nets onto physical pads, and prove identity defaults plus invalid-map refusal. Proof: `uv run pytest tests/unit/lens/test_build_pins.py tests/unit/dsl/test_footprint.py -q` (passed).
- [x] 2. Add modeled slot geometry to Padstack and DSL footprint authoring; serialize aligned slots in KiCad and keep Altium refusal explicit. Proof: focused pad, reader, board-frame and Altium PCB tests passed; `make check-fast` passed.
- [x] 3. Regenerate schemas and update API and normative specs. Proof: `uv run python tools/gen_schemas.py --check` and `openspec validate c0056-dsl-pin-pad-map-slots --strict` passed.
- [x] 4. Run focused checks, fast checks and residue scan. Proof: `make check-fast` passed (4603 passed, 9 skipped).
- [x] 5. Update evidence labels from proof results. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py tests/unit/test_provenance.py -q` passed (73 tests); facts remain `INFERRED` where not oracle-verified.
- [x] 6. Update CHANGELOG. Proof: `rg -n 'c0056' CHANGELOG.md`.
