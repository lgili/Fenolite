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
| 2026-10-29 | v0.6.0 (release run 40894254054) | root .. 7b9cc1e | 12 586 blobs of every ref the release workflow fetched | 5 structural + blob list | not run | 0 |
