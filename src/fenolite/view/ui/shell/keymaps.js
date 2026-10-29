// ================================================================== keymaps (change c0245, decision 5)
// The keymaps over the `fenolite` keys of each command, and the keys a browser keeps for itself. The JSON
// between the braces is read as it stands by fenolite.view.keymap, so it stays plain JSON.
// - `altium`: menu accelerator sequences that Altium Designer documents (S-0921): V,F fit board; V,D fit
//   document; X,A deselect all.
// - `kicad`: the habits KiCad documents (S-0920): ` highlights the net under the cursor, ~ clears the
//   highlight, N and Shift+N step the grid, Alt+1 and Alt+2 choose the fast grids (their values are
//   Fenolite's choice: 0.1 mm and 0.5 mm, or 5 and 25 mil).
// - `reserved`: the tab, window, address-bar, history, page and developer-tool keys of Chrome on Windows and
//   Linux (S-0934) and of Safari on macOS (S-0935). A keymap may not bind them.
const KEYMAP_DATA = {
  "schema": "fenolite.view_keymap_data.v0",
  "maps": {
    "altium": {
      "view.fit": ["V F", "V D", "F", "Shift+F"],
      "edit.clear-selection": ["X A"]
    },
    "kicad": {
      "view.highlight-net": ["`"],
      "edit.clear-selection": ["~"],
      "view.grid-next": ["N"],
      "view.grid-prev": ["Shift+N"],
      "view.grid-fast-1": ["Alt+1"],
      "view.grid-fast-2": ["Alt+2"],
      "place.mark": []
    }
  },
  "sources": {
    "altium": {"view.fit": "S-0921", "edit.clear-selection": "S-0921"},
    "kicad": {"view.highlight-net": "S-0920", "edit.clear-selection": "S-0920", "view.grid-next": "S-0920",
      "view.grid-prev": "S-0920", "view.grid-fast-1": "S-0920", "view.grid-fast-2": "S-0920"}
  },
  "reserved": [
    "Ctrl+N", "Ctrl+Shift+N", "Ctrl+T", "Ctrl+Shift+T", "Ctrl+Tab", "Ctrl+Shift+Tab", "Ctrl+PageDown", "Ctrl+PageUp",
    "Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4", "Ctrl+5", "Ctrl+6", "Ctrl+7", "Ctrl+8", "Ctrl+9",
    "Ctrl+W", "Ctrl+F4", "Ctrl+Shift+W", "Alt+F4", "Alt+ArrowLeft", "Alt+ArrowRight", "Ctrl+L", "Alt+D", "F6",
    "F5", "Ctrl+R", "F11", "F12", "Ctrl+Shift+J", "Ctrl+F", "F3", "Ctrl+P", "Ctrl+H", "Ctrl+J", "Alt+F", "Alt+E", "F10",
    "Meta+W", "Meta+Shift+T", "Meta+Shift+]", "Meta+Shift+[",
    "Meta+1", "Meta+2", "Meta+3", "Meta+4", "Meta+5", "Meta+6", "Meta+7", "Meta+8", "Meta+9",
    "Meta+[", "Meta+]", "Meta+L"
  ]
};
for (const [name, map] of Object.entries(KEYMAP_DATA.maps)) KEYMAPS[name] = map;
const RESERVED = new Set(KEYMAP_DATA.reserved.map(k => normKey(k)));
