// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The writes of this session (c0271), a Preact list at the foot of the Actions panel (change c0272, decision
// 10): one row per receipt with its time, action and files, and Undo, which plans `restore` on it.
import * as preact from "preact";
import { actUndo } from "../actions/actions";

export function ReceiptList({ receipts }: { receipts: any[] }) {
  return <><h4>Writes of this session</h4>{receipts.map(r =>
    <div class="actReceipt"><span>{`${r.time || ""} · ${r.action} · ${(r.files || []).join(", ")}`}</span>
      <button onClick={() => actUndo(r.id)}>Undo…</button></div>)}</>;
}
export function buildReceipts(panel, receipts) {   // appended to the panel, which is rebuilt as a whole
  if (!receipts.length) return;
  const box = document.createElement("div"); box.className = "actReceipts"; panel.appendChild(box);
  preact.render(<ReceiptList receipts={receipts} />, box);
}
