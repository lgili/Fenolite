## Context

`ci.yml` starts with `on: push:` and `pull_request:` and no filter, with `concurrency: ci-${{ github.ref }}`,
so a tag and a branch each get their own run. The release record of v0.5 names the jobs of a run on the
release branch's head; that does not change.

## Decisions

1. **`push.branches: ["**", "!backup/**"]`.** `**` matches every branch name, slashes included; the negated
   pattern after it removes the backups. GitHub runs a push workflow only for the kinds of ref that its
   filters name, so a filter on branches alone leaves tags out; no `tags-ignore` is needed (GitHub refuses
   `branches` together with `branches-ignore`, not `branches` alone).
2. **Pull requests unchanged.** A pull request from any branch, a backup included, still runs every job: a pull
   request is a merge gate.
3. **A textual test**, as the other checks of `ci.yml` (the dev extra has no YAML parser): the `on` block must
   be exactly the filter above and `pull_request:`.

## Risks

- A maintainer who wants CI on a backup branch opens a pull request from it, or renames the branch.
