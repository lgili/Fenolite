# Current-source preparation proof

Source: 78c086be, current CAC model0/CLI0. Historical bf6532a4 supplies only selectively adapted
Fenolite-owned implementation/tests; its review/freeze receipts and entity classes are not imported.

The initial surface tests fail collection because cli.surface is absent. After the focused port,
52 authored surface/deprecation/dual-contract tests pass. The active contract remains v0; v1 is
exercised only through test monkeypatches and prepared envelope/error schemas. Existing output,
model validation, source-import exceptions and evidence handling remain in place.

All twenty pre-existing schema files are byte-identical to source78c086be after generation. Only the
new envelope/error v1 files are generated. This preservation receipt is preparatory, not the final
model0 freeze. `tools/gen_cli_surface.py --check` and `tools/gen_schemas.py --check` pass.
`openspec validate c0216-contract-v1 --strict` passes. Targeted Pyright reports zero errors. Hypothesis-register/release-record proofs pass52 cases;
the private staged residue gate reports zero hits across24 staged files.

The larger focused CLI/guide/consistency run initially has754 passes,42 existing parameterized skips
and7 failures: three capabilities tests retain their old exact key lists, and four kit examples cannot
run without the declared geo extra. The three lists are extended explicitly for contract/deprecated
while retaining exact order and checking v0/empty-deprecation values. The declared geo extra is installed;
no product behavior is changed to disguise the missing dependency. The seven failed cases pass in the targeted follow-up:15 passed. Ruff check/format and agent-guide generation also pass.

## Human review is pending

The external current-source report is generated without --keep-all. It contains57 visible commands,
713 option rows including aliases/global flags,185 public Python export/member rows, and hidden _echo.
Twenty option rows and104 issue codes have no literal test mention; these are static review leads,
not execution coverage claims. Four guide and six contract-document mention gaps remain explicit;
three gap names are argparse selector destinations, not option spellings.

Report SHA-256:0649a3c404b9e20e36c143323ab3db720992ab347c1864eb1a314facdf3332e4.
All decisions are pending. No historical review approval is reused and no maintainer decision is made
by the implementation agent. Task1.4, application of review decisions, final source refresh, check-fast
and exact-commit full CI remain open. Active CLI1/package1.0 are not enabled by this preparation.
