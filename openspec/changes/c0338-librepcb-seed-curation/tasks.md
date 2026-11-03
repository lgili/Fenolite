## 0. Scope
- [x] 0.1 Validate the explicit curation contract before mutation; preserve raw failed candidates.
## 1. External candidate
- [x] 1.1 Implement and replay deterministic external recipe; prove only two pin lengths differ semantically and every footprint/device record stays byte-identical.
- [x] 1.2 Preserve original source/UUID/hash and modification notice; validate provenance and hashes, no arbitrary schema keys or invented review.
- [x] 1.3 Prove native KiCad before/after partition equality and complete library check exit0/zero ERROR with four preferred100mil WARN visible; generate exact-plan review sheets with explicit change preview.
## 2. Human and release gates
- [x] 2.1 Obtain actual per-item human review of this candidate with sheet digests; do not infer acceptance from generation.
- [ ] 2.2 Root/library owner integrates reviewed candidates and runs exact-source library/core CI before c0266/c0279 closure. No publication or cleanup before preserving evidence.

Proof: four-item external recipe repeated with byte-identical receipt/output SHA; only two symbol lengths differ32um, all footprint/device record bytes preserved. Provenance validator accepts existing modification_notice/NOTICE and output hashes. Complete check exit0, zero ERROR, four WARN visible; exact-plan sheets confirmed and hashes verified. KiCad10.0.6 native three-net partitions equal before/after. The artifact does not infer human approval or CI completion. Maintainer explicitly retained2.032mm and visible warnings, rather than increasing to2.54mm to suppress them.

Actual human approval (2026-11-02): Luiz Carlos Gili stated “Revisei e aprovo os quatro itens, considerando os avisos”, for the four exact sheet digests in approval.md, including the32um artwork delta and four visible preferred100mil warnings. Three CLI acceptance confirmations exist; device acceptance materialization is blocked only by the direct-device dependency discovery bug owned by root, not by missing human approval. Release/audit/CI remain pending under2.2.
