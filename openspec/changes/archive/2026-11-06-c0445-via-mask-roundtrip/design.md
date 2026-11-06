# Design: c0445

1. **One value for the board.** KiCad 10 opens an untented via by the board's `pad_to_mask_clearance`.
   Its rules file does not reach a via (S-2042). So a conversion keeps the most frequent via opening and
   counts the others `changed`. The smaller value wins a tie, because a smaller opening leaves more mask
   between vias.
2. **The via's margin** (`openings.via_margin`):
   - manual state (2 at 66): the via's own expansion at 54;
   - otherwise the governing via rule (`openings.via_rule`), measured from the hole when
     `SOLDERMASKFROMHOLE=TRUE`;
   - no rule: no value, and the via does not vote.

   State 0 is read as the rules. A record whose scope selects no via (`IsPad`) is left out.
3. **Finding a via's record.** `via_margins` reads the via record named by the provenance locator
   `Vias6/Data#N` (offsets of `ViaRecord.tail`, which starts at 31). Vias tented on both sides have no
   opening and do not vote.
4. **Pads keep theirs.** A board margin other than 0 would also open every pad that has no margin of its
   own. Such a pad that holds a mask layer gets 0 first: before this change it was opened by the board's 0.
5. **Back to Altium.** `to_altium.with_mask_margin` reads `pad_to_mask_clearance` from the source board
   (0 when there is none). `lower` passes `via_mask=board.mask_margin` only for a write of a model
   (`options is None`). `via_record(mask=)` writes it at 54 and 242 in the manual state. A tented via keeps
   its flags and the manual state, as in c0112.
6. **Bytes.** `Board.mask_margin` is `None` in every build and in every board read from a file, so the
   written bytes and canonical JSON of those boards do not change.
