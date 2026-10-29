## Decisions

Allocation follow-up, 2026-10-28: committed c0208-copper-tidy occupies the current number. Rename only this uncommitted presentation draft and its branch to c0228-public-presentation, keep the worktree location, and preserve prior proof records and allocation aliases. The audit branch tracks this reconciliation in its documentation change.

1. Base the work on the v0.5.0 tag in an isolated worktree. Ongoing repour work stays in its checkout.
2. Show three entry points: review existing files, author in Python, and convert with an explicit loss report. Lead with a viewer experience requiring no KiCad or Altium installation.
3. Use only Fenolite-authored examples and libraries. Screenshots show the actual viewer, with no invented UI or engineering results. The demo is an educational example, not a validated product or production design.
4. Keep release evidence and the roadmap in linked pages. Preserve concise visible caveats for experimental conversion and Altium writes, external routing and KiCad checks, and engineering review.
5. Keep launch materials as drafts until reviewed. Supply exact repository description/topics, a 1280 by 640 social image below 1 MB, bilingual announcement text and release notes. Preserve existing tags and commit history.
6. Documentation uses relative links on GitHub and absolute repository URLs in package-facing README links where required for PyPI. Images have alternative text. Captures have public relative provenance and a reproducible recipe.
7. New validation is limited to documentation, metadata, authored quickstart commands and assets. Full validation belongs to CI; no unmeasured user/adoption or performance claim.

8. The release guard refuses a populated Unreleased at version 0.5.0. Open development at 0.6.0.dev0 (the next release named in the released record), synchronize the alias and pin, and retain the published tag/artifacts. Do not weaken the release guard. Media was captured before this version-only transition on 0.5.0.

9. Full-history quick-gate reconciliation: c0166 commit 5a75bc73 intentionally added two naming flags to the authored hierarchy project. The old c0085 guard does not account for it (shallow CI lacks that baseline). Allow only those exact two additions over the historic file, while keeping every other old-sample byte comparison and current golden proof. No fixture is regenerated.

10. On 2026-10-27 this still-uncommitted draft is reallocated from c0197-public-presentation to c0208-public-presentation to avoid the remote c0197-router-input. The media/design provenance and prior proof results stay unchanged. MCP's optional SDK in 0.5 is not a server command; advertise the server only after its separate branch is integrated and released.
