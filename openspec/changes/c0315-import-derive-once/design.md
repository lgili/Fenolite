## Context

Base `51c877b8`, 2026-11-01. Read AGENTS.md and the existing derive/vendor code.
The current signature depends on the instance definition, source name, library
and target, which do not change during its candidate-variant comparisons.

## Decisions

Decided 2026-11-01: calculate the signature before visiting existing variants and
reuse it when appending. Normalizing a newly assigned variant back to its source
name yields the same signature; explicit byte/variant tests must prove that.

Decided 2026-11-01: keep current parsing and public signatures. The largest observed
source boards have only one nickname, so repeated whole-board parsing alone does
not explain their cost. Any parse-sharing API or broader performance work needs a
separate measured justification.

## Evidence

This is authored algorithmic work. Existing format sources and evidence apply;
there is no new external format claim. The stress case uses wholly invented pads.
Actual whole-corpus conversion and its timing remain separate CI proofs.
