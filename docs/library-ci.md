# Library review in CI

Install Fenolite with no external CAD tool for checks and HTML sheets. The shipped record gate is the
same check used by a data repository. Never run `library review --accept` in CI.

```yaml
- run: fenolite library check data --sheets review --dry-run --json > library-plan.json
- run: fenolite library check data --sheets review --confirm --json > library-check.json
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: library-review
    path: |
      review/
      library-plan.json
      library-check.json
```

`--confirm` in this workflow plans and writes in one step; locally, inspect the dry-run `plan_id` and
use `--confirm --plan ID` to replay exactly those bytes. Exit 5 means findings at the failure threshold.
An error finding plans no writes, so the JSON report remains the diagnostic artefact on a failing run.
Use `--fail-on warning` for a stricter repository policy.

For an old/new review, check out the base branch into a separate folder with `git worktree add` and add
`--compare ../base/data`. The JSON includes additions, removals, changed field paths and interface
errors. HTML embeds the existing visual overlay. No network or git operation happens inside the checker.

Reviewers download and open `review/index.html`, inspect source facts and geometry, then generate the
base sheet locally for each record they accept. `review_sha256` names the base sheet hash even when
the CI sheet includes a comparison overlay, and `content_sha256` the hash of its shown content, which a
review pins and a viewer-only Fenolite upgrade leaves unchanged (c0415). The record's previous evidence remains effective after an
edit until a person accepts the new content. Fenolite's shipped records remain `INFERRED` with explicit
compatibility waivers, and no CI review promotion occurs.
