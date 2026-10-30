## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs `enclosure-model`, `enclosure-fit` and `cli-contract`; record under this task, with the date and base commit: c0307 to c0309's state and their final names for faces, apertures and the judge; that `enclosure.template-*` collides with no code; that S-0955 to S-0957 are still this line's rows; the maintainer's answers to the open questions (readers, tiling). Proof: `openspec validate c0310-panel-templates --strict --no-interactive`; `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.

## 1. Geometry

- [ ] 1.1 `enclosure/templates.py`: face rectangles, split line, flat rectangle, datum, openings grown by clearance, centres from the datum, ordering (scenario "Front face of the example"). Proof: `uv run pytest tests/unit/enclosure/test_templates.py -k front -q`.

## 2. Writers

- [ ] 2.1 Record the format facts used in `docs/formats/templates/svg.md`, `pdf.md` and `dxf.md` with S-0955 to S-0957 and their labels. Proof: `uv run pytest tests/unit/test_provenance.py -q`.
- [ ] 2.2 SVG writer (scenario "Sizes in each format", SVG part). Proof: `uv run pytest tests/unit/enclosure/test_template_formats.py -k svg -q`.
- [ ] 2.3 PDF writer: objects, content stream, Béziers for arcs, `/PrintScaling /None`, information dictionary and `--timestamp` (PDF part). Proof: `uv run pytest tests/unit/enclosure/test_template_formats.py -k pdf -q`.
- [ ] 2.4 DXF writer: header, layers, entities (DXF part). Proof: `uv run pytest tests/unit/enclosure/test_template_formats.py -k dxf -q`.
- [ ] 2.5 Golden files authored for Fenolite and the determinism test on the three CI platforms (scenario "Golden files"; `H-G-ENCL-TEMPLATE-BYTES`). Proof: `uv run pytest tests/unit/enclosure/test_templates.py -k golden -q`.

## 3. Command

- [ ] 3.1 `enclosure templates`: options, record lookup, judge first, plan and receipt, the two codes in `explain.toml` and `docs/cli-contract.md` (scenarios "An aperture off its face", "Faces and receipt"). Proof: `uv run pytest tests/unit/cli/test_enclosure_templates.py -q`; `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 3.2 Independent readers for `H-G-ENCL-TEMPLATE-FILES`, as the maintainer decides (open question 1), skipped when absent. Proof: `uv run pytest tests/unit/enclosure/test_template_readers.py -q` in CI.
- [ ] 3.3 Ask the maintainer to print the example's front template and measure the scale bar and the test opening; record `H-G-ENCL-TEMPLATE-SCALE`. Proof: the row names the report; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 4. Docs and guide

- [ ] 4.1 `docs/enclosures.md` ("Face templates": printing at 100 %, measuring the bar, drilling from outside, DXF for services) and `docs/cli-contract.md` (`enclosure templates`). Proof: `uv run pytest tests/unit/docs tests/consistency -q`.
- [ ] 4.2 Agent guide: a tested line on `fabrication.md` for `enclosure templates`; regenerate. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.

## 5. Closing

- [ ] 5.1 Residue and fast checks. Proof: `make residue`; `make check-fast`.
- [ ] 5.2 Evidence labels of the three hypotheses. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 5.3 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.4 CI green on the exact commit. Proof: the required jobs of `gh run list --branch <branch> --limit 1` succeed.
