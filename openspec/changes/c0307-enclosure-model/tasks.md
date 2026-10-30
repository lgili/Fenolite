## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs `canonical-serialization`, `design-model`, `package-layering` and `cli-contract`; record under this task, with the date and base commit: c0306's state (the command `enclosure` must exist or land first); which open change holds a delta of "Allowed import edges" (regenerate the MODIFIED block from the living text if one was archived); whether `FEN-3009` is still free; the maintainer's answers to the open questions of `design.md`. Proof: `openspec validate c0307-enclosure-model --strict --no-interactive`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 1. Model, reader and writer

- [ ] 1.1 Write the dataclasses of `fenolite.model.enclosure` with their structural checks (scenario "A fixture box loads"). Proof: `uv run pytest tests/unit/model/test_enclosure.py -k loads -q`; `uv run pyright src/fenolite/model`.
- [ ] 1.2 `dump_enclosure` and `load_enclosure`: canonical form, schema validation, pointers in errors (scenarios "Round trip", "A float refused", "A boss outside the floor"). Proof: `uv run pytest tests/unit/model/test_enclosure.py -k "round or float or boss" -q`.
- [ ] 1.3 Provenance and per-field evidence rules (scenario "A label above INFERRED refused"). Proof: `uv run pytest tests/unit/model/test_enclosure.py -k evidence -q`.
- [ ] 1.4 Generate `schemas/fenolite.enclosure.v0.json` in `tools/gen_schemas.py` and cover it by the drift test. Proof: `uv run python tools/gen_schemas.py --check`; `uv run pytest tests/unit/test_schema_drift.py -q`.

## 2. Package and derivation

- [ ] 2.1 Create `fenolite.enclosure` and the import edge (scenario "The enclosure package stays below the command"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 2.2 Author the three fixture boxes with hand-computed expected areas in the test file (scenario "Fixture provenance"). Proof: `uv run pytest tests/unit/model/test_enclosure.py -k provenance -q`.
- [ ] 2.3 `derive`: cavity at board level with draft and corner arcs, obstacles through the board, guides, zones top and bottom, rounding direction, weakest evidence (scenarios "Hand-computed areas", "Deterministic"; `H-G-ENCL-DERIVED`). Proof: `uv run pytest tests/unit/enclosure/test_derive.py -q`.

## 3. Command actions

- [ ] 3.1 `enclosure show`: validation, derivation, drift, `weakest`, `enclosure.boss-outside`, `enclosure.field-assumed`; `FEN-3009` in the registry and `explain.toml` (scenarios "Drift reported", "Refused document"). Proof: `uv run pytest tests/unit/cli/test_enclosure_show.py -q`; `uv run pytest tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 3.2 `enclosure derive` through the mutation protocol (scenario "Derive writes only derived fields"). Proof: `uv run pytest tests/unit/cli/test_enclosure_show.py -k derive -q`.

## 4. Docs and guide

- [ ] 4.1 `docs/design-model.md` ("Enclosure model": frame, faces, fields, basis and evidence, CC0 rule) and `docs/enclosures.md` ("Box models": authoring one box from a datasheet, what never to store, the stage 2 library in `lgili/fenolite-library`). Proof: `uv run pytest tests/unit/docs -q`.
- [ ] 4.2 `docs/cli-contract.md` (`enclosure show`, `enclosure derive`, the three codes); agent guide: tested lines on `fabrication.md` for `show` and `derive`, a `recovery.md` row for `FEN-3009`; regenerate. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py tests/consistency -q`.
- [ ] 4.3 `src/fenolite/enclosure/PROVENANCE.md`: the fixtures are authored for Fenolite, CC0; no vendor data. Proof: `make residue`.

## 5. Closing

- [ ] 5.1 Residue and fast checks. Proof: `make residue`; `make check-fast`.
- [ ] 5.2 Evidence labels: `H-G-ENCL-DERIVED` and `H-G-ENCL-CANON` (the canonical test on the three CI platforms). Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 5.3 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.4 CI green on the exact commit. Proof: the required jobs of `gh run list --branch <branch> --limit 1` succeed.
