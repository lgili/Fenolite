## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`routing`, `cli-contract`, `net-roles`, `board-viewer`). Write under this task, with the date and the base commit the implementation starts from:
  - whether a commit since the merge of c0243 and c0244 changed `routing/protocol.py`, `routing/octilinear.py`, `routing/roleroute.py`, `roles/copper.py`, `roles/routes.py` or `cli/cmd_route.py`;
  - which open change holds a delta of "Pairs and escape in a routing job" or "Critical route failures" (if one was archived, regenerate the MODIFIED blocks from the living text);
  - the state of c0303 and c0305 (merged or not, and the names of their allow-lists and routes);
  - the real opens of the six role-copper variants after phase 2, measured again with KiCad DRC after a refill: which variant holds the buck's `C3-2`/`J2-2`, the half-bridge's `ks_tie` end and the bms `FET_S`, and whether a neighbour's band lies across `FET_S`'s straight way; and whether the three `good` variants have no open connection;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `timeout 180 npx -y @fission-ai/openspec validate c0280-route-proposals --strict`; `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.

  Measured on 2026-10-30, base `b2b0b063` (`origin/dev`), KiCad 10.0.7, by the maintainer's session:
  - No commit after the merges of c0243 (`804e5586`) and c0244 (`55f485d9`) touched `routing/protocol.py`,
    `routing/octilinear.py`, `routing/roleroute.py`, `roles/copper.py`, `roles/routes.py`, `cli/cmd_route.py`
    or `cli/_roleroute.py` (`git log 804e5586..b2b0b063` on those paths is empty).
  - Only this change holds a delta of "Pairs and escape in a routing job" and "Critical route failures"; both
    MODIFIED blocks were written from the living text of `routing` and `net-roles` and stay as they are.
  - c0303 and c0305 are open changes whose code is on `dev` (commit `b2b0b063`, "the viewer of v0.7"): the
    action allow-list is `fenolite.view.actions.ACTIONS` (planned through `view.actions.plan`, served by
    `view.server`), the run allow-list is `fenolite.view.runs.ALLOWED` (`check`, `analyze`, `ready`,
    `equivalent`, `roles`). Tasks 5.1 and 5.2 can be done in this change.
  - The opens after phase 2 (each role-copper script built, `roles --accept-all --confirm`,
    `route --roles critical` confirmed, `fenolite fill` with KiCad 10.0.7, `check --stages drc.kicad`). Fenolite's
    connectivity on the pour of `analysis.pour` gives the same connections as KiCad's `unconnected_items`, on
    the unfilled board (simulated pour) and on the KiCad-filled one:

    | variant | KiCad `unconnected_items` | open connection (Fenolite) | subject |
    |---|---|---|---|
    | buck `good_roles` | `C3-2, J2-2` | GND `C3-2`~`J2-2` | `fanout:GND:C3-2` |
    | buck `bad_roles` | `C3-2, J2-2`; `zone[5], C3-1` | GND `C3-2`~`J2-2`; VOUT `segment[35]`~`C3-1` | `fanout:GND:C3-2`; `join:VOUT:…` |
    | half-bridge `good_roles` | `segment[12], Q2-3`; `segment[3], Q1-3` | SRC `Q2-2`'s return~`Q2-3`; SW `Q1-2`'s return~`Q1-3` | two `join` |
    | half-bridge `bad_roles` | `segment[15], Q2-3` | SRC `Q2-2`'s return~`Q2-3` | one `join` |
    | bms `good_roles`, `bad_roles` | `Q1-3, segment[19]`; `Q2-3, segment[20]` | FET_S `Q1-3`~`Q1-2`'s copper, `Q2-3`~`Q2-2`'s copper, 3.5 mm each | two `role-net` |

    This contradicts the spec in four points, corrected in `design.md` (decisions 2, 11 and 15) and in the
    `net-roles` and `routing` deltas: `J2-2` is a through-hole pad on the ground plane, the far end of the one
    open connection of `C3-2`, not a subject; the half-bridge open is each Kelvin-source pad's gate-return
    copper apart from its source pour (`ks_tie` of `bad` closes the high side), twice on `good_roles`; the bms
    `FET_S` has two open connections, so a `role-net` subject is one per open connection, keyed
    `role-net:<net>:<a>~<b>`; the buck `bad_roles` also holds a VOUT `join` (`C3-1` outside the VOUT pour).
  - No neighbour's band lies across `FET_S`'s way: the opens are the 3.5 mm from each source pad to its own
    Kelvin-source pad, and the straight way between `Q1-3` and `Q2-3` is free of other nets' copper (the
    `PACK_N` band ends at x = 125.36 mm, the `SHUNT_N` band starts at x = 140.64 mm, board frame).
  - The three `good` variants (`good.py`) have no open connection after phase 2: KiCad's DRC finds no
    unconnected item and Fenolite's connectivity none. The `open` variants: buck and bms none; the
    half-bridge two (`segment[13], U3-4` of GND and `R1-1, U3-3` of SRC, the sense pair that `SW_UNDER` blocks).
  - Phase 2 leaves groups `unrouted` on the role-copper variants although KiCad finds no unconnected item for
    them: buck `gate_Q1` (`isolation`, both variants) and `kelvin_R12` (`isolation`, `bad_roles`),
    half-bridge `gate_Q1` (`no-room`, `bad_roles`), bms `kelvin_R1` (`pads`, `bad_roles`). They become `group`
    subjects with no open connection of the board; the reference gate records them and rejects them whole
    (`design.md`, decision 15).
  - Open questions: the recommended answers of `design.md` are the maintainer's decisions (2026-10-30).
  - `npx` is not allowed in this session, so the `openspec validate` part of the proof could not run here.

  Left unticked: the `openspec validate --strict` part of the proof needs `npx`, which this session may not
  run; the `pytest` part passes. The deltas were checked by hand (each requirement holds SHALL or MUST and
  at least one `#### Scenario:`); run the validator before archiving.

