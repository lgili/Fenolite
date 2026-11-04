## ADDED Requirements

### Requirement: Model-only pad geometry of non-plated holes
The model-only pad geometry (`checks.padpath.model_pads`) SHALL give an `np_thru_hole` pad no copper
entries, as the KiCad and Altium pad frames do, and SHALL leave out any copper entry that a copper record
cannot hold, such as a disc of diameter 0. The pad SHALL stay in the result with its position, layers and
net. No check SHALL fail with an internal error because a pad has no copper.

#### Scenario: A non-plated hole without copper
- **WHEN** a board holds an `np_thru_hole` pad of size 0 on `*.Cu` and `fenolite check` runs
- **THEN** the check completes the selected steps without `FEN-1001`
- **AND** `model_pads` lists the pad with no copper entries

#### Scenario: A plated pad of size 0
- **WHEN** a plated pad has a size of 0
- **THEN** `model_pads` lists the pad without the refused copper entry instead of raising
