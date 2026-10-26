## MODIFIED Requirements

### Requirement: Probe results per kicad-cli version
`tests/kicad/_probes.py` SHALL define the closed mapping `PROBES` (probe id → probe function and the majors it runs on) and `run(probe_id) -> str`, memoised per test session. An outcome MUST be one of `load`, `reject`, `present`, `absent`, `equal`, `different`, `inconclusive` and `timeout`.
- Oracle tests MUST assert on `run(…)` rather than run a probe themselves.
- `tests/kicad/test_probe_results.py` MUST run every probe of the running major and compare the outcomes with `docs/evidence/kicad/probes/<version>.json`. `<version>` is the first line of `kicad-cli version` restricted to `[0-9A-Za-z.+-]`.
- With `FENOLITE_PROBES_WRITE=1`, the test MUST write that file instead of comparing.
- A missing file for the running version MUST fail the test with a message naming `FENOLITE_PROBES_WRITE`.
- The file MUST hold only the version, the probe ids and their outcomes, and MUST pass the residue scan.
- The `kicad-9` and `kicad-10` jobs MUST run the comparison in required mode.
- A probe whose corpus input is not cached on the machine SHALL raise `NotFetched` (`tests/_resources.py`); `run` MUST then give `inconclusive` and add the id to `_probes.NOT_FETCHED`, and the comparison MUST leave those ids out of both sides. When `FENOLITE_REQUIRE` names `corpus`, or with `FENOLITE_PROBES_WRITE=1`, such a probe MUST fail the test, naming it.

#### Scenario: Drift detected
- **GIVEN** a committed `docs/evidence/kicad/probes/10.0.6.json` that records `absent` for `pcb-libdrc-missing-table`
- **WHEN** a run on 10.0.6 yields `present` for that probe
- **THEN** `uv run pytest tests/kicad/test_probe_results.py` fails naming the probe id and both outcomes

#### Scenario: Missing results file
- **GIVEN** a `kicad-cli` whose version has no file under `docs/evidence/kicad/probes/`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs without `FENOLITE_PROBES_WRITE`
- **THEN** it fails with a message naming `FENOLITE_PROBES_WRITE`

#### Scenario: Results regenerated
- **WHEN** `FENOLITE_PROBES_WRITE=1 uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** `docs/evidence/kicad/probes/10.0.6.json` holds one outcome per probe of major 10, and `uv run python tools/residue/scan.py` exits 0

#### Scenario: Corpus input not cached
- **GIVEN** a results file that records `equal` for a probe whose corpus input is not in the cache
- **WHEN** `tests/kicad/test_probe_results.py` runs without `FENOLITE_REQUIRE=corpus`
- **THEN** that probe is left out of the comparison and no drift is reported for it; with `FENOLITE_REQUIRE=corpus` the test fails naming the probe
