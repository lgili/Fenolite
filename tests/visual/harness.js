// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The browser side of the visual tests (change c0191). Reads a job file (JSON), opens each page in one Chromium,
// runs the job's script in the page, takes a screenshot and compares it with the reference, all in the browser:
// a pixel differs when a channel differs by more than `threshold` levels. Writes the screenshot, and a
// difference image when the pixels that differ exceed `max_ratio`; prints one JSON reply.
const fs = require("fs");
const { chromium } = require(process.env.FENOLITE_PLAYWRIGHT || "playwright");

async function compare(page, shot, ref) {
  return page.evaluate(async ([a, b]) => {
    const load = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = src; });
    const [x, y] = await Promise.all([load(a), load(b)]);
    if (x.width !== y.width || x.height !== y.height) return { size: [x.width, x.height, y.width, y.height] };
    const c = document.createElement("canvas"); c.width = x.width; c.height = x.height; const g = c.getContext("2d");
    g.drawImage(x, 0, 0); const p = g.getImageData(0, 0, c.width, c.height);
    g.clearRect(0, 0, c.width, c.height); g.drawImage(y, 0, 0); const q = g.getImageData(0, 0, c.width, c.height);
    const out = g.createImageData(c.width, c.height); let n = 0;
    for (let i = 0; i < p.data.length; i += 4) {
      let d = 0; for (let k = 0; k < 3; k++) d = Math.max(d, Math.abs(p.data[i + k] - q.data[i + k]));
      const v = Math.round((p.data[i] + p.data[i + 1] + p.data[i + 2]) / 12);
      if (d > window.THRESHOLD) { n++; out.data[i] = 255; out.data[i + 1] = 0; out.data[i + 2] = 255; } else { out.data[i] = out.data[i + 1] = out.data[i + 2] = v; }
      out.data[i + 3] = 255;
    }
    g.putImageData(out, 0, 0);
    return { differing: n, pixels: c.width * c.height, diff: c.toDataURL("image/png") };
  }, [shot, ref]);
}

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const browser = await chromium.launch({ ...(process.env.FENOLITE_CHROMIUM ? { executablePath: process.env.FENOLITE_CHROMIUM } : {}), args: ["--disable-gpu", "--font-render-hinting=none", "--disable-lcd-text"] });
  const replies = [];
  try {
    for (const job of jobs) {
      const context = await browser.newContext({ viewport: { width: job.width, height: job.height }, deviceScaleFactor: 1, colorScheme: job.scheme || "dark" });   // c0300: the dark shell unless a job asks
      const page = await context.newPage(); const errors = [];
      page.on("pageerror", e => errors.push(String(e)));
      await page.goto("file://" + job.page + (job.hash || ""));
      await page.waitForFunction(() => typeof linkReady !== "undefined" && linkReady && typeof S !== "undefined" && S, null, { timeout: 60000 });
      let result = null;
      if (job.script) result = await page.evaluate(`(async () => { ${job.script} })()`);
      if (job.reloadScript) {   // c0300: what a page keeps across a reload (localStorage of the same context)
        await page.reload();
        await page.waitForFunction(() => typeof linkReady !== "undefined" && linkReady && typeof S !== "undefined" && S, null, { timeout: 60000 });
        result = { before: result, after: await page.evaluate(`(async () => { ${job.reloadScript} })()`) };
      }
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      const reply = { name: job.name, result, errors };
      if (job.frameScript) {
        reply.frames = [];
        for (const frame of page.frames().filter(f => f.parentFrame() === page.mainFrame())) {
          await frame.waitForFunction(() => typeof linkReady !== "undefined" && linkReady && typeof S !== "undefined" && S, null, { timeout: 15000 });
          reply.frames.push(await frame.evaluate(`(async () => { ${job.frameScript} })()`));
        }
      }
      if (job.shot) {
        const png = await page.screenshot({ path: job.shot });
        if (job.ref && fs.existsSync(job.ref)) {
          await page.evaluate(t => { window.THRESHOLD = t; }, job.threshold);
          const data = u => "data:image/png;base64," + u.toString("base64");
          const cmp = await compare(page, data(png), data(fs.readFileSync(job.ref)));
          if (cmp.size) Object.assign(reply, { ok: false, size: cmp.size });
          else {
            const ratio = cmp.differing / cmp.pixels;
            Object.assign(reply, { ok: ratio <= job.max_ratio, differing: cmp.differing, pixels: cmp.pixels, ratio });
            if (!reply.ok && job.diff) { fs.writeFileSync(job.diff, Buffer.from(cmp.diff.split(",")[1], "base64")); reply.diff = job.diff; }
          }
        } else reply.ok = null;   // no reference yet
      }
      replies.push(reply); await context.close();
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify(replies));
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(1); });
