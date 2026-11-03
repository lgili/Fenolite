# Cyclic orientation proof

The living Angle contract uses exact circular distance modulo360000000
microdegrees. The bug was L7 feeding typed Text/FootprintField rotation integers
into the generic length comparator. Only those two call sites now pass an
explicit orientation path. Generic fields, L6, sweep/ranges, S and model/codec
presence remain unchanged. No writer or tolerance/mask changes are involved.

Authored pre-code tests failed for0/360 and-90/270, and exposed that a large
length tolerance could previously hide true rotations. After the focused metric
fix,25 controls pass, including45.000001/405.000001 orientations,90/0 and180/0
negatives,1microdegree exact failure, angular tolerance only and None/bool/zero
separation. Input canonical JSON strings remain distinct and unchanged.

The exact existing Tiny public corpus input hashes were verified. One fresh
import/build was compared using the prior generic integer metric and then the
explicit cyclic metric. Comparing differences as MULTISETS is necessary because
some locations repeat:29 removed rows occupy22 distinct locators. All29 are
text-field.rotation -90000000→270000000, with zero circular distance. No row is
added. Every other row remains unchanged, including multiplicity:328field-pose
rows (c0345),5graphic-missing rows and the311/14602 Edge.Cuts pixel finding.
These remain real failures, outside this scope, not passing/accepted outcomes.

The broader focused command executed235cases:231passed; four existing c0334
bom-only table/CLI teaching guards failed and were delegated to the native
owner. This is not reported as a green combined focus. All25 new orientation
controls and runtime Ruff/Pyright pass. Final root fast/plans/CI remain required.
