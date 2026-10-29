// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The interface theme (c0300, design decision 1): "system" follows prefers-color-scheme, "dark" and "light" are
// the user's choice, kept in localStorage under fenolite.view.theme and written to html[data-theme]. Only the
// chrome changes; a document keeps the colours of its scene.
import { refreshToolbar } from "../panels/toolbar";
export const THEMES = ["system", "dark", "light"];
export let THEME = (() => { try { const t = localStorage.getItem("fenolite.view.theme"); return THEMES.includes(t) ? t : "system"; } catch (e) { return "system"; } })();
export function applyTheme() {
  if (THEME === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", THEME);
}
export function themeIsLight() {
  return THEME === "light" || (THEME === "system" && matchMedia("(prefers-color-scheme: light)").matches);
}
export function setTheme(t) {
  THEME = THEMES.includes(t) ? t : "system";
  try { localStorage.setItem("fenolite.view.theme", THEME); } catch (e) { /* the choice is kept for this page only */ }
  applyTheme(); themeChanged();
}
export function themeChanged() { refreshToolbar(); }   // what reads the theme outside CSS: the toolbar's theme icon
applyTheme();
matchMedia("(prefers-color-scheme: light)").addEventListener?.("change", () => { if (THEME === "system") themeChanged(); });
