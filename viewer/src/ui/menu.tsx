// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// A menu button (c0300, design decision 3): a toolbar button with aria-haspopup that opens a list of items
// (role="menu") or a small panel under it. The list is placed with fixed coordinates, so no scrolling parent clips
// it; arrows move between items, Enter runs one, Esc closes and gives the focus back to the button, and a click
// elsewhere closes it.
import * as preact from "preact";
import { Icon } from "./icons";

export type MenuItem = { id?: string, title?: string, icon?: string, keys?: string, run?: () => void, checked?: boolean,
  radio?: boolean, disabled?: boolean, sep?: boolean, hint?: string, heading?: string };
type MenuProps = { id: string, label: string, icon?: string, text?: string, tip?: string, keys?: string, items?: MenuItem[],
  panel?: () => any, cls?: string, caret?: boolean, pressed?: boolean, align?: "left" | "right", showLabel?: boolean };
let OPEN_MENU: Menu = null;
export function closeMenus() { if (OPEN_MENU) OPEN_MENU.close(false); }

export class Menu extends preact.Component<MenuProps, { open: boolean, x: number, y: number }> {
  declare button: HTMLButtonElement; declare list: HTMLElement;
  constructor(props) { super(props); this.state = { open: false, x: 0, y: 0 }; }
  outside = (e: Event) => { const t = e.target as Node; if (this.list?.contains(t) || this.button?.contains(t)) return; this.close(false); };
  open() {
    if (OPEN_MENU && OPEN_MENU !== this) OPEN_MENU.close(false);
    const r = this.button.getBoundingClientRect(), w = 232;
    const x = this.props.align === "right" || r.left + w > innerWidth - 8 ? Math.max(8, r.right - w) : r.left;
    OPEN_MENU = this; this.setState({ open: true, x, y: r.bottom + 6 }, () => {
      document.addEventListener("pointerdown", this.outside, true);
      (this.list?.querySelector("[role^=menuitem]:not([disabled]), input, select, button") as HTMLElement)?.focus();
    });
  }
  close(focus = true) {
    document.removeEventListener("pointerdown", this.outside, true);
    if (OPEN_MENU === this) OPEN_MENU = null;
    if (this.state.open) this.setState({ open: false }); if (focus) this.button?.focus();
  }
  componentWillUnmount() { document.removeEventListener("pointerdown", this.outside, true); if (OPEN_MENU === this) OPEN_MENU = null; }
  onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); this.close(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const items = [...this.list.querySelectorAll("[role^=menuitem]:not([disabled])")] as HTMLElement[]; if (!items.length) return;
    e.preventDefault(); const i = items.indexOf(document.activeElement as HTMLElement);
    items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus();
  };
  choose(it: MenuItem) { if (it.disabled) return; this.close(); it.run && it.run(); }
  render(p: MenuProps, s) {
    return <span class={"menuWrap" + (p.cls ? " " + p.cls : "")}>
      <button id={p.id} type="button" class={"tb" + (p.caret ? " caret" : "") + (p.showLabel === false || !p.text ? " icon" : "")}
        aria-haspopup="menu" aria-expanded={Boolean(s.open)} aria-label={p.label} aria-pressed={p.pressed}
        data-tip={p.tip || p.label} data-keys={p.keys || undefined} ref={el => { this.button = el; }}
        onClick={() => s.open ? this.close() : this.open()} onKeyDown={e => { if (e.key === "ArrowDown" && !s.open) { e.preventDefault(); this.open(); } }}>
        {p.icon ? <Icon name={p.icon} /> : null}{p.text ? <span class="lbl">{p.text}</span> : null}{p.caret ? <Icon name="chevDown" size={12} /> : null}
      </button>
      {s.open ? <div class={"menu" + (p.panel ? " menuPanel" : "")} role={p.panel ? "dialog" : "menu"} aria-label={p.label} style={`left:${s.x}px;top:${s.y}px`}
        ref={el => { this.list = el; }} onKeyDown={this.onKey}>
        {p.panel ? p.panel() : (p.items || []).map((it, k) => it.sep ? <div key={k} class="menuSep" role="separator"></div>
          : it.heading ? <div key={k} class="menuHead">{it.heading}</div>
          : <button key={k} id={it.id} type="button" role={it.radio ? "menuitemradio" : it.checked !== undefined ? "menuitemcheckbox" : "menuitem"}
            aria-checked={it.checked} disabled={it.disabled} class="menuItem" onClick={() => this.choose(it)}>
            <span class="menuIc">{it.checked ? <Icon name="check" /> : it.icon ? <Icon name={it.icon} /> : null}</span>
            <span class="menuText">{it.title}{it.hint ? <small>{it.hint}</small> : null}</span>
            {it.keys ? <kbd>{it.keys}</kbd> : null}
          </button>)}
      </div> : null}
    </span>;
  }
}
