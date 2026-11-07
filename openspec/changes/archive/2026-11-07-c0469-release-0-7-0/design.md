## Context

- The release process is that of `0.6.0` (c0242): a record under `docs/release/`, a guard under
  `tests/unit/`, the version in three strings, the changelog cut, the history row of the residue scan, the
  README, the roadmap, and the maintainer's verdict before the tag. The publication is a pushed tag
  `vX.Y.Z` (c0221, `docs/releasing.md`); `release.yml` checks the versions and the changelog, scans the
  history, builds both packages, publishes them and creates the GitHub Release.
- The maintainer's decision of 2026-11-06: release `0.7.0` once the CI of lote-29 passes, with what `dev`
  and lote-29 implemented since `0.6.0`; c0468 (library generator families) goes to the next lote.
- The rule of 2026-10-08, kept on 2026-10-25 and 2026-10-29: what depends on his own tests (Altium Designer
  runs, KiCad GUI saves made by him, a run of a real AI agent, his own MCP client) is deferred, the code of
  its change ships, and no evidence label is raised for it.

## Decisions

1. **The id.** c0469, given by the coordinator on 2026-11-06; new changes start at c0470.
2. **What is a change of the release.** Every change whose folder was added after the tag `v0.6.0` and whose
   code is on the base, and every change of an earlier release with tasks closed since `0.6.0` (its row says
   what closed since). c0175, open before `0.6.0`, keeps its row while its task 10.4 waits.
3. **Rows by folder.** As in v0.6, the column `change` names the folder `cNNNN-<slug>`, and the guard reads
   that folder's task list, open or archived.
4. **Three results.** `ships`, `ships with deferred tasks` or `pending`. The long-term changes c0175, c0384,
   c0389 and c0417 ship with deferred tasks: their open tasks wait for the maintainer, Altium Designer or a
   later batch, and their entry says which. The changes of lote-29 still open when the record is written are
   `pending`; the coordinator turns each row as it closes, and the guard refuses a verdict over a pending row.
5. **Left out.** A change that shipped no code (docs, evidence or census pins only) gets no row; it is named
   under `## Left out of the rows` with its reason. The guard refuses a row for it and asks for the entry.
6. **Not in 0.7.0.** c0468, the library generator families, is the next lote's. The v1.0 tag stays held:
   c0216 to c0220 ship their machinery in `0.7.0`, and the contract stays `v0` until `1.0.0`.
7. **The CI evidence.** The run of the release branch is a `TODO(coordinator)` placeholder until it is read;
   the guard refuses a verdict over it.
8. **The changelog and the version are the last task.** The `[Unreleased]` section keeps growing while
   lote-29 closes; the coordinator cuts it into `## [0.7.0] - <date>` with one `Added`, `Changed` and
   `Fixed`, sets `0.7.0` in the package, its alias and the alias pin, and the README status names 0.7, in one
   last commit. Until then the guard checks the version, the changelog and the README only at `0.7.0`.
9. **The history row.** The history scan with the public patterns and the private lists of the maintainer's
   checkout (`FENOLITE_RESIDUE_TOKENS_FILE`, `FENOLITE_RESIDUE_BLOBS_FILE`) goes into the row `v0.7.0`,
   private gate `on`. The release workflow scans again over the refs of the GitHub repository.
10. **The roadmap.** The milestone row of v0.7 names this change and the record; the rows of v0.6 and v1.0
    keep what the guard of v0.6 asks.

## Risks / Trade-offs

- [A change closes after the record is written] → its row stays `pending` until the coordinator updates it;
  the guard accepts a named task that is ticked, and refuses a verdict while a row is pending.
- [Two hundred rows are long] → the rows are short and the guard holds each one to its folder's task list,
  so a stale row fails a test instead of passing unnoticed.
