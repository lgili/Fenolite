## 0. Entry check

- [ ] 0.1 Read `openspec list`, `AGENTS.md`, `docs/research/electrical-requirements.md` and the living specs this change touches (`fenolite-component-catalog`, `design-model`, `design-dsl`, `verification-loop`, `cli-contract`, `net-roles`). Write under this task, with the date and the base commit:
  - what c0246 and c0248 landed: the unit table and `Decimal10`; `Rating`, `DevicePin`, `core/quantities` and the record keys. If either folder is archived, regenerate this change's requirements against the living text;
  - that no device record with c0248's single `{ min, max }` form has shipped (phase A refuses it);
  - before phase B: what c0252 and c0253 landed (the stage `circuit.rules`, `checks/circuit/`, the requirement table, the classes injected from `roles.classify`, `design.contracts`);
  - which open change holds a delta of "Waivers in the check", "Waivers in the DSL", "Waivers in the findings layer" or "Part classes"; if one was archived, rewrite the MODIFIED block from the living text;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0274-electrical-requirements --strict`; `make check-fast`.

## 1. Phase A: units and products (after c0246, before c0252)

- [ ] 1.1 Add the unit `kelvin` to `dsl/quantity.py` and to the model's `RangeUnit`, `celsius()` and `kelvin()` to `fenolite.dsl`, temperature texts in `core/quantities`, and the Celsius text of absolute temperatures (scenarios "A Celsius range", "An ambient range in kelvin"). Proof: `uv run pytest tests/unit/dsl/test_quantity.py -k "celsius or kelvin" tests/unit/model/test_circuit.py -k kelvin -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 1.2 Add the products and quotients of `volt_squared` and `ampere_squared`, refused by `RangeUnit` (scenario "The power of a bleeder"). Proof: `uv run pytest tests/unit/dsl/test_quantity.py -k products -q`.
- [ ] 1.3 Allow one-sided ranges in arithmetic where the result keeps a bound (scenario "A one-sided floor"), with property tests against `Fraction` on bounded ranges. Proof: `uv run pytest tests/unit/dsl/test_quantity.py -k one_sided -q`.

## 2. Phase A: device limits (after c0248, before c0252)

- [ ] 2.1 Split every limit of the device record into `abs_max` and `operating`, refuse the single form, and store temperatures in mK (scenarios "Both kinds on one pin", "The ambiguous form is refused", "Celsius and kelvin agree"); rewrite the shipped and test records in the split form. Proof: `uv run pytest tests/unit/catalog/test_devices.py -q`.
- [ ] 2.2 Add `[[limits]]`, the five pin thresholds and the `class` key to the parser, the canonical text and the digest (scenarios "Bootstrap to switch node" of the catalog, "A ferrite says what it is" for the parse only). Proof: `uv run pytest tests/unit/catalog/test_devices.py -k "limits or thresholds or class" -q`.
- [ ] 2.3 Add `Rating.limit`, `DevicePin.ratings` and `thresholds`, `PinPairLimit`, `DeviceDef.limits` and `cls` to `model/library.py`, regenerate the library schema, and update `docs/design-model.md` and `docs/catalog/README.md` (scenario "A split record round-trips"). Proof: `uv run pytest tests/unit/model/test_library.py -k limits -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 2.4 Tell c0252 and c0253 that phase A has landed: run their entry checks' reading of `abs_max`, `operating`, `[[limits]]`, kelvin and the products. Proof: `openspec validate c0252-parametric-interfaces --strict`; `openspec validate c0253-electrical-contracts --strict`.

## 3. Phase B: the one classifier (after c0253)

- [ ] 3.1 Add `ferrite`, `fuse` and `jumper` to `PART_CLASSES`, the prefixes `FB`, `F` and `JP` and the device `class` evidence to `roles.classify`, and make c0252's device ports take thresholds from their pins (scenarios "A ferrite, a fuse and a jumper", "A ferrite says what it is", "A port takes its pins' thresholds"). Proof: `uv run pytest tests/unit/roles/test_classify.py tests/unit/roles/test_infer_reference.py tests/unit/catalog/test_device_ports.py -k "prefixes or thresholds or class" -q`.
- [ ] 3.2 Add `ferrite` to c0253's series classes with the derating key `ferrite_current`, and update `docs/roles.md` and `docs/contracts.md`. Proof: `uv run pytest tests/unit/checks/circuit/test_ratings.py -k ferrite -q`.

## 4. Phase C and D: waivers and propagation

- [ ] 4.1 Add `Waiver.digest`, the `circuit.*` codes and the digest rules to `Design.waive`, regenerate the findings schema (scenarios "A circuit waiver keeps its digest", "A circuit waiver with its digest"). Proof: `uv run pytest tests/unit/model -k waiver_digest tests/unit/dsl/test_waivers.py -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 4.2 Add the row digest, the hint `digest <digest>`, circuit matching in `checks/waivers.py`, the waivers in the stage and in `cmd_build`'s circuit hook, `check.waiver-expired`, `result.waivers.expired` and `info` on every `circuit.*` code, with `explain.toml` and `docs/cli-contract.md` (scenarios "A waived rating on the circuit stage", "A changed rating expires the waiver", "Waived severities are allowed"; every existing scenario of "Waivers in the check" keeps passing). Proof: `uv run pytest tests/unit/checks/test_waivers.py tests/unit/checks -k "codes or waiver" -q`.
- [ ] 4.3 Add `checks/circuit/propagate.py`: links, the breadth-first hull, conflicts, origins in the table, rails judged with propagated voltages, and `design.contracts(propagate=False)`; add `examples/circuit/ferrite/` (good and bad, authored for Fenolite); register `H-G-CIRCUIT-PROPAGATION` in `docs/hypotheses.md` (scenarios "An analog rail behind a ferrite", "The origin of a propagated value"). Proof: `uv run pytest tests/unit/checks/circuit/test_propagate.py tests/unit/test_hypotheses_register.py -q`.

