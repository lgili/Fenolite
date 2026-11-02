## 0. Entry

- [x] 0.1 Inspect the reported historical blob and record the bounded decision.
  Proof: `npx -y @fission-ai/openspec validate c0316-residue-web-paths --strict`.
  Passed 2026-11-01: the original public blob was inspected; decisions recorded;
  strict validation valid without warnings.

## 1. Scanner correction

- [x] 1.1 Add authored URL/component, encoding, archive and private-token
  regressions, observe the pre-fix failure, then scope the URL-path distinction.
  Proof: `uv run pytest tests/residue/test_scan.py -q`.
  Passed 2026-11-01: 44 cases, including HTTP/HTTPS, ports, IPv6, three encodings,
  malformed authorities, file URIs, query/fragment paths, private tokens, known
  blobs and archived historical labels. Before the fix, twelve cases failed.

## 2. Validation

- [x] 2.1 Add the Unreleased entry and run static, type, residue and strict checks.
  Proof: `uv run ruff check .`; `uv run ruff format --check .`;
  `uv run pyright tools/residue/scan.py`; `uv run pytest tests/residue -q`;
  `uv run python tools/residue/scan.py`;
  `npx -y @fission-ai/openspec validate c0316-residue-web-paths --strict`.
  Passed 2026-11-01: lint/format clean, scanner types zero errors/warnings,
  residue tests 69 passed with five missing-corpus skips, tree scan zero hits
  across 5634 files with fourteen unchanged waivers; private gate skipped.
  Strict validation valid without warnings. A planted revision string was
  assembled at runtime after the initial whole-tree proof correctly caught it.
- [x] 2.2 Confirm the public history scan on its recorded ref scope.
  Proof: `make residue-history` and its recorded commit, ref scope and summary.
  Passed 2026-11-01 on `8536797276b61e0ef02ee07dc1d7811b026f34ac` in an
  isolated checkout containing all fetched origin refs/tags plus that candidate:
  45 refs, sorted-ref manifest SHA-256
  `1e137a92c1aea206c179f14960d1befc7e4e2364ce6c3f4ea1dfec5dfa33591b`.
  `residue: 0 hit(s) in 0 file(s); 16839 file(s) scanned; waivers: 14; private gate: skipped (no private list configured)`.
  Unpublished local work branches are outside that scope. This is a public
  development proof, not the future private release scan of c0220 task 1.3.
- [ ] 2.3 Confirm the serialized larger-batch fast gate and exact-head required CI.
  Proof: `make check-fast` and required jobs green on the published batch commit.
