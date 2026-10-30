## Context

- The release process is that of `0.5.0` (c0171): a record under `docs/release/`, a guard under
  `tests/unit/`, the version in three strings, the changelog cut, the history row of the residue scan, the
  README, the roadmap, and the maintainer's verdict before the tag. Since c0221 the publication is a pushed
  tag `vX.Y.Z` (`docs/releasing.md`): `release.yml` refuses a tag whose commit is not on `main` or whose
  versions and changelog section disagree (`tools/release.py check`), scans the history on the public
  patterns (c0220 task 1.1), builds both packages, publishes them and creates the GitHub Release.
- The maintainer's decision of 2026-10-29: hold the v1.0 freeze (c0216 to c0220 stay open, not implemented),
  release `0.6.0` now with what is implemented since `0.5.0`, and then `0.7.0` with improvements.
- The rule of 2026-10-08, kept by the decision of 2026-10-25: what depends on his own tests (Altium Designer
  checks, KiCad GUI saves made by him, a run of a real AI agent, his own MCP client) is deferred, the code of
  its change ships, and no evidence label is raised for it.

## Decisions

1. **The id.** c0242: `openspec/README.md` on the base says that new changes start at c0242; no folder,
   archive or fetched branch holds it (checked on 2026-10-29: the archive and the open folders end at c0241).
2. **What is a change of the release.** Every change whose folder was added after the tag `v0.5.0` and whose
   code is on the base: c0195, c0196, c0197 to c0215, c0221, c0223 to c0229, c0232 to c0240 and c0241; and
   c0175, proposed before `0.5.0` ("Not in 0.5.0") and implemented since through those packages and its own
   task 13.1. Not in it: c0216 to c0220 (held on 2026-10-29; c0220's tasks 1.1 and 1.2, the history scan of
   the release and the nightly and `make residue-history`, are tooling on the base and are named there),
   c0222 (a proposal), and the ids c0230 and c0231, which hold no change (aliases of c0239 and c0240).
3. **Rows by folder.** As in v0.5, the column `change` names the folder `cNNNN-<slug>`, and the guard reads
   that folder's task list, open or archived.
4. **Three results.** `ships`, `ships with deferred tasks` or `pending`. A task that waits for the maintainer's
   test, or only on such a task, is deferred to v0.7. Nothing is held: the decision of 2026-10-29 releases what
   is implemented.
5. **Open changes of earlier releases.** c0081 and c0105, and the twelve changes of `0.5.0` that shipped with
   deferred tasks plus c0170 (every task ticked, archived after c0168): each gets an entry, and the guard asks
   for every open task number in it.
6. **The CI evidence.** The base's own commit ran in CI run 40802940021 (pending when written) and its parent
   `1559f1b`, `dev`'s head, passed every job of run 40789845819 (13 jobs: `unit` on five systems, `viewer`,
   `mcp`, `wheel`, `dco`, `kicad-9`, `kicad-10`, both `routing`). The run of the release branch is a
   `TODO(coordinator)` placeholder until it is read; the guard refuses a verdict over it.
7. **The changelog is regrouped, not shortened.** The `[Unreleased]` section already holds one `Added`,
   `Changed` and `Fixed`; it becomes `## [0.6.0] - 2026-10-29` (the day of the decision, as `0.5.0` took the
   day of the maintainer's approval), with one entry that sums up the release opening `Added`. The three
   copies of the c0212 entry that merges left behind become the newest one, whose last sentence named silk
   clipping and test-point placement as left to c0175; they shipped since (c0226, c0229) and the entry says so.
8. **The history row.** The coordinator's public history scan on the base goes into the row `v0.6.0`, private
   gate `not run`. The release workflow scans again over the refs of the GitHub repository; the private gate is
   c0220 task 1.3, the maintainer's (the guard accepts `on` when he records it).
9. **The roadmap.** v0.6 becomes this release; v0.7 gets a row whose scope the maintainer decides; v1.0 keeps
   its row, its section and its table of c0216 to c0220, marked held by the decision of 2026-10-29.

## Risks / Trade-offs

- [A branch of the GitHub repository holds a residue hit that the local refs do not] → c0220 task 1.2 found
  two hits of one example path in `docs/mcp.md` reachable only from the branch `c0195-mcp-server`; the
  release workflow fails at "Residue scan over the history" until that branch is deleted or the hit is decided
  (c0220, open question 2). The record lists it under the maintainer's steps.
- [A task closed later makes a row stale] → the guard accepts a named task that is ticked; the row is updated
  with the verdict.
