## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`routing`, `cli-contract`, `net-roles`). Write under this task, with the date and the base commit that the implementation starts from:
  - whether c0222 is merged into `dev`, and whether a commit since `ff9d9e4c` changed `fenolite.roles.judge`, the branch walks of `roles/kelvin.py`, `routing/octilinear.py`, `routing/protocol.py` or `cli/cmd_route.py`;
  - c0243's state: its run order, and the names it uses for locked copper, corridors and capped hot legs. Reconcile them with decision 11 of `design.md`: take c0243's names if they landed first, and record the mapping;
  - which open change holds a delta of "Pairs and escape in a routing job" (if one was archived, regenerate the MODIFIED block from the living text);
  - that S-0890 to S-0892 are still the rows this proposal registered, and that no other branch used S-0893 to S-0919;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0244-critical-routes --strict --no-interactive`; `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.

## 1. Job, codes and plan

- [ ] 1.1 Add `JobRoleEnd`, `JobRoleRoute` and `RoutingJob.roles` to `routing/protocol.py`, add the feature `roles` to `ROUTER_FEATURES` and to `OctilinearRouter.features` (scenarios "A job built as before" of "Role routes in a routing job", "The octilinear router takes roles"). Proof: `uv run pytest tests/unit/routing/test_protocol.py -q`; `uv run pyright src/fenolite/routing`.
- [ ] 1.2 Add the six `route.role-*` codes to `routing/codes.py`, `explain.toml` and `docs/cli-contract.md` (scenario "Codes explained" of "Role route codes"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py tests/unit/routing -k codes -q`.
- [ ] 1.3 Write `fenolite.roles.routes.plan_critical`: groups to routes, with confirmed and declared groups only, open connections only, widths, gaps, layers (the reference layer first), inner-half entries, isolation, aggressors and loop points (scenario "Routes of the half-bridge", once task 4.1 has the open variants; before that, authored benches). Proof: `uv run pytest tests/unit/roles/test_routes.py -q`.
- [ ] 1.4 Add `critical_copper(design, roles)` with `power_copper_needed` (scenario "A capped hot leg"). Proof: `uv run pytest tests/unit/roles/test_routes.py -k power_copper -q`.

## 2. Role mode of the octilinear router

- [ ] 2.1 Add `routing/roleroute.py`: tiers, units of partnered routes, rounds inside a tier, and ends at `JobRoleEnd.at` (scenarios "Kelvin pair after the switch node", "Entry on the inner half"). Proof: `uv run pytest tests/unit/routing/test_roleroute.py -k "tiers or entry" -q`.
- [ ] 2.2 Isolation and keep-away in the acceptance, with zone outlines as obstacles (scenarios "A sense branch beside its own pour", "A pair over a switch-node pour" with `z-shapes=off`). Proof: `uv run pytest tests/unit/routing/test_roleroute.py -k "isolated or keepaway" -q`.
- [ ] 2.3 Cost choice among accepted shapes: role-loop area for hot legs and gate pairs, length for Kelvin pairs; no via on hot legs (scenario "The smaller loop wins"). Proof: `uv run pytest tests/unit/routing/test_roleroute.py -k hot -q`.
- [ ] 2.4 Z shapes in role mode, with `z-shapes=off` (scenarios "A pair over a switch-node pour", second run; "Plain jobs unchanged"). Proof: `uv run pytest tests/unit/routing/test_roleroute.py -k keepaway -q`; `uv run pytest tests/unit/routing/test_octilinear.py -q`.
- [ ] 2.5 Gate pairs: side by side, stacked with one via at each end, plane return (scenario "Stacked when the side is blocked"). Proof: `uv run pytest tests/unit/routing/test_roleroute.py -k gate -q`.
- [ ] 2.6 Vias per role and the options `hot-vias`, `gate-vias` and `kelvin-vias`; reason `no-layer` (scenario "No common layer"). Proof: `uv run pytest tests/unit/routing/test_roleroute.py -k vias -q`.
- [ ] 2.7 The `role_check` comparison and `route.role-refused` (scenario "A worse group is removed"). Proof: `uv run pytest tests/unit/routing/test_roleroute.py -k refused -q`.

## 3. Command

- [ ] 3.1 `route --roles critical`, `--group` and `--roles-file`; the option checks; the role job and the extras `role_check`, `clearance` and `copper_check` (scenarios "Wrong router", "No roles"). Proof: `uv run pytest tests/unit/cli/test_route_cmd.py -k roles -q`.
- [ ] 3.2 `result.roles` with statuses, connections, findings before and after, reasons and proposals with their commands and `render --region`; the verdict on role connections; `--require-complete` (scenarios "The reply of an open buck", "A blocked pair is reported"). Proof: `uv run pytest tests/unit/cli/test_route_cmd.py tests/unit/roles/test_critical_reference.py -k "reply or blocked" -q`.
- [ ] 3.3 Locks and corridors: `locked=True` on role copper, `Keepout` per isolated branch, ids in the `roles` namespace without the build's item marker (scenario "The fill leaves the sense branch alone"). Proof: `uv run pytest tests/unit/roles/test_critical_reference.py -k corridor -q`.
- [ ] 3.4 `--rip` in role mode removes only the groups' branches; `route.role-kept` without it. Proof: `uv run pytest tests/unit/cli/test_route_cmd.py -k role_rip -q`.
- [ ] 3.5 `--gate drc` drops a whole group through `together`, with reason `drc`. Proof: `uv run pytest tests/unit/cli/test_route_cmd.py -k role_gate -q` (the KiCad part in task 4.4).

## 4. Reference boards: the acceptance gate

- [ ] 4.1 Add the `open` variant to the three `*_board.make` and the scripts `open.py`, with the critical copper of `bad` left out as `design.md`, decision 17, lists. Proof: `uv run pytest tests/unit/roles/test_reference_boards.py -q` (the six variants unchanged) and `uv run pytest tests/unit/roles/test_critical_reference.py -k builds -q`.
- [ ] 4.2 The gate: each `open` variant routed and checked keeps exactly its non-critical findings, and each `good` variant plans no write (scenario "Critical findings cleared"; hypotheses `H-G-CRIT-KELVIN`, `H-G-CRIT-GATE`, `H-G-CRIT-HOT`, `H-G-CRIT-KEEPAWAY`). Record each measure under this task. Proof: `uv run pytest tests/unit/roles/test_critical_reference.py -q`.
- [ ] 4.3 Idempotence: a second run writes nothing, and two rebuilds of a routed `open` project keep the role copper and corridors with equal bytes (`H-G-CRIT-IDEMPOTENT`). Proof: `uv run pytest tests/unit/roles/test_critical_reference.py -k again -q`.
- [ ] 4.4 KiCad DRC: `route --roles critical --gate drc` on each `open` variant drops nothing and adds no violation type, on KiCad 9 and 10 (`H-K-CRIT-DRC`). Proof: `uv run pytest tests/kicad/roles/test_critical_drc.py -q` in the jobs `kicad-9` and `kicad-10` on the pushed commit.
- [ ] 4.5 Altium output: convert each routed `open` variant and compare the read-back (scenario "Same critical copper in Altium"; `H-A-CRIT-READBACK`). Proof: `uv run pytest tests/unit/roles/test_critical_reference.py -k altium -q`.

## 5. Closing

- [ ] 5.1 Docs: `docs/routing.md` (the role mode, its options, the order, the interface with power copper), `docs/roles.md` (critical routes, the reasons and proposals, the Altium deliverable through `convert`, the run order with power copper), and `docs/cli-contract.md` ("route": `--roles`, `--group`, `--roles-file`, `result.roles`, the codes). Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/cli -k "contract or explain" -q`.
- [ ] 5.2 Agent guide (AGENTS.md rule 6): a tested line for `route --roles critical` with a `fenolite-cmd` block on the page `routing`, and one on `board-power` for the order "critical routes, then power copper". No limit as a value, no change id. Then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [ ] 5.3 Residue: the `open.py` scripts and the benches carry the authored-for-Fenolite line, and every new `.py` starts with its SPDX and copyright lines. Proof: `make residue`.
- [ ] 5.4 Run `make check-fast` and the focused tests of the touched files, then push the batch and confirm the required CI jobs on the exact commit (AGENTS.md rule 4; no full suite on the maintainer's machine). Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 5.5 Evidence: the seven hypotheses in `docs/hypotheses.md` with their measurements; S-0890 to S-0892 cited from `src/fenolite/roles/PROVENANCE.md`, the provenance file of the package that plans the routes; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 5.6 Add an entry under `## [Unreleased]` in `CHANGELOG.md`, only after `0.7.0.dev0` has opened. The v0.6 guard requires `[Unreleased]` empty while `0.6.0` is cut and not published. Proof: `uv run pytest tests/unit -k changelog -q`; `uv run pytest tests/unit/test_release_record_v06.py -q` until 0.6.0 is published.
