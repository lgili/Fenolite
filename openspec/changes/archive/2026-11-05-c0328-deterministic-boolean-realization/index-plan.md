# Conservative candidate proof — task 2.1

Base: clean signed f7413fb8. The geometry subtree has no diff from ea762411.
The inherited prototype/oracle script bytes are unavailable on this host;
their historical receipts remain unchanged. Do not claim to rerun their modes.

## Reviewed algorithm and bounds before implementation

Use closed integer segment bounding boxes and a deterministic sweep. Choose
the axis with fewer interval overlaps, measured by an integer heap sweep on
each axis. Expire an active box only when its high coordinate is strictly less
than the next low coordinate; endpoint contacts must remain candidates. Check
the other axis inclusively. Retain original segment IDs, direction and operand
tags, including duplicate/reversed/zero-length edges. Sort the final ID pairs.
Reject explicit budget exhaustion; never return a truncated successful result.

Conservativeness follows because a common point belongs to both closed boxes:
their projections overlap on each axis. A sweep discards a pair only when one
projection is disjoint. No coordinate rounding, floating arithmetic, geometric
cleanup, source mutation or signed-winding replacement occurs in this filter.

An independent exhaustive Fraction pair oracle must produce the same complete
split graph: exact nodes, directed subedges, operand multiplicities and source
edge provenance. Prove authored contacts, degeneracies, overlaps, cancellations,
rational crossings, integer-domain boundaries, deterministic seeded sets and
bounded subsets of the actual operation-176 operands, each at most 150 edges.
Retain a planted strict-expiry defect and explicit budget-refusal controls.
This is new index evidence, not a rerun of the absent legacy realization code.

Default bounds: at most 10000 input edges, 1000000 active-box comparisons,
250000 retained candidate pairs and 60 seconds per index invocation. Bounded
exhaustive pair enumeration is limited to 150 edges. Failure retains a receipt.

## Proof commands and source confinement

External scratch only, named by `FENOLITE_INDEX_SCRATCH`:

1. `capture_operands.py`: observe the unmodified pinned authored build and
   retain only operation 176's raw integer operands. Verify all source guards,
   the archived ordered/canonical input hashes and the full 188-operation trace.
2. `prove_index.py --bounded`: exhaustive versus indexed exact split graphs,
   plus invariances, negative and budget controls; write counts and hashes.
3. Only after command 2 passes, `prove_index.py --source-census`: count the
   8058-edge source candidates within the declared budgets. This mode performs
   no full Fraction arrangement, face selection, realization or production edit.

Task 2.2 still needs its separately reviewed indexed full-arrangement command
and topology certificates. Task 2.3 still requires root review and a separate
production design. A successful broad-phase census cannot close either gate,
certify a legacy script, select a platform hash or make the Mac byte guard pass.
