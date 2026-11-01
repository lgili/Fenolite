// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The two constants of the inline script that precedes the bundle in the page (change c0304, decision 7):
// fenolite.view.export.page() writes the embedded data and the live flag into them.
declare const EMBED: any;
declare const LIVE: boolean;
// The objects the page exposes to the toolbar, palette and inspector of c0300 and c0301 (c0302, c0303).
interface Window { FenoliteRuns: any; FenoliteActions: any; }
