# Residue scan over the git history

Run before each tag with the private token and blob lists configured
(`uv run python tools/residue/scan.py --history`). The scan reads every distinct blob reachable
from any ref; it prints `path:offset:pattern-id` for hits and never the matched text.

| date | tag | commit range | blobs scanned | public patterns | private gate | hits |
|---|---|---|---|---|---|---|
| 2026-09-30 | v0.0.1.dev0 | root .. v0.0.1.dev0 | every blob reachable from any ref | 5 structural + blob list | on (tokens and hashes) | 0 |
