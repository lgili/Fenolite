# Design

## Failure and rejected inference

The public Tiny replay has eleven root edges and nine footprint edges. The root alone does not close, so the importer calls edge_outline over both. Its twenty-edge outline chains nearby endpoints through join_ends(CHAIN_GAP). Four footprint edges still match the writer's raw keys; five no longer do and become extra root graphics. No footprint graphics were lost.

A cluster-key experiment recovers the expected eleven root edges, but is insufficient evidence of ownership. An authored root line and an intentionally distinct parallel footprint line one nanometre away have a unique cluster-key match too. Silently removing that root line is wrong. The experiment and counterexample are preserved externally. No proximity-based suppression will be implemented.

## Reviewed explicit representation

Use existing typed Board.graphics to express the exact original root lines/arcs, while Board.outline continues to express the logical closed outline. No model field, extension key, provenance schema, dependency, or entity is added. The root graphic's presence explicitly says it is owned by the board, irrespective of nearby footprint geometry.

Allow design.line and design.arc on Edge.Cuts; other drawing kinds retain their layer restrictions. Writer acceptance of outline plus explicit root edges is bounded: remove the logical outline from a copy, reconstruct a complete outline from the explicit root edges plus the existing footprint edges with the established deterministic edge_outline pipeline, then compare its complete edge-text multiset exactly with the logical outline. Open, branching, ambiguous, incomplete, or inconsistent reconstructions retain outline-conflict refusal. Exact CHAIN_GAP and collapsed/transitive cases are controlled explicitly. There is no new tolerance.

On a valid complete reconstruction emit the explicit root graphics, retain existing footprint graphics, and emit no synthetic outline graphics. Arc midpoint integers, widths, footprint local geometry, placements, and graphics multiplicity remain unchanged. A distinct parallel root is either preserved as an explicit root or causes honest inconsistency refusal, never silently erased.

The importer selects this explicit representation only when its logical outline cannot be represented by the exact source root and footprint edge multiset using the existing exact suppression. The original exact-join path, including the existing notched fixture, keeps its bytes and plans. Only representable positive-width unfilled root lines/arcs are eligible; unsupported cases remain visible and cannot be claimed lossless. Reuse the existing drawing emitter and source-relative coordinate conversion.

## Proof

Authored controls run red before runtime changes for both KiCad targets. They include nanometre joined lines/arcs, different arc mids, parallel one-nanometre lines, duplicate/multiple edges, transitive clusters, exact ten-micrometre gaps, collapsed pieces, and inconsistent outlines. Successful cases must preserve exact explicit root and footprint geometry; negative cases may refuse but never silently erase geometry.

Public replay remains external. Fresh verified import/build must have exactly eleven original root edges and nine original footprint edges, eliminate exactly the five duplicate graphics, and preserve unrelated findings. Root owns the combined 75-plan defaults check, check-fast, and full CI on the exact integrated commit.
