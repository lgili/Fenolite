# Design: c0440

1. **Read before emptying.** `prepare` maps each source pad id to `openings.source_pairs(pad)` (its `mask`
   and `paste` entries) before `_clean`; `open_pad` takes them as `pairs`. Pad ids survive `_clean`.
2. **Manual 0.** `_margin` returns `pcb_length(units)` for mode 2, so 0 is a margin of 0; the KiCad writer
   writes `(solder_mask_margin 0)`, which overrides the board's setting.
3. **Writer.** `pcblib.pad_bytes` derives the modes from the model: `mask_margin` → solder mode 2 and its
   expansion, `paste_margin` → paste mode 2 and its expansion; otherwise the modes of c0160.
4. **Equivalence.** `checks` may neither import nor name a backend (`test_package.py`), so level 3 takes
   `masks`, one `norm.MaskOf` per side (pad → nanometres, `none`, `rules` or `None`), by default the pad's
   own margin; `masks_equal` treats `None` as no statement. `api.equivalence.mask_of` gives the Altium
   reading: own margin, else the bag's manual value or mode none, else the side's rule of scope `All`
   (`mask_rule`, from the kept `SolderMaskExpansion` records with `openings.rule_expansion`), else `rules`.
5. **Mode.** Not kept across KiCad (proposal, Out of scope); the value is.
