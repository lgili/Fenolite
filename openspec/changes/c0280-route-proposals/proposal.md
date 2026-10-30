## Why

Phase 4 of the router that works from electrical intent ("propose and lock", c0222). Phases 1 (c0243)
and 2 (c0244) are archived. The maintainer decided: critical routes and power copper are automatic,
**everything else is proposed, never silently committed**; phase order 0 → 1 → 2 → 4 → 3; KiCad and
Altium output; limits from public sources and the user; creepage declared by the user.

After phases 1 and 2 the reference boards still hold real opens, recorded by c0243's DRC run: a ground pad
on `F.Cu` whose plane is on `B.Cu` with no via (buck `C3-2`, `J2-2`), a Kelvin-source track that does not
reach its copper (half-bridge), an inferred net that role copper skipped (bms `FET_S`). Signal nets are not
routed at all. A single "best" score hides the trade-off (a shorter route over switching copper).

## What Changes

- **Subjects.** `fenolite route PATH --router octilinear --propose` finds every open connection after
  phases 1 and 2 and sorts it into one subject kind: `fanout` (a pad and its net's zone on another layer),
  `join` (pieces of one net that role copper left apart, and `roles.copper-blocked` edges), `role-net` (an
  inferred role net left without copper), `group` (a critical group that phase 2 left `unrouted` or
  `refused`) and `connection` (the rest).
- **Candidates.** Up to `--candidates N` (default 4) distinct shapes per subject from the octilinear
  router: c0228's shapes, c0244's Z shapes, one-via L shapes, zone fan-out vias, and for a `group` c0244's
  role mode with one named relaxation (`kelvin-vias`, `gate-vias`, `keep-away`).
- **Facts, no score.** Each candidate carries facts: connections closed, open connections before and
  after, copper-check and role findings before and after, KiCad DRC findings with `--gate drc`, vias,
  length, layers, loop area where a role loop is measured, relaxations, conflicts, and what could not be
  evaluated. The reply `result.proposals` holds no score, rank or "recommended" field.
- **Lock through a reviewed plan.** `--accept ID` (repeatable) plans the candidate's copper as locked
  items plus the decision record; `--confirm --plan ID` writes both. `--reject ID [--reason TEXT]`
  remembers a candidate or a whole proposal. `--replay` re-places locked decisions missing from a board;
  `--forget ID` drops one.
- **Decision record** `fenolite.route-decisions.v0` beside the roles document.
- **Viewer.** `fenolite view --proposals run|FILE` joins a reply to the scene; with `--allow-actions` the
  page gets `route-accept` and `route-reject` (c0303, c0305). The drawing belongs to the viewer line.
- **Altium.** As c0244: `fenolite convert --to altium` of the KiCad board keeps the locked copper.
- **Reference boards.** The six role-copper variants become fully connected with phases 1, 2 and 4, with
  KiCad DRC as the proof.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routing`: subjects and candidates in the protocol, the feature `propose`, candidate families, codes.
- `cli-contract`: route proposals, facts, accept and reject, the decision record, replay, `view --proposals`.
- `net-roles`: leftover opens proposed, proposals on the reference boards and both backends; MODIFIED
  "Critical route failures" (proposal `propose`).
- `board-viewer`: route proposals on a board, accept and reject from a served page.

## Non-goals

- No search router and no rip-up across nets: phase 3. No placement change.
- No routing of a `.PcbDoc` in place (c0241). No creepage value of Fenolite's own.
- No code from a third-party router; no value from a paid standard.
- No external-router candidates (`--propose-with`): moved to a future change by the maintainer's decision of
  2026-10-30; a subject without candidate names an external router as its `external-router` alternative.

## Evidence level required

Candidates and facts `INFERRED` (`H-G-PROP-*`); written copper `UNVERIFIED` until checked;
`KICAD-VERIFIED` with `--gate drc` (`H-K-PROP-DRC`); Altium `INFERRED` (`H-A-PROP-READBACK`).

## Impact

- New: `routing/propose.py`, `routing/decisions.py`, `roles/proposals.py`, `cli/_propose.py`,
  `view/proposals.py`. Changed: `routing/protocol.py`, `routing/codes.py`, `cli/cmd_route.py`,
  `cli/cmd_view.py`, `view/actions.py`, docs, guide.
- Depends on c0243, c0244 (archived); viewer parts on c0303 and c0305.
- Size: about 8 design-days.
