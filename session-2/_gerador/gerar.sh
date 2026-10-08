#!/usr/bin/env bash
# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Rebuild every Altium file of the session-2 pack from a Fenolite checkout at commit 695574b.
# Run from the root of that checkout:  bash <pack>/session-2/_gerador/gerar.sh <pack>/session-2
# The folder given must lie outside the checkout. Every command takes a fixed seed and timestamp where it
# has them, so a second run writes the same bytes.
set -euo pipefail

OUT=$(cd "$1" && pwd)
GEN="$OUT/_gerador"
SEED=(--seed 0 --timestamp 2026-01-01T00:00:00Z)

# Part K: the verification kit (its own defaults are seed 0 and 2026-01-01T00:00:00Z).
rm -rf "$OUT/K-kit"
uv run fenolite kit build --out "$OUT/K-kit" "${SEED[@]}" --confirm --json > /dev/null

# Part O: the output job with the Gerber settings (change c0138).
rm -rf "$OUT/O-outjob/blink_routed" "$OUT/O-outjob/blink_routed_p6" "$OUT/O-outjob/board6"
uv run fenolite build examples/blink_routed/design.py --target altium \
  --out "$OUT/O-outjob/blink_routed" "${SEED[@]}" --confirm --json > /dev/null
uv run fenolite build examples/blink_routed/design.py --target altium \
  --altium-outjob-preset "$OUT/O-outjob/precision6.toml" \
  --out "$OUT/O-outjob/blink_routed_p6" "${SEED[@]}" --confirm --json > /dev/null
uv run python "$GEN/vias/construir.py" examples/kit/board6/design.py "$OUT/O-outjob/board6" > /dev/null

# Part X8: component bodies (change c0121), the sets saved/ and short/.
rm -rf "$OUT/X8-bodies"
FENOLITE_ALTIUM_BODY2="$OUT/X8-bodies" uv run pytest tests/unit/lens/test_altium_bodies.py -k golden -q -p no:cacheprovider > /dev/null
rm -f "$OUT/X8-bodies/README.md"

# Part R: the two-channel Repeat project (changes c0083 and c0146); equal to tests/data/altium/channels/two/.
rm -rf "$OUT/R-repeated-sheet"
mkdir -p "$OUT/R-repeated-sheet"
uv run python -c "
import sys; from pathlib import Path
sys.path.insert(0, 'tests')
import _altium_channels as two
for name, data in two.files().items():
    (Path(sys.argv[1]) / name).write_bytes(data)
" "$OUT/R-repeated-sheet"

# Part S: the five symbols of change c0134.
rm -rf "$OUT/S-simbolos"
uv run fenolite build "$GEN/simbolos/simbolos.py" --target altium \
  --out "$OUT/S-simbolos" "${SEED[@]}" --confirm --json > /dev/null

# Part V: the vias for "Remove Unused Pad Shapes" (change c0132).
rm -rf "$OUT/V-vias"
uv run python "$GEN/vias/construir.py" "$GEN/vias/vias.py" "$OUT/V-vias" > /dev/null

# The build records (.fenolite/) are not opened in Altium and name the folder of the build: left out.
find "$OUT" -type d -name .fenolite -prune -exec rm -rf {} +
find "$OUT" -type d -name __pycache__ -prune -exec rm -rf {} +
