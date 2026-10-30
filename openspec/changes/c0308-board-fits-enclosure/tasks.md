## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs `design-dsl`, `design-model` and `enclosure-model` (c0307 archived, or its folder); record under this task, with the date and base commit: c0307's final field names for `usable`, `zones`, bosses and screws, and map them into decisions 4 and 5 of `design.md`; whether `Part.place` can carry an anchor on a part that `hole()` placed; the maintainer's answers to the open questions. Proof: `openspec validate c0308-board-fits-enclosure --strict --no-interactive`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 1. Model of the record

- [ ] 1.1 Add `Fit`, `FaceRule` and `ApertureShape` to `fenolite.model.enclosure`, their reader and writer, the digest check, and `schemas/fenolite.enclosure-fit.v0.json` (scenario "Round trip" of "Fit record document"). Proof: `uv run pytest tests/unit/model/test_enclosure_fit.py -q`; `uv run python tools/gen_schemas.py --check`.

## 2. DSL

- [ ] 2.1 `Design.fit`, `Enclosure.load`, the pose transform and `Fit.to_board`; re-exports (scenarios "Recorded, nothing generated", "Refused calls", "Four rotations"; `H-G-ENCL-POSE`). Proof: `uv run pytest tests/unit/dsl/test_fit.py -k "recorded or refused or pose" -q`.
- [ ] 2.2 `Fit.outline` with arcs and `Fit.holes()` with drill, courtyard and anchor intent (scenario "Four holes"). Proof: `uv run pytest tests/unit/dsl/test_fit.py -k "outline or holes" -q`.
- [ ] 2.3 `Fit.zones()`: rule areas, thickness source, limits, footprint keep-outs where the limit is 0 or less (scenario "Limits and keep-outs"). Proof: `uv run pytest tests/unit/dsl/test_fit.py -k zones -q`.
- [ ] 2.4 `Aperture` and `Fit.face()` (scenario "A wall aperture without height"). Proof: `uv run pytest tests/unit/dsl/test_aperture.py tests/unit/dsl/test_fit.py -k face -q`.

## 3. Build

- [ ] 3.1 `dsl.fit_record` and the record in the build plan for both targets; removal when the call goes (scenario "Record written and unchanged designs"). Proof: `uv run pytest tests/unit/cli/test_build_fit.py -q`.
- [ ] 3.2 `examples/enclosure/fit_box.py` with a fixture box copied as `examples/enclosure/boxes/`, CC0 and authored for Fenolite. Proof: `uv run pytest tests/unit/examples -k enclosure -q`.
- [ ] 3.3 KiCad probe `H-K-ENCL-FIT-BUILD` (scenario "Example board"). Proof: `uv run pytest tests/kicad/enclosure/test_fit_build.py -q` in the jobs `kicad-9` and `kicad-10`.

## 4. Docs and guide

- [ ] 4.1 `docs/dsl.md` ("Enclosures": `fit`, outline, holes, zones and their limits, faces and apertures, the record) and `docs/enclosures.md` ("Board fits box"). Proof: `uv run pytest tests/unit/docs -q`.
- [ ] 4.2 Agent guide: a tested design-script line using `design.fit` on `design-script.md`; regenerate `dsl-reference` for `fit`, `Enclosure`, `Fit`, `Aperture`. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.

## 5. Closing

- [ ] 5.1 Residue and fast checks. Proof: `make residue`; `make check-fast`.
- [ ] 5.2 Evidence labels of `H-G-ENCL-POSE` and `H-K-ENCL-FIT-BUILD`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 5.3 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.4 CI green on the exact commit (unit and KiCad jobs). Proof: the required jobs of `gh run list --branch <branch> --limit 1` succeed.
