// ================================================================== icons (change c0245)
// Fenolite's own 16-pixel toolbar icons: plain strokes on a 16 x 16 grid, drawn for Fenolite (design,
// decision 14). No icon of another tool is used.
const ICONS = {
  fit: "M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4",
  cube: "M8 1.5l5.5 3v7L8 14.5 2.5 11.5v-7zM2.5 4.5L8 7.5l5.5-3M8 7.5v7",
  flip: "M3 5h8l-2.5-2.5M13 11H5l2.5 2.5",
  measure: "M1.5 10.5l9-9 4 4-9 9zM4.5 7.5l1.5 1.5M6.5 5.5l1 1M8.5 3.5l1.5 1.5",
  edge: "M3 2v12M13 2v12M5 8h6M5 8l2-2M5 8l2 2M11 8l-2-2M11 8l-2 2",
  mark: "M4 14.5V1.5M4 2h8l-2 3 2 3H4",
  link: "M7 9.5l2-2M5.5 7L4 8.5a2.5 2.5 0 003.5 3.5L9 10.5M10.5 9L12 7.5A2.5 2.5 0 008.5 4L7 5.5",
  svg: "M3 1.5h7l3 3v10H3zM10 1.5v3h3M5.5 9.5c0-1 1-1.5 2-1.5s2 .5 2 1.5-4 1-4 2.5c0 1 1 1.5 2 1.5s2-.5 2-1.5",
  print: "M4 6V1.5h8V6M4 12H2V6h12v6h-2M4 9.5h8v5H4z",
  clear: "M3.5 3.5l9 9M12.5 3.5l-9 9",
  search: "M7 12A5 5 0 107 2a5 5 0 000 10zM10.5 10.5l4 4",
  grid: "M3 3h.01M8 3h.01M13 3h.01M3 8h.01M8 8h.01M13 8h.01M3 13h.01M8 13h.01M13 13h.01",
  layers: "M8 2l6 3-6 3-6-3zM2 8l6 3 6-3M2 11l6 3 6-3",
  review: "M2.5 2.5h11v11h-11zM5 6l1.5 1.5L9.5 4.5M5 10.5h6",
  menu: "M3 4h10M3 8h10M3 12h10",
  pin: "M3 8h10",
  close: "M4 4l8 8M12 4l-8 8",
  eye: "M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8zM8 10a2 2 0 100-4 2 2 0 000 4z",
  eyeOff: "M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8zM2.5 13.5l11-11",
  roles: "M3 4.5h3M3 8h5M3 11.5h3M10 3l3 1.5L10 6zM10 10l3 1.5-3 1.5z",
  undo: "M5 4L2 7l3 3M2 7h8a4 4 0 010 8H8",
  redo: "M11 4l3 3-3 3M14 7H6a4 4 0 000 8h2",
  lock: "M4.5 7.5h7v6h-7zM6 7.5V5a2 2 0 014 0v2.5",
};
function icon(name, label) {
  const d = ICONS[name] || ICONS.menu;
  return `<svg class="ico" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false"><path d="${d}"/></svg>` + (label ? `<span class="lbl">${esc(label)}</span>` : "");
}
