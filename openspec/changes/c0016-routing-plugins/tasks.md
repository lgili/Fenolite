## 1. Registers and documentation

- [ ] 1.1 Register sources and hypotheses. This is the first commit of the implementation, so c0014's cited-id guard sees the ids registered.
  - Add S-0215 to S-0218 to `docs/evidence/sources.md` from design "Sources registered by this change", after opening each page at the pinned tag: the consultation date, the commit of the tag, and the licence each page or the LICENSE file states.
  - Add the rows `H-K-KRT-CLI`, `H-K-KRT-ROUTE`, `H-K-KRT-KEEP` and `H-K-KRT-REPEAT` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and result `pending`. Remove `H-K-KRT-*` from the reserved-families table, and add the paragraph "Change c0016 (routing plugins) adds …".
  - Re-check every name consumed from c0013, c0017, c0019, c0020 and c0028 (design "Context" and "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-KRT-' docs/hypotheses.md` prints `4`.
- [ ] 1.2 Write the skeleton of `docs/routing.md` (plugin contract, built-in routers, how to install KiCadRoutingTools at the pinned tag, loop order, the CI job is no merge gate) and of `docs/evidence/routing.md` (the gate table, empty). Add a `LEGAL-ANNEX.md` session row naming the tool as a program run across a process boundary, with its licence. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_legal_docs.py`; `uv run python tools/residue/scan.py` exits 0.

## 2. Feasibility gate (KiCadRoutingTools at `v0.22.1`; `kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [ ] 2.1 Install the tool at the pinned tag in a folder outside the repository, with its dependencies in an environment of its own, and record in `docs/evidence/routing.md`: the commit of the tag, the platform, the interpreter version, how the binary was obtained, and where the tool states its version (design, Open Questions). Add the marker `needs_router` and the resource `router` to `tests/conftest.py`, with `tests/unit/test_conftest_require.py -k router`. Proof: `uv run pytest tests/unit/test_conftest_require.py -k router`; `FENOLITE_KRT=<dir> FENOLITE_KRT_PYTHON=<python> <python> <dir>/py_router/route.py --help` exits 0.
- [ ] 2.2 Write `tests/routing/test_krt_gate.py` with `test_cli`, `test_route`, `test_keep` and `test_repeat`, using only `fenolite build`, `write_board`, `read_board`, `KicadCli.drc` and `subprocess` (no plugin code yet), and a helper that appends each outcome to `docs/evidence/routing.md` when `FENOLITE_ROUTING_EVIDENCE=1`. Run it on 10.0.6 for target 10 and inside the 9.0.9 image, with the tool mounted, for target 9. Apply design Decision 1: record the verdict, and on a failed major register the successor row and note the consequence for c0023 under this task. Proof: `FENOLITE_REQUIRE=kicad,router uv run pytest tests/routing/test_krt_gate.py -rA` on both majors; `docs/evidence/routing.md` holds the verdict.

## 3. Protocol, registry, selection and merge

- [ ] 3.1 Write `src/fenolite/routing/{__init__,protocol,codes}.py` and `registry.py`, declare the entry points in `pyproject.toml`, widen the `routing.plugins.<x>` row of `tests/unit/test_import_graph.py` to `routing`, `model`, `geometry` and `backends.<same>` (MODIFIED "Allowed import edges"), and write `tests/unit/routing/test_protocol.py` and `test_registry.py` (scenarios of "Router protocol" and "Router registry", with a broken and a duplicate entry point built through `importlib.metadata` test doubles). Proof: `uv run pytest tests/unit/routing -k "protocol or registry" tests/unit/test_import_graph.py tests/unit/test_pyproject_invariants.py`; `uv run pyright src`.
- [ ] 3.2 Write `routing/select.py` and `routing/merge.py` with `tests/unit/routing/test_select.py` and `test_merge.py`, covering every scenario of "Net selection" and "Routed copper is merged", plus a locked track that `rip` keeps and RT1 of a merged board written for targets 9 and 10. Proof: `uv run pytest tests/unit/routing -k "select or merge"`.
- [ ] 3.3 Write `routing/direct.py` with `_ROUTER: Router = DirectRouter()` and `tests/unit/routing/test_direct.py` (scenario "Two-pad net", pads on different layers, determinism). Add `tests/data/kicad/routing/two_pads.kicad_pcb`, authored through the model API, with its row in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/unit/routing -k direct`; `uv run pyright src`.

## 4. KiCadRoutingTools plugin

- [ ] 4.1 Write `tests/_fakerouter.py` (a fake checkout with `py_router/route.py`, configurable to add a segment, drop a track, fail or sleep) and `src/fenolite/routing/plugins/kicad/routingtools.py` (design Decision 7), with `tests/unit/routing/test_routingtools.py` covering every scenario of "KiCadRoutingTools plugin", plus a timeout, `route.tool-unpinned`, the flags passed per net, and a run folder outside the project. Proof: `uv run pytest tests/unit/routing -k routingtools tests/unit/test_import_graph.py`; `uv run pyright src`.

## 5. Command, capabilities and doctor

- [ ] 5.1 Write `src/fenolite/cli/cmd_route.py` (design Decisions 8 and 10), add `EXAMPLE_UNROUTED` to `cli/_examples.py`, and write `tests/unit/cli/test_route_cmd.py`, covering every scenario of "Route command" with `direct` and the fake tool, plus `--rip`, `--nets`, `--allow-offsite` with a test router, sanitised `log`, and `route.fill-stale`. Add the `route` section and its issue table to `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli/test_route_cmd.py tests/unit/cli/test_hermetic_examples.py tests/unit/routing -k "codes or not codes" tests/consistency`.
- [ ] 5.2 Add `result.routers` to `capabilities` and to `doctor` (design Decision 9), with their tests in `tests/unit/cli/test_capabilities.py` and `test_doctor_cmd.py` (scenarios of "Routers in capabilities and doctor"). Proof: `uv run pytest tests/unit/cli -k "capabilities or doctor" tests/consistency`.

## 6. Oracle loop and CI

- [ ] 6.1 Switch `test_route` of the gate to the plugin through `fenolite route`, and write `tests/routing/test_route_oracle.py::test_loop` (scenario "Loop keeps routes"). Proof: `FENOLITE_REQUIRE=kicad,router uv run pytest tests/routing -rA` on the local KiCad 10.0.6 and inside the 9.0.9 image.
- [ ] 6.2 Add the job `routing` to `.github/workflows/ci.yml` and its textual checks to `tests/unit/test_ci_workflow.py` (scenarios of "Routing smoke job"). Proof: `uv run pytest tests/unit/test_ci_workflow.py`; the `routing` job is green on the pull request, or its failure is analysed under this task.

## 7. Closing

- [ ] 7.1 Run the residue and full test suites. Complete `docs/routing.md`. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0 (model unchanged); `make check` passes; `openspec validate c0016-routing-plugins --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
- [ ] 7.2 Update the evidence labels from the gate: `H-K-KRT-CLI`, `H-K-KRT-ROUTE` and `H-K-KRT-KEEP` become `KICAD-VERIFIED (9.0.x, 10.0.x)` for the pinned tag with the run or local-run reference, or are refuted with a successor; `H-K-KRT-REPEAT` records its outcome and its level follows the run that measured it. Update `docs/roadmap.md` with the gate verdict and its consequence for c0023. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; the verdict appears in `docs/roadmap.md` and `docs/evidence/routing.md`.
- [ ] 7.3 Add to `CHANGELOG.md` under Unreleased: "Routing plugins: a router protocol with an entry-point registry, `fenolite route` with the built-in `direct` router and the KiCadRoutingTools plugin (an external MIT tool run as a subprocess at a pinned tag), routed copper merged into the board and kept by later builds". Proof: `git diff CHANGELOG.md`.