## 5. Phase E: decidable stages

- [ ] 5.1 Add `decidable` to `RequirementRow`, the closed table, the per-subject reach (outline and open connections), the status `deferred` and `summary.deferred` to `circuit.rules` and `roles.rules`; role findings that do not fail are not reported while deferred (scenario "Track width before routing"). Proof: `uv run pytest tests/unit/checks/circuit/test_decidable.py tests/unit/roles -q`.

## 6. Phase F: the matrix

- [ ] 6.1 Give every row family its stable id form (`design.md`, decision 7) (scenario "Ids survive a reordered script"). Proof: `uv run pytest tests/unit/checks/circuit/test_matrix.py -k stable -q`.
- [ ] 6.2 Add `--matrix` to `fenolite check`: `result.matrix` with rows and receipt, statuses `waived` and `deferred`, the text table, and `docs/cli-contract.md` (scenarios "The matrix of the bad sensor", "The matrix in a terminal"). Proof: `uv run pytest tests/unit/cli/test_check_matrix.py tests/unit/cli/test_check_cmd.py -q`.
- [ ] 6.3 Register `H-G-CIRCUIT-ROW-IDS` in `docs/hypotheses.md` with its measurement. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 7. Docs, guide, changelog and CI

- [ ] 7.1 Docs: `docs/catalog/README.md` (limits, `[[limits]]`, thresholds, `class`, temperatures), `docs/dsl.md` (temperatures, products, one-sided ranges, circuit waivers), `docs/contracts.md` (origins, propagation, decidable stages, the matrix, waivers that expire), `docs/roles.md` (the three classes). Proof: `uv run pytest tests/consistency tests/unit/test_docs_links.py -q`.
- [ ] 7.2 Agent guide (AGENTS.md rule 6): tested lines for `celsius`, `kelvin` and a `circuit.*` waiver with its digest on `design-script`; `fenolite check --matrix`, `deferred` and `check.waiver-expired` on `checks`; `[[limits]]`, `abs_max` and `operating` on `board-power`. Then run the generator. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 7.3 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 7.4 Residue: every authored record and example carries its authored-for-Fenolite line, and no threshold, rating or table comes from another project or a standard. Proof: `make residue`.
- [ ] 7.5 Push each phase to the working branch and confirm that the required unit and KiCad jobs pass on that exact commit; run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4). Proof: the CI run of the commit is green; `make check-fast` passes locally.
- [ ] 7.6 Validate the change. Proof: `openspec validate c0274-electrical-requirements --strict`.
