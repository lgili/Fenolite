## Context

- The release process is that of `0.3.0` (c0150): a record under `docs/release/`, a guard under `tests/unit/`, the version in three strings, the changelog cut, the history row of the residue scan, the README, the roadmap, and the maintainer's verdict before the tag. c0150 left the changes it released open and archived only itself, after the verdict.
- v0.4 has no acceptance block in the roadmap. The unit of the record is therefore the change: what it ships, its open tasks, and why each is open.
- The maintainer decided on 2026-10-08 that everything that depends on his own tests (KiCad GUI saves made by him, a run of a real AI agent, Altium Designer checks) is deferred to the next release, and that everything else ships.
- On the base `367cdf8` the changes of v0.4 are 36 folders; 22 have every task ticked, 14 have open tasks (counted with `openspec list` and the task lists, task 0.1).

## Decisions

1. **The id.** c0154: the ids up to c0153 are folders or branches (c0151 `repeat-bus-split` on its own branch, c0152 and c0153 on `v04`).
2. **Three results.** A row says `ships` (no open task), `ships with deferred tasks` (the open tasks wait for the next release; the code ships) or `pending` (an open task is closed by the CI of the release branch, the full suite at the merge, or the first run of the `yardstick` job). A `pending` row may also hold deferred tasks; its entry says which is which. `not met` is not used: v0.4 has no acceptance item to fail.
3. **The guard reads the task lists.** Every unchecked task of a change's `tasks.md` (the open folder, or the archived one once it is archived) must be named in the column `open tasks` of its row, and every number named there must be a task of that list. A task ticked later may stay named, so the record does not have to change when the coordinator closes a task; the result is what changes, and the verdict waits for it.
4. **Placeholders are refused at the verdict.** The runs that do not exist yet are written `TODO(coordinator): CI run <id>`; the guard refuses a verdict other than `pending` while such a placeholder stands or a row is `pending`.
5. **Follow-ups are a section of their own** ("Follow-ups found on 2026-10-08"), each named so that the guard can ask for it: the refuted escape gate of c0110, the outcome that the `kicad-10` job does not print (c0105 1.3), the 9.0.9 census (c0108), the scale re-measure (c0109), the guide line of c0112, the real agent (c0081), the kit revalidation (c0091, c0148), the Altium parts X8, V, G and R2 to R4, the cut prompt of a `.cmd` launcher on Windows, and c0151.
6. **No archive in this change.** As in c0150. Several changes of v0.4 also cannot be archived yet: c0077 waits for c0123 and c0126, c0104 for c0084, and c0110 for c0104, c0107, c0108 and c0109; c0081 cannot be archived before the maintainer's agent run or his decision not to run it. The record gives the order for the archive after the verdict (c0078 before c0079 before c0080, c0100 before c0102 with c0102's delta of "Layer count across rebuilds" written then).
7. **The changelog is regrouped, not shortened.** The 69 entries of Unreleased keep their text; nine that were filed under `Added` but describe a change of behaviour, a probe or a fix move to `Changed` or `Fixed`; one entry that sums up the release opens `Added`, and one development entry closes `Changed`.
8. **The guards of v0.1 to v0.3 stay as they are.** They already accept a later version (the guard of v0.3 tests its changelog section, not the top of the file, at another version).

## Risks / Trade-offs

- [The CI run of the release branch does not exist yet] → the record names the runs of `v04` (37772583226 on `04ef42a`, 37803522539 on `a105cc0`) and leaves placeholders for the push and pull request runs of the release branch and for the first `yardstick` run; the guard refuses a verdict while they stand.
- [A task closed by the coordinator after this change makes a row stale] → the guard accepts a named task that is ticked (decision 3); the row's result is updated with the verdict.
