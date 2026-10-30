// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== catalog selection (c0240)
import { allDocs, sceneOf } from "../core/documents";
import { $, download } from "../core/dom";
import { PREVIEW_MODE } from "../core/env";
import { PROJECT } from "../core/state";
export const CATSEL = { generation:0, symbols:[], footprints:[], symbol:null, footprint:null, validFilters:true, candidates:[], symbolCandidates:[], loading:false, mapping:new Map() };
export async function openCatalogSelection() {
  if (PREVIEW_MODE || !PROJECT || PROJECT.source !== "catalog") return;
  const generation = ++CATSEL.generation; CATSEL.loading = true;
  $("catalogSelection").showModal(); $("catMessage").textContent = "Loading the installed definitions…";
  try {
    const docs = allDocs().filter(d => d.viewable && d.present);
    const scenes = await Promise.all(docs.map(async d => ({doc:d.id, scene:await sceneOf(d)})));
    if (generation !== CATSEL.generation || !$("catalogSelection").open) return;
    CATSEL.symbols = []; CATSEL.footprints = [];
    for (const {doc,scene} of scenes) for (const item of scene?.items || []) {
      const facts = item.catalog_selection; if (!facts) continue;
      (facts.kind === "symbol" ? CATSEL.symbols : CATSEL.footprints).push({...item,doc});
    }
    CATSEL.loading = false; filterCatalogSelection();
  } catch (e) { if (generation === CATSEL.generation) { CATSEL.loading = false; $("catMessage").textContent = `Could not load catalog: ${e.message}`; } }
}
$("bCatalogSelection").onclick = openCatalogSelection;
$("catClose").onclick = () => $("catalogSelection").close();
$("catalogSelection").addEventListener("close", () => {
  if ($("catalogSelection").open) return;
  CATSEL.generation++; CATSEL.loading = false;
  $("catSymbolPreview").replaceChildren(); $("catFootprintPreview").replaceChildren();
});
export function catalogOptions(id, items, selected, placeholder) {
  const select = $(id); select.innerHTML = "";
  const option = document.createElement("option"); option.value = ""; option.textContent = placeholder; select.appendChild(option);
  for (const item of items) { const option = document.createElement("option"); option.value = item.lib_id; option.textContent = item.lib_id; select.appendChild(option); }
  if (selected && !items.some(x => x.lib_id === selected.lib_id)) {
    const option = document.createElement("option"); option.value = selected.lib_id; option.textContent = `${selected.lib_id} (outside filters)`; option.disabled = true; select.appendChild(option);
  }
  select.value = selected?.lib_id || "";
}
export function filterCatalogSelection() {
  if (CATSEL.loading) return;
  $("catReviewed").checked = false;
  const match = (item, text) => !text || [item.lib_id,item.category,item.summary].some(x => String(x || "").toLowerCase().includes(text));
  const sq = $("catSymbolQuery").value.trim().toLowerCase(), fq = $("catFootprintQuery").value.trim().toLowerCase();
  const symbols = CATSEL.symbols.filter(x => match(x,sq));
  const nums: any = {}, errors = [];
  for (const id of ["PadCount","SpacingMin","SpacingMax","WidthMin","WidthMax","HeightMin","HeightMax"]) {
    const input = $("cat" + id), text = input.value.trim(), number = text === "" ? null : Number(text);
    const invalid = input.validity.badInput || number !== null && (!Number.isFinite(number) || number < 0 || id === "PadCount" && !Number.isInteger(number));
    input.setAttribute("aria-invalid", String(invalid)); if (invalid) errors.push("Use nonnegative numbers; pad count must be an integer."); nums[id] = number;
  }
  for (const kind of ["Spacing","Width","Height"]) if (nums[kind+"Min"] !== null && nums[kind+"Max"] !== null && nums[kind+"Min"] > nums[kind+"Max"]) errors.push(`${kind}: minimum exceeds maximum.`);
  const range = (value,kind) => (nums[kind+"Min"] === null || value !== null && value >= nums[kind+"Min"] * 1e6) && (nums[kind+"Max"] === null || value !== null && value <= nums[kind+"Max"] * 1e6);
  const mounting = $("catMounting").value;
  const footprints = errors.length ? [] : CATSEL.footprints.filter(item => {
    const f = item.catalog_selection, pads = f.pads.filter(p => p.number);
    return match(item,fq) && (!mounting || f.mounting === mounting) && (nums.PadCount === null || f.pad_numbers.length === nums.PadCount) && range(f.min_center_spacing_nm,"Spacing") &&
      (!["WidthMin","WidthMax","HeightMin","HeightMax"].some(k => nums[k] !== null) || pads.length > 0) && pads.every(p => range(p.width_nm,"Width") && range(p.height_nm,"Height"));
  });
  CATSEL.validFilters = !errors.length; CATSEL.candidates = footprints.map(x => x.lib_id); CATSEL.symbolCandidates = symbols.map(x => x.lib_id);
  catalogOptions("catSymbol",symbols,CATSEL.symbol,"Choose a symbol"); catalogOptions("catFootprint",footprints,CATSEL.footprint,"Choose a footprint");
  $("catMessage").textContent = errors.length ? errors.join(" ") : `${symbols.length} symbols · ${footprints.length} footprints match${!symbols.length || !footprints.length ? " — no matches in one group" : ""}. Select both definitions; compatibility must be checked against your part's datasheet.`;
  catalogSelectionFacts();
}
export function catalogSelectionFacts() {
  const s = CATSEL.symbol, f = CATSEL.footprint;
  $("catSymbolFacts").textContent = s ? `${s.lib_id} · ${s.catalog_selection.pins.length} pins · ${s.evidence} · sources: ${s.sources.join(", ")}` : "No symbol selected.";
  if (f) { const facts = f.catalog_selection, spacing = facts.min_center_spacing_nm;
    $("catFootprintFacts").textContent = `${f.lib_id} · ${facts.mounting} · ${facts.pad_numbers.length} numbered pads (${facts.pad_count} physical pads) · min centre spacing ${spacing === null ? "unknown" : (spacing/1e6).toFixed(6)+" mm"} · ${f.evidence} · sources: ${f.sources.join(", ")}`;
  } else $("catFootprintFacts").textContent = "No footprint selected.";
  catalogPreview("catSymbolPreview",s,"Symbol"); catalogPreview("catFootprintPreview",f,"Footprint");
  updateCatalogSnippet();
}
export function catalogPreview(id,item,kind) {
  const host = $(id);
  if (!item || !$("catalogSelection").open || PREVIEW_MODE) { host.replaceChildren(); return; }
  if (host.firstElementChild?.dataset.item === item.lib_id) return;
  const url = new URL(location.href); url.hash = new URLSearchParams({doc:item.doc,item:item.lib_id,preview:"1"}).toString();
  const frame = document.createElement("iframe"); frame.className = "catPreview"; frame.title = `${kind}: ${item.lib_id}`;
  frame.dataset.item = item.lib_id; frame.setAttribute("sandbox","allow-scripts"); frame.src = url.href; host.replaceChildren(frame);
}
for (const id of ["SymbolQuery","FootprintQuery","PadCount","SpacingMin","SpacingMax","WidthMin","WidthMax","HeightMin","HeightMax"]) $("cat"+id).oninput = filterCatalogSelection;
$("catMounting").onchange = filterCatalogSelection;
$("catSymbol").onchange = () => { CATSEL.symbol = CATSEL.symbols.find(x => x.lib_id === $("catSymbol").value) || null; resetCatalogMapping(); catalogSelectionFacts(); };
$("catFootprint").onchange = () => { CATSEL.footprint = CATSEL.footprints.find(x => x.lib_id === $("catFootprint").value) || null; resetCatalogMapping(); catalogSelectionFacts(); };
export function catalogPins() {
  return (CATSEL.symbol?.catalog_selection.pins || []).filter((p,i,a) => a.findIndex(x=>x.number===p.number) === i);
}
export function resetCatalogMapping() {
  CATSEL.mapping = new Map(); $("catReviewed").checked = false; $("catCopyState").textContent = "";
  const box = $("catMap"); box.innerHTML = "";
  const prefix = CATSEL.symbol?.catalog_selection.reference || "U";
  $("catReference").value = (/^[A-Za-z][A-Za-z0-9_]*$/.test(prefix) ? prefix : "U") + "1";
  for (const pin of catalogPins()) {
    const label = document.createElement("label"), input = document.createElement("input");
    label.textContent = `Pin ${pin.number}: ${pin.name} (${pin.type}) → pads`; input.dataset.pin = pin.number;
    input.setAttribute("aria-label",`Pads for pin ${pin.number}`); input.placeholder = "e.g. 1 or 2, 3";
    input.oninput = () => { CATSEL.mapping.set(pin.number,input.value.split(",").map(v=>v.trim()).filter(Boolean)); $("catReviewed").checked = false; updateCatalogSnippet(); };
    label.appendChild(input); box.appendChild(label);
  }
}
export function catalogMapErrors() {
  const pins = catalogPins(), pads = CATSEL.footprint?.catalog_selection.pad_numbers || [], used = new Set(), errors = [];
  if (!CATSEL.validFilters || !CATSEL.candidates.includes(CATSEL.footprint?.lib_id) || !CATSEL.symbolCandidates.includes(CATSEL.symbol?.lib_id)) errors.push("The selected definitions are outside the current valid filters.");
  if (!pins.length || !pads.length) errors.push("Select definitions with electrical pins and numbered pads.");
  for (const pin of pins) {
    const targets = CATSEL.mapping.get(pin.number) || [];
    if (!targets.length) errors.push(`Pin ${pin.number} has no pad.`);
    for (const target of targets) {
      if (!pads.includes(target)) errors.push(`Pin ${pin.number}: unknown pad ${target}.`);
      if (used.has(target)) errors.push(`Pad ${target} is assigned more than once.`); used.add(target);
    }
  }
  const missing = pads.filter(n=>!used.has(n)); if (missing.length) errors.push(`Unmapped numbered pads: ${missing.join(", ")}.`);
  if (!/^[A-Za-z][A-Za-z0-9_]*[0-9]$/.test($("catReference").value.trim())) errors.push("Use a reference such as R1 or U12.");
  return errors;
}
export function catalogPython() {
  const s = CATSEL.symbol, f = CATSEL.footprint, q = value => JSON.stringify(value);
  const map = Object.fromEntries(catalogPins().map(pin => { const pads = CATSEL.mapping.get(pin.number); return [pin.number,pads.length === 1 ? pads[0] : pads]; }));
  return `from fenolite.dsl import Part\n\npart = Part(\n    ${q($("catReference").value.trim())},\n    ${q(s.lib_id)},\n    footprint=${q(f.lib_id)},\n    value=${q($("catValue").value)},\n    pad_map=${JSON.stringify(map)},\n)\n\n# Add part to your Design and connect its pins before building.\n`;
}
export function updateCatalogSnippet() {
  const selected = Boolean(CATSEL.symbol && CATSEL.footprint); $("catMapping").hidden = !selected;
  const errors = selected ? catalogMapErrors() : [];
  $("catReviewed").disabled = !selected || errors.length > 0;
  const ready = selected && !errors.length && $("catReviewed").checked;
  $("catMapState").textContent = !selected ? "Select both definitions to review their map." : errors.length ? errors.join(" ") : "Map structure is complete. Verify the actual part's datasheet before confirming; catalog evidence remains INFERRED.";
  $("catSnippet").hidden = !ready; $("catSnippet").value = ready ? catalogPython() : "";
  $("catCopy").disabled = $("catDownload").disabled = !ready;
  $("catCopyState").textContent = "";
}
$("catEqualNumbers").onclick = () => {
  const pads = CATSEL.footprint?.catalog_selection.pad_numbers || [];
  for (const input of $("catMap").querySelectorAll("input")) {
    const number = input.dataset.pin; input.value = pads.includes(number) ? number : "";
    CATSEL.mapping.set(number,input.value ? [input.value] : []);
  }
  $("catReviewed").checked = false; updateCatalogSnippet();
};
$("catReviewed").onchange = updateCatalogSnippet;
$("catReference").oninput = $("catValue").oninput = updateCatalogSnippet;
$("catCopy").onclick = async () => {
  if ($("catCopy").disabled) return;
  try { await navigator.clipboard.writeText($("catSnippet").value); $("catCopyState").textContent = "Python copied."; }
  catch (e) { $("catSnippet").focus(); $("catSnippet").select(); $("catCopyState").textContent = "Clipboard unavailable; copy the selected code directly."; }
};
$("catDownload").onclick = () => { if (!$("catDownload").disabled) download($("catSnippet").value,"component.py","text/x-python"); };
