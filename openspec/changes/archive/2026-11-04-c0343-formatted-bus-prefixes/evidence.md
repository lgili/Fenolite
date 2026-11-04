# Source-bound focused proof, 2026-11-02

Base is clean c0334/power source `cee88f0d`, with the independent test-only oracle-major binding
`1576a2ae`. Every test invocation explicitly uses the isolated `src:tests` import path. No vendor
parser/grammar, public CAD fixture or unreviewed baseline is copied into the repository.

## Independent rule before implementation

Original Mini native inputs are constructed after building the valid unchanged baseline, independent
of the resolver under test. Actual 10.0.6 exports for subscript, superscript, overbar, sequential and
nested formatting prefixes all preserve the literal prefix and four expanded member names. All
40 pins are present: native has 36 groups, old own resolution has 40 (eight own groups versus four
native groups). The pre-fix regression group records 11 failures and 12 controls passing; log SHA-256
`d1b51af760e3e794b270f30ab08fd433d952b7a055613f1fe8077159ea9ae7a4`.

The malformed negative found a second real delimiter failure: text resembling an unterminated group
but ending in a vector range fell through the old vector regex. Native retains 40 singleton groups,
while own resolution invented four joins (36 groups), despite all 40 pins being listed. Independent
native proof preceded the bounded vector-prefix validation. The existing valid vector cardinality
and member mapping are unchanged.

The authored scanner recognizes only balanced literal formatting spans, including measured nested
formatting, before the true group delimiter. It never strips text. The existing group-member parser,
alias depth and native/generic scoped identity rules remain. Unsupported nested groups, malformed
braces and trailing invalid content remain unrecognized. Formatting alone declares no members;
unequal scalar spellings do not gain visual aliases. No variables/quoted-space expansion is added.

## Native and regression proof

- Complete native prefix suite: **17 passed on actual 9.0.9** and **17 on actual 10.0.6**, including
  literal identity, malformed-vector and formatting-only negatives. Every case retains all 40 pins
  and all groups. Final log SHA-256:9 `cc5a00b4ee28ddfc56b875f16875ee1cea89d89d3d29cb9c7e781d87ca5cde01`,10 `9e7e02015fd8278c76be4cafc0a8e4ac498a9ba8070e13c992117843c2a3e05f`.
- Existing unit/native bus and connectivity neighbors plus initial new controls: **103 passed**;
  log SHA-256 `549b7b6dd93e78b8a0fd03861d75dbae270396bf1a59ab3728577032bfbd4a1d`. Groups overlap and
  are not summed into a unique-test count. Subsequent malformed/format-only controls are independently
  source-bound; none is a fixture acceptance or expected-count relaxation.
- All **15 affected public owner017 context rows** pass actual 10.0.6 census, with SHA-checked
  inputs: every row retains 4712/4712 pins, 1355/1355 electrical groups, zero missing/extra/differing
  groups. Original-native and lowered-native names/partitions also agree completely. The own resolver
  still reports four naming differences among 715 named nets and 1223 bus-member warnings; these
  remain visible and are not a full-naming-fidelity claim. Log SHA-256
  `653fcacc77fac32d99d1b894c1bd893e0d8c42a58a9993a3a57de1f60f6fd95d`.
- VME regression also passes with all 6811 pins/1800 groups intact; log SHA-256
  `b17baf25ab7c24c9d8a811a28b5f0bf6d05f5f7e2f5f2ca4ee5a41887e295903`.

No standalone-unowned port diagnostic or published read floor changed. The earlier immutable literal
130-row census and separate combined-source strict24 diagnostic remain their original measurements,
never relabeled as fixed-source gates. No model/DSL argument/schema/dependency/evidence level changes.
Ruff and focused source typing pass; the guide teaches literal spelling with a tested line. Required
combined fast and exact-head matrix CI remain task 2.2 and must precede archival.
