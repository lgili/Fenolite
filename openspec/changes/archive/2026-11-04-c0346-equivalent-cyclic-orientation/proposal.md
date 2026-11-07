# Why
The living Angle contract compares cyclic orientation modulo360deg in integer
microdegrees. Level7 currently treats Text.rotation and FootprintField.rotation
as lengths, so exact equal orientations -90deg and270deg are incorrectly unequal.
Tiny's remaining29 such differences are representational, unlike real90vs0 edits.

# What Changes
Explicitly mark only these two typed L7 orientation paths for the existing
norm.angles_equal metric. Generic fields, level6, sweeps/ranges and canonical
model presence stay unchanged. No tolerance, waiver, writer normalization or
comparison mask. Preserve unrelated Tiny Edge.Cuts and pixel findings.
