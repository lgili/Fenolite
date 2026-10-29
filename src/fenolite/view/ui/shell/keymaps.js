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
