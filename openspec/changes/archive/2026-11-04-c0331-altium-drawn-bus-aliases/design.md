## Decision

Use the source resolver's existing alias expansion and precedence (first global
declaration, then the current sheet overrides it). Only identifiers anchored on
a bus without a wire at that point are candidates; group-looking scalar wire
labels remain literal. Labels, hierarchical ports and sheet entries use the
same conversion. Existing vector names retain their original direction/bytes.

A converted identifier must expand to unique names with one nonempty common
prefix and canonical decimal suffixes covering a contiguous range. The native
vector's expanded member set must exactly equal the source set. No scalar
member, geometry, code partition or source file changes. Heterogeneous, gapped,
empty and padded member groups refuse with FormatError and a source locator;
allow-lossy cannot authorize inventing or dropping connectivity. A native signal
harness implementation is separate work.

## Proof and limits

Reproduce the unchanged writer's invalid full label and connected two-sheet
alias control. Prove both output forms, parent entry/child port, alias scope,
unchanged scalar/vector controls and unrepresentable-group refusals. Compile
fresh authored controls with Altium 22.2.1 and export all physical pins and
native net-object memberships independently. Keep full-fixture source ERC
findings and raw native names visible. Save/reopen operates only on authored
clones; a successful return without an actual file is not a save proof.

The six original cases, byte hashes, raw messages and native exports are
retained separately from corrected outputs. H-A-DRAWN-WRITE remains INFERRED;
the original kit's remaining ERC, name, visual and save requirements are not
closed by a targeted bus proof. No Mac board-40 golden or CI gate changes.

After actual native measurements, keep the dated unavailable-application kit
request as historical context. The current metadata regression must instead
require Altium 22.2.1, its measured report and still-pending acceptance; its
literal unavailable-reason assertion reproduces a failure after the truthful
status update. Preserve the no-connectivity-message criterion, inferred grade,
concrete kit steps and explicit negative-control refusal.
