# Isolate the native routing scale tests

## Why

The 150-part KiCad 10 shapes acceptance test exhausted its existing 600-second budget twice in
the parallel native corpus shard on the same code that passed the previous complete CI and a
focused local KiCad 10.0.6 run. The full gate needs a runner where this fixture can finish without
concurrent corpus tests.

## What Changes

- Add an audited KiCad 10 partition for the existing routing scale file and execute it serially.
- Keep the original four hash partitions for all other native files and retain every test and limit.

## Capabilities

### Modified Capabilities

- `ci-baseline`: the native suite audits five disjoint whole-file receipts.
