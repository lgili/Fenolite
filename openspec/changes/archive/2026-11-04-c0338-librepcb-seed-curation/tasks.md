## 0. Scope
- [x] 0.1 Validate the explicit curation contract before mutation; preserve raw failed candidates.
## 1. External candidate
- [x] 1.1 Implement and replay deterministic external recipe; prove only two pin lengths differ semantically and every footprint/device record stays byte-identical.
- [x] 1.2 Preserve original source/UUID/hash and modification notice; validate provenance and hashes, no arbitrary schema keys or invented review.
- [x] 1.3 Prove native KiCad before/after partition equality and complete library check exit0/zero ERROR with four preferred100mil WARN visible; generate exact-plan review sheets with explicit change preview.
## 2. Human and release gates
- [x] 2.1 Obtain actual per-item human review of this candidate with sheet digests; do not infer acceptance from generation.
- [x] 2.2 Root/library owner integrates reviewed candidates and runs exact-source library/core CI before c0266/c0279 closure. No publication or cleanup before preserving evidence.

Proof: four-item external recipe repeated with byte-identical receipt/output SHA; only two symbol lengths differ32um, all footprint/device record bytes preserved. Provenance validator accepts existing modification_notice/NOTICE and output hashes. Complete check exit0, zero ERROR, four WARN visible; exact-plan sheets confirmed and hashes verified. KiCad10.0.6 native three-net partitions equal before/after. The artifact does not infer human approval or CI completion. Maintainer explicitly retained2.032mm and visible warnings, rather than increasing to2.54mm to suppress them.

Actual human approval (2026-11-02): Luiz Carlos Gili stated “Revisei e aprovo os quatro itens, considerando os avisos”, for the four exact sheet digests in approval.md, including the32um artwork delta and four visible preferred100mil warnings. Three CLI acceptance confirmations exist; device acceptance materialization is blocked only by the direct-device dependency discovery bug owned by root, not by missing human approval. Release/audit/CI remain pending under2.2.

Current-renderer follow-up2026-11-03: explicit NEW user approval “Aprovo as quatro fichas atualizadas, com os mesmos avisos” binds the four current-renderer-v1 hashes, not an inferred extension of the older decision. All four actual CLI accept dry/confirm receipts match exact reviewed record and sheet hashes; no missing device receipt remains. Complete portable receipt is `docs/evidence/current-renderer-human-approval-20261103.json`, identical to library6a6c14a. Four warnings/geometry/dependencies remain unchanged. Task2.2 stays open for integration and exact-source CI/audit/release.


Local authoritative integration2026-11-03: maintainer explicitly approved
"Aprovo os quatro itens com a origem corrigida" for four new exact D-0005 sheets.
Preserved occupied source IDs D-0001/D-0004 and their complete registry mapping.
Four CLI dry-run/plan/confirm acceptances materialized the new approval. Four
items/23payload files now integrate locally in fenolite-library with three
declared native outputs; no old payload replaced. New item audits4xexit0;
record check exit0/zero errors/four unchanged pin-grid warnings; existing native
regeneration body exit0;33focused review/check and13licence tests pass. Root
library audit retains exactly21old errors (exit5). Receipts in library
docs/librepcb-source-integration-{approval,proof}-20261103.json. Composite2.2
remains unchecked for exact-source CI and c0266/c0279 audit/release gates.
No public pin, push, CI or release claim.

Root review committed the29manifest-bound files locally as library
23deaee0085f7fe8f358876a28f6cd76a8ab385b with maintainer DCO. Every file
hash/size and unchanged prior source-register bytes were checked before
staging; private staged residue0hits/29files/private gateON and whitespace
validation passed. Authoritative worktree is clean. No publication occurred.

Closed 2026-11-04: `make check-fast` passed on the batch (22620 passed, 51 skipped); every
required job of CI 41853235387 passed on the exact commit 0bce63e2 (unit on Linux 3.11/3.12/3.13, macOS
after a rerun of a runner-capacity cancellation, Windows; kicad-9, kicad-10, drawn-floor, routing
9/10, viewer, mcp, wheel, dco).
