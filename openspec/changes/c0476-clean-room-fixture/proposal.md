# Proposal: clean-room harness fixture and documentation

## Problem
Recent change documents and a harness regression fixture contain private-project identifiers and
observations. The repository's clean-room policy prohibits private project data and examples.

## Change
Remove private references and project-specific observations from the change documents. Replace the
harness test's sample records with independently authored data while retaining the same behavioral
checks. Keep format facts grounded in the existing public-source documentation.

## Proof
Run the affected test, the documentation checks, and the repository residue scan; separately inspect
the tracked tree for the identified private identifiers without adding those identifiers to the tree.
Prior Git history is not rewritten by this change.
