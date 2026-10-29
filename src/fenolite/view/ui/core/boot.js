"use strict";
const EMBED = /*__DATA__*/null;
const LIVE = /*__LIVE__*/false;
const PREVIEW_MODE = new URLSearchParams(location.hash.slice(1)).get("preview") === "1";
if (PREVIEW_MODE) document.body.classList.add("preview");