## 1. Protocol, codes and record

- [x] 1.1 Add `JobAttach`, `JobSubject`, `Candidate`, `RoutingJob.subjects` and `RoutingResult.candidates` to `routing/protocol.py`, the feature `propose` to `ROUTER_FEATURES` and to `OctilinearRouter.features` (scenarios "A job built as before" of "Proposal subjects in a routing job", "The octilinear router takes roles"). Proof: `uv run pytest tests/unit/routing/test_protocol.py -q`; `uv run pyright src/fenolite/routing`.
- [x] 1.2 Add the eight `route.proposal-*` codes to `routing/codes.py`, `cli/data/explain.toml` and `docs/cli-contract.md` (scenario "Codes explained" of "Proposal codes"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py tests/unit/routing -k proposal -q`.
- [x] 1.3 Add `routing/decisions.py`: the `fenolite.route-decisions.v0` reader and canonical writer, sorted entries, no clock, refusal of an unknown key (scenario "A stable record"). Proof: `uv run pytest tests/unit/routing/test_decisions.py -q`.

## 2. Subjects and candidates

- [x] 2.1 Add `roles/proposals.py`: `subjects(...)` with the five kinds in their order, attach points, keys and proposal ids; group statuses from c0244's planner run in memory; `roles.copper-blocked` edges from phase 1's issues (scenario "An inferred net between two switches"; authored benches for each kind). Proof: `uv run pytest tests/unit/roles/test_proposals.py -q`.
- [x] 2.2 Add `routing/propose.py` with the families `shape`, `z-shape` and `via-l`, the distinctness rule, `candidates=N` and the generation order, and the content ids (scenarios "Candidates only", "Ids ignore unrelated copper", "Distinct candidates"). Proof: `uv run pytest tests/unit/routing/test_propose.py -k "only or ids or families" -q`; `uv run pytest tests/unit/routing/test_octilinear.py tests/unit/routing/test_roleroute.py -q` (plain and role jobs unchanged).
- [x] 2.3 The `fanout` family: the zone fan-out search inside the zone outline and its simulated fill (scenario "The same search as plane fan-out"). Proof: `uv run pytest tests/unit/routing/test_propose.py -k fanout -q`.
- [x] 2.4 The `role` family: role mode with its defaults, then one relaxation at a time, isolation never relaxed (scenario "A pair over switching copper"). Proof: `uv run pytest tests/unit/routing/test_propose.py -k relaxed -q`.
- 2.5 (removed) The optional `external:<router>` family behind `--propose-with`: moved to a future change by the
  maintainer's decision of 2026-10-30; `--propose-with` is not added, and an external router remains the
  `external-router` alternative of a subject without candidate.

## 3. Command

- [x] 3.1 `route --propose` in `cli/_propose.py`: option checks, the job, the facts (`closes`, `open`, local `copper_check`, `roles` within role reach, `loop`, `conflicts`, `fill`, `not_evaluated`), reasons and alternatives with their commands and regions, the reply (scenarios "Wrong router", "Proposing writes nothing", "Closed keys", "Facts of a fan-out", "A blocked connection"). Record under this task the time of a run on each role-copper variant. Proof: `uv run pytest tests/unit/cli/test_route_propose.py -k "router or writes_nothing or keys or fanout_facts or blocked" -q`.

  Times of `route --propose` with the default four candidates, on the variants after phase 2 (2026-10-30,
  this container, one process): buck `good_roles` 21.9 s, `bad_roles` 26.8 s; half-bridge `good_roles`
  74.5 s, `bad_roles` 41.6 s; bms `good_roles` 130.7 s, `bad_roles` 132.4 s. The role check of each candidate
  within role reach dominates (one c0222 judge run, about 2 s on the buck, 4 s on the half-bridge and 10 s on
  the bms, mostly the neck analysis of `measure_currents`); the pour is simulated once and joined again per
  candidate (`analysis.pour.rejoin`) unless the candidate comes near another net's zone.
- [x] 3.2 DRC batches under `--gate drc` with a stand-in gate (scenario "Batches of candidates"); the KiCad part in task 4.3. Proof: `uv run pytest tests/unit/cli/test_route_propose.py -k drc_batches -q`.
- [x] 3.3 `--accept` and `--reject`: recomputation, locked items in the `proposal` namespace, corridors of group candidates, the record in the same plan, `route.proposal-unknown`, `-conflict`, `-findings`, `-rejected`, `--show-rejected`, the `together` drop under `--gate drc` (scenarios "Accept, then confirm", "Unknown and conflicting ids", "A rejected candidate stays out"). Proof: `uv run pytest tests/unit/cli/test_route_propose.py -k "accept or unknown or rejected" -q`.
- [x] 3.4 `--replay` and `--forget` (scenario "Replay on a fresh build"). Proof: `uv run pytest tests/unit/cli/test_route_propose.py -k "replay or forget" -q`.
- [x] 3.5 c0244's reply names `propose` for an `unrouted` or `refused` group (MODIFIED "Critical route failures", scenario "A blocked pair is reported"). Proof: `uv run pytest tests/unit/roles/test_critical_reference.py -k blocked -q`.

## 4. Reference boards: the acceptance gate

- [x] 4.1 The leftovers: on the six role-copper variants after phase 2, the subjects of `design.md`, decision 11, each with a closing candidate (scenarios "The leftovers of phase 1"; `H-G-PROP-LEFTOVERS`). Record each subject's candidates and facts under this task. Proof: `uv run pytest tests/unit/roles/test_proposal_reference.py -k leftovers -q`.

  Measured 2026-10-30 (`--candidates 2`, the subjects of task 0.1, corrected in `design.md`, decision 2):
  buck: `fanout:GND:C3-2`, four fan-out candidates (neck and via), each `open` one lower, no new finding;
  `bad_roles` also `join:VOUT:C3-1~role.power.VOUT.F.Cu` (an L into the pour, clean). Half-bridge:
  `join:SRC:Q2-2~role.power.SRC.F.Cu` (and on `good_roles` `join:SW:Q1-2~role.switch_node.SW.F.Cu`), the pad end
  moved off the gate return; of four candidates three clean and one with `roles.gate-return-shared` (error)
  in its facts. Bms: `role-net:FET_S:Q1-2~Q1-3` and `role-net:FET_S:Q1-3~Q2-3`, taken along the power pads,
  each with clean candidates (`current: not-declared`, alternative `confirm`); along the nearest anchors (the
  first measurement) every candidate of both subjects brought `roles.gate-return-shared` on both gate loops.
  Groups that phase 2 leaves `unrouted` are `group` subjects without candidates: buck `gate_Q1`
  (`isolation`, blockers `track of net GL`, `zone role.switch_node.SW.F.Cu`) and on `bad_roles` `kelvin_R12`
  (`isolation`, `zone role.power.VL.F.Cu`); half-bridge `bad_roles` `gate_Q1` (`no-room`); bms `bad_roles`
  `kelvin_R1` (`pads`).
- [x] 4.2 The chain and its criteria: the test's selection rule, one accept plan per variant, fill, `roles --check`; facts equal to the measures after the write; `--propose` again gives `route.proposal-none`; the `good` variants need nothing; the `open` variants' proposals recorded, the half-bridge pair's facts included (scenarios "Fully connected", "Good variants need nothing"; `H-G-PROP-COMPLETE`, `H-G-PROP-FACTS`, `H-G-PROP-REPLAY`). Record each measure under this task. Proof: `uv run pytest tests/unit/roles/test_proposal_reference.py -k "complete or facts or again" -q`.

  Measured 2026-10-30: after one accept plan per variant (the groups rejected whole), the six variants have no
  open connection on the pour; `good_roles` no role finding of warning or above and `bad_roles` exactly the
  designed routing findings (buck `roles.kelvin-outer` and `roles.kelvin-shared` of `kelvin_R12`,
  half-bridge `roles.gate-loop` of `gate_Q2` and `roles.gate-return-shared` of `gate_Q1`, bms
  `roles.kelvin-shared` of `kelvin_R1`, as c0243 lists them); each accepted candidate's `open.after` equals the
  board's count once it is written, and nothing new is found by the copper check or the role check. A second
  `--propose` gives `route.proposal-none` with every decision present, and `--replay` on a fresh build gives
  the accepted board byte for byte. The `open` half-bridge's sense pair is `group:kelvin_R1` with the reason
  `near-switching`; the `good` variants need nothing.
- [x] 4.3 KiCad DRC of the accepted variants on KiCad 9 and 10 (scenario "KiCad finds no unconnected item"; `H-K-PROP-DRC`). Proof: `uv run pytest tests/kicad/roles/test_proposal_drc.py -q` in the jobs `kicad-9` and `kicad-10` on the pushed commit.

  Passed 2026-10-30 in the jobs `kicad-9` and `kicad-10` of CI run 41002715336 on commit `ef892747` (the six
  cases each), and locally with `kicad-cli` 10.0.7. On 9 the outline fill of the unit tests stands for
  KiCad's, so the zero of unconnected items is claimed on 10 and the no-growth on both (design decision 15.7).
- [x] 4.4 Altium: convert each accepted variant and compare the read-back (scenario "Same accepted copper in Altium"; `H-A-PROP-READBACK`). Proof: `uv run pytest tests/unit/roles/test_proposal_reference.py -k altium -q`.

## 5. Viewer (after c0303 and c0305 land)

- [x] 5.1 `fenolite.view.proposals.overlay` and `fenolite view --proposals run|FILE` (scenarios "The buck's proposals joined to its scene", "Proposals joined to a view"). Proof: `uv run pytest tests/unit/view/test_proposals.py tests/unit/cli/test_view_cmd.py -k proposals -q`.
- [x] 5.2 The run `proposals` and the actions `route-accept` and `route-reject` in the allow-lists of c0303 (scenario "Accept a candidate from the page"). Proof: `uv run pytest tests/unit/view/test_actions.py -k route -q`.

## 6. Closing

- [x] 6.1 Docs: `docs/routing.md` ("Proposals": subjects, families, facts, no score, accept and reject, replay), `docs/roles.md` ("Proposals after the critical routes": the leftovers, the run order 1 → 2 → 4, the Altium deliverable through `convert`), `docs/cli-contract.md` ("route": the modes, `result.proposals`, the record, the codes; "view": `--proposals`). Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/cli -k "contract or explain" -q`.
- [x] 6.2 Agent guide (AGENTS.md rule 6): a `fenolite-cmd` line and a bullet for `route --propose` and `route --accept` on the page `routing` (11 948 of 12 000 bytes: tighten sentences, or put the bullet on `board-routing` and keep only the command line on `routing`), and the order "critical routes, power copper, then proposals" on `board-power`. No limit as a value, no change id. Then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [x] 6.3 Residue: every new `.py` starts with its SPDX and copyright lines; the authored benches carry the authored-for-Fenolite line. Proof: `make residue`.
- [x] 6.4 Run `make check-fast` and the focused tests of the touched files, then push the batch and confirm the required CI jobs on the exact commit (AGENTS.md rule 4; no full suite on the maintainer's machine). Proof: `make check-fast`, and the required jobs green on the exact commit.

  `make check-fast` passed locally on 2026-10-30 (after fixing five tests that name the router features and
  the job fields); every job of CI run 41002715336 on commit `ef892747` passed (unit on Linux 3.11, 3.12,
  3.13, macOS and Windows, kicad-9, kicad-10, routing 9 and 10, viewer, mcp, wheel, dco).
- [x] 6.5 Evidence: the six hypotheses `H-G-PROP-LEFTOVERS`, `H-G-PROP-FACTS`, `H-G-PROP-COMPLETE`, `H-G-PROP-REPLAY`, `H-K-PROP-DRC` and `H-A-PROP-READBACK` in `docs/hypotheses.md` with their measurements; no new source (the facts reuse S-0850 to S-0853, S-0860 and S-0890 to S-0892 through the phases they come from); the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 6.6 CHANGELOG: an entry under `## [Unreleased]` › `### Added` (`dev` is at `0.7.0.dev0`): "`fenolite route --router octilinear --propose` lists every open connection left after the power copper and the critical routes with candidate shapes and their facts, without a score; `--accept ID` locks a candidate through a reviewed plan, `--reject ID` remembers a refusal, `--replay` restores locked decisions (c0280)." Proof: `uv run pytest tests/unit -k changelog -q`.
