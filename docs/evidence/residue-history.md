# Residue scan over the git history

Run before each tag (`uv run python tools/residue/scan.py --history`). The public gate, five structural
patterns and the public blob list, always runs. The private gate, a token list and a blob list that live
outside the repository, is optional: the column below says whether it was on. It was not run for v0.1.0. The scan reads every distinct blob reachable
from any ref; it prints `path:offset:pattern-id` for hits and never the matched text.

| date | tag | commit range | blobs scanned | public patterns | private gate | hits |
|---|---|---|---|---|---|---|
| 2026-09-30 | v0.0.1.dev0 | root .. v0.0.1.dev0 | every blob reachable from any ref | 5 structural + blob list | on (tokens and hashes) | 0 |
| 2026-10-04 | v0.1.0 | root .. e1769c6 | 3442 blobs reachable from any ref | 5 structural + blob list | not run | 0 |
