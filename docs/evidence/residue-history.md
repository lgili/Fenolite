# Residue scan over the git history

Run before each tag (`uv run python tools/residue/scan.py --history`). The public gate, five structural
patterns and the public blob list, always runs. The private gate, a token list and a blob list that live
outside the repository, is optional: the column below says whether it was on. It was not run for v0.1.0, nor for v0.2.0, nor for v0.2.1, nor for v0.2.2. The scan reads every distinct blob reachable
from any ref; it prints `path:offset:pattern-id` for hits and never the matched text.
It was not run for v0.3.0 either, nor for v0.4.0, nor for v0.5.0, nor, unless the maintainer records it
(c0220 task 1.3), for v0.6.0. Since c0220 the release workflow and the nightly also scan the history of the
GitHub repository on the public patterns.

| date | tag | commit range | blobs scanned | public patterns | private gate | hits |
|---|---|---|---|---|---|---|
| 2026-09-30 | v0.0.1.dev0 | root .. v0.0.1.dev0 | every blob reachable from any ref | 5 structural + blob list | on (tokens and hashes) | 0 |
| 2026-10-04 | v0.1.0 | root .. e1769c6 | 3442 blobs reachable from any ref | 5 structural + blob list | not run | 0 |
| 2026-10-06 | v0.2.0 | root .. f613c67 | 5403 blobs reachable from any ref | 5 structural + blob list | not run | 0 |
| 2026-10-07 | v0.2.1 | root .. 2c38a10 | 6825 blobs reachable from any ref | 5 structural + blob list | not run | 0 |
| 2026-10-08 | v0.2.2 | root .. a58604d | 6832 blobs reachable from any ref | 5 structural + blob list | not run | 0 |
| 2026-10-08 | v0.3.0 | root .. c293a56 | 6821 blobs reachable from any ref | 5 structural + blob list | not run | 0 |
| 2026-10-08 | v0.4.0 | root .. 367cdf8 | 8053 blobs reachable from any ref | 5 structural + blob list | not run | 0 |
| 2026-10-15 | v0.5.0 | root .. 9946628 | 9814 blobs reachable from any ref | 5 structural + blob list | not run | 0 |
| 2026-10-29 | v0.6.0 | root .. ab73da4 | 6991 blobs reachable from any ref of the local clone | 5 structural + blob list | not run | 0 |
| 2026-11-06 | v0.7.0 | root .. 890c4e39c | 25559 files of the blobs reachable from any ref of the local clone | 5 structural + blob list | on (separate run: 42 history hits, 0 in the tree; below) | 0 |

v0.7.0, 2026-11-06 (c0469 task 1.3). The public scan at `890c4e39c` over every ref of the local clone:
`residue: 0 hit(s) in 0 file(s); 25559 file(s) scanned; waivers: 23`. A separate run with the private gate
on, over the same refs at `89c5334d9`: 42 hits in the history and 0 in the tree of `cac/lote-29`. 41 hits are
pattern `private-token-9`, one leaked identifier first committed on 2026-11-06; 8 of them are reachable from
`origin/dev`, and all 41 were fixed forward under the maintainer's decision of 2026-11-06, with no history
rewrite. 1 hit is pattern `private-token-3`, a chance byte match inside zlib-compressed PNG data (an `IDAT`
chunk of `tests/visual/refs/altium_sheet.png`) reachable only from `origin/c0245-engineering-viewer`.

Public development proof, 2026-11-01 (c0316, no tag or release):
`make residue-history` passed on `8536797276b61e0ef02ee07dc1d7811b026f34ac`.
The isolated checkout contained all fetched origin refs and tags plus that
candidate, 45 refs; unpublished local work branches were excluded. The sorted
ref manifest SHA-256 was
`1e137a92c1aea206c179f14960d1befc7e4e2364ce6c3f4ea1dfec5dfa33591b`.
Result: 16839 distinct blobs scanned, zero findings, fourteen unchanged waivers,
private gate skipped because no private list was configured. The earlier public
HTTPS-path false positive is corrected; no original historical blob was changed.
This does not close the private scan required on the eventual release commit.
