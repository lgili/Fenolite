## ADDED Requirements

### Requirement: Routing smoke job
`.github/workflows/ci.yml` SHALL contain a job `routing` that runs on every push to `main` and on pull requests, inside the pinned `kicad/kicad:10.0.6` image of the `kicad-10` job, and that is NOT a required check for merging, because it downloads third-party code. It MUST run these steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `kicad-cli version`
4. `uv sync --locked --extra dev`
5. a clone of `https://github.com/drandyhaas/KiCadRoutingTools` at the tag `routingtools.PINNED_TAG`, whose commit hash the step prints
6. the tool's build step (`python build_router.py`) and its dependencies installed in a virtual environment of its own, never in Fenolite's
7. `uv run pytest tests/routing -q -rA` with `FENOLITE_REQUIRE=kicad,router`, `FENOLITE_KRT` set to the clone and `FENOLITE_KRT_PYTHON` to that environment's interpreter

`tests/unit/test_ci_workflow.py` SHALL check the job textually: the image digest equal to `kicad-10`'s, the tag equal to `PINNED_TAG`, and the order of the steps. `docs/routing.md` SHALL say that the job is not a merge gate, because branch protection is not stored in the repository.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k routing` runs
- **THEN** it passes only if the `routing` job exists with the pinned image, clones the tool at `PINNED_TAG`, and runs `tests/routing` with `FENOLITE_REQUIRE=kicad,router`

#### Scenario: Tag drift caught
- **GIVEN** `PINNED_TAG` changed in `routingtools.py` and not in `ci.yml`
- **WHEN** the same test runs
- **THEN** it fails naming both values

### Requirement: Router resource
The marker `needs_router` SHALL skip a test when `FENOLITE_KRT` does not name a KiCadRoutingTools checkout holding `py_router/route.py`, with a reason naming `FENOLITE_KRT`, and SHALL fail it instead, with the same message, when `FENOLITE_REQUIRE` lists `router`. This adds the resource `router` beside `kicad`, `corpus` and `libs` of "Required-resource mode", whose rules stay as they are.

#### Scenario: Missing tool fails in the routing job
- **GIVEN** `FENOLITE_REQUIRE=router` and no `FENOLITE_KRT`
- **WHEN** `uv run pytest tests/unit/test_conftest_require.py -k router` runs a `needs_router` test through `pytester`
- **THEN** it fails with a message naming `FENOLITE_KRT`

#### Scenario: Default is skip
- **GIVEN** neither variable set
- **WHEN** `uv run pytest tests/routing -q` runs
- **THEN** every test is skipped and the exit code is 0
