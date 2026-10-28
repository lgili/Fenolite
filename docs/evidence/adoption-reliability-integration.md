# Adoption and reliability batch

The maintainer authorized consolidation on dev, complete CI, archival and one squashed dev commit on
2026-10-28. This record describes this batch's implementation proofs; the final archived revision must
also pass the CI checks attached to its own commit before dev advances.

## Scope and allocation

| Change | Delivery | Earlier draft ID |
|---|---|---|
| c0232-snapshot-consistency | Complete-set observed hash checks | c0223; c0210 |
| c0233-viewer-review-reliability | Refinement, shortcuts and narrow review windows | c0224; c0211 |
| c0234-catalog-visual-browser | Installed offline catalog drawings | c0225; c0212 |
| c0235-viewer-navigation-consistency | Ordered navigation, cache and polling | c0226; c0213 |
| c0236-documentation-reconciliation | Current docs and integration records | c0227; c0215 |
| c0237-public-presentation | README, tutorial, public media and launch drafts | c0228; c0216 |
| c0238-write-recovery | Truthful incomplete rollback and preserved originals | c0229; c0217 |
| c0239-project-review-status | Scoped status and finding review | c0230; c0218 |
| c0240-catalog-selection | Paired previews, geometry filters and explicit pad maps | c0231; c0219 |

The final allocation preserves dev's c0215–c0221, remote c0222-net-roles and other agents' layout work.
The final fetch on 2026-10-29 exposed other agents' c0223–c0229 on dev-c0213-c0216 and dev-c0225-c0227.
Only this batch's identities moved to c0232–c0240, with prior aliases/proofs retained. Current source
comment IDs changed with them; implementation behavior and the already-tested comparisons did not.
Checkpoint bc0b422f preserves the audit and f374e140 the presentation; both carry the maintainer's
Signed-off-by trailer. Only their deltas were applied to dev 04e1caa1, preserving the current MCP,
Altium pour and release-automation implementations. No private project, CAD fixture, visual reference,
core dependency or external repository setting was added or changed.

## Combined local proof — 2026-10-29

- Focused integration: 152 passed.
- `make check-fast`, with the declared dev and geo extras: 14406 passed, 37 skipped, 278.85 seconds.
  Lint, generated guides, format, full src types and residue scan passed.
- Chromium interaction/navigation/catalog/review: 60 passed, 131.94 seconds.
- Strict living-spec validation: 70 passed, 0 failed. The nine change deltas also validate strictly.
- Diff and staged-path checks passed. No local full-suite pass is claimed.

The first quick attempt stopped in the kit generator before tests because geo was missing from the
environment; installing the already-declared extra resolved it. The presentation and audit retain
their earlier focused/local proof records under their allocation aliases.

The first implementation CI's Linux viewer job passed the canonical screenshot comparisons. On this macOS host the old page
also differs from the committed references because of platform fonts/controls; all eight new-vs-old
same-host comparisons passed the existing tolerance. No reference or tolerance was changed to conceal
that difference.

## Complete CI

The [first implementation run](https://github.com/lgili/Fenolite/actions/runs/40723421798) tested
21cafbd0cef59481cfe05b7a5457ab1f1f3b64b7 and failed; it is not an approval. Unit jobs identified two
existing c0215 authored kit scripts missing from `tests/data/MANIFEST.toml`, and Windows additionally
identified locale-dependent text decoding in the presentation test. Registering the two scripts
preserves their bytes and the strict provenance guard. Explicit UTF-8 preserves the bilingual
documents and assertions. Focused checks passed: 48 manifest tests and 14 presentation tests, the
latter with implicit text decoding rejected. The repeated `make check-fast` passed 14406 with 37 skipped
in 425.83 seconds; lint, generated guides, format, types and residue scan passed.

Implementation approval: [run 40743806475](https://github.com/lgili/Fenolite/actions/runs/40743806475)
completed successfully on 8c2fa27048cf36543b93ee01c873aec0673f5d7d with all 13 jobs passed, under the
c0223–c0231 identities. KiCad 10 and corpus: 3461 passed, 118 skipped, 3 expected failures, 5642.24 seconds.
Windows, macOS, all three Linux/Python variants, both routers, KiCad 9, the official visual suite, MCP,
isolated wheel and sign-off checks passed. The nine implementation CI tasks can close; the final
renamed/archived revision must pass its own complete CI before dev advances. GitHub settings and launch
posts remain separate from this code integration.

The [second run](https://github.com/lgili/Fenolite/actions/runs/40728671336) tested
bf4b8a3ddd48ee9777e8810c126a3a44ea58b021. Its five unit jobs, viewer, wheel, MCP, DCO, KiCad 9 and both
routers passed. The KiCad 10 job exposed further historical-test failures; no complete approval is
claimed. The [parent dev run](https://github.com/lgili/Fenolite/actions/runs/40711152654) independently
reported the same triangle/census failures before this batch: the historical measurements expected
unpoured inputs but accidentally used c0215's new computed default.

The authored triangle reproduced four failures locally, then all six sample/probe cases passed with
explicit outline mode. The full conversion-census file passed 50 tests, skipping its four declared
heavy cases for CI, in 54.04 seconds. Counts, tolerances, comparisons and sample bytes were unchanged.
The model-write helper now exposes the backend's existing pour mode with its existing default;
23 mode/build/conversion tests passed, including real output for default, computed and outline. The
evidence pages name the historical outline scope and make no new computed-equivalence claim. The
quick gate passed 14409 with 37 skipped in 206.20 seconds (8 workers, worksteal); all 48 agent-page checks
also passed, along with strict OpenSpec, diff checks, lint, format, generated guides, src types and
residue. The replacement implementation CI subsequently passed as recorded above. No local full-suite
pass is claimed.

## Archived revision gate

All nine final identities were archived through `openspec archive --yes`, in dependency order, after
implementation approval. Their folders use OpenSpec's UTC prefix `2026-10-28-c0232-` through
`2026-10-28-c0240-`; local proof records use 2026-10-29. All implementation tasks are checked. The 24
requirement deltas update ten living capabilities, including the new public-presentation and
documentation-consistency specs, whose purposes are filled in. Other agents' changes and the manual
Altium K6 acceptance remain open.

Final local proof after archival: `make check-fast` passed 14409 with 37 skipped in 274.52 seconds;
lint, generated guides, format, src types and residue passed. Strict living-spec validation passed
all 72 specs; diff checks passed after normalizing archive-generated trailing blank lines. All nine
archived task lists are complete. The post-approval ID changes were checked as Python docstrings or
JavaScript comments only; runtime behavior was preserved.

The CI check attached to the final archived commit is the final publication gate: all 13 jobs must
succeed on that exact revision before the single-commit squash advances dev. Its immutable run records
the final SHA; the publication result reports that SHA without another source edit after approval.
The main branch, repository settings, release publication and launch posts are outside this integration.
