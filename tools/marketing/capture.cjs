// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// Actual released viewer captures, from pages produced by prepare.py. Dev-only Node dependencies.
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');
const { chromium } = require(process.env.FENOLITE_PLAYWRIGHT || 'playwright');
const sharp = require('sharp');

const root = path.resolve(__dirname, '../..');
const input = path.join(root, 'build/presentation');
const output = path.join(root, 'docs/media');
const frames = path.join(input, 'frames');
const errors = [];
const settle = page => page.evaluate(() => new Promise(ok => requestAnimationFrame(() => requestAnimationFrame(ok))));

async function ready(page, name) {
  await page.goto(pathToFileURL(path.join(input, name)).href);
  await page.waitForFunction(() => typeof linkReady !== 'undefined' && linkReady && typeof S !== 'undefined' && S);
  await page.evaluate(() => document.fonts.ready);
  await settle(page);
}

async function clickPad(page, label, twice = false) {
  await page.evaluate(({ label, twice }) => {
    const p = S.pads.find(p => p.label === label);
    if (!p) throw new Error(`missing pad ${label}`);
    const [x, y] = w2s(p.x, p.y), r = cv.getBoundingClientRect();
    const at = { clientX: r.left + x, clientY: r.top + y, bubbles: true, view: window };
    if (twice) cv.dispatchEvent(new MouseEvent('dblclick', at));
    else {
      cv.dispatchEvent(new MouseEvent('mousedown', at));
      cv.dispatchEvent(new MouseEvent('mouseup', at));
    }
  }, { label, twice });
  await settle(page);
}

async function main() {
  fs.mkdirSync(frames, { recursive: true });
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    ...(process.env.FENOLITE_CHROMIUM ? { executablePath: process.env.FENOLITE_CHROMIUM } : {}),
    args: ['--disable-gpu', '--font-render-hinting=none', '--disable-lcd-text'],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => errors.push(String(error)));
  try {
    await ready(page, 'blink.html');
    await page.screenshot({ path: path.join(output, 'board.png') });
    await ready(page, 'routed.html');
    await page.screenshot({ path: path.join(output, 'hero.png') });
    await ready(page, 'altium.html');
    const frame = async number => page.screenshot({ path: path.join(frames, `frame-${number}.png`) });
    await frame(0);
    await clickPad(page, 'R1-1');
    await frame(1);
    await clickPad(page, 'U1-1', true);
    await page.waitForFunction(() => S.kind === 'schematic' && SCH.selComp >= 0);
    await settle(page);
    await frame(2);
    await page.keyboard.press('f');
    await settle(page);
    await frame(3);
    await page.screenshot({ path: path.join(output, 'schematic.png') });
    if (errors.length) throw new Error(errors.join('\n'));
    console.log(JSON.stringify({ browser: browser.version(), errors, frames: 4 }));
  } finally {
    await browser.close();
  }
  // Four actual application states, five seconds each. No UI or findings are painted onto the captures.
  execFileSync('ffmpeg', ['-y', '-framerate', '1/5', '-i', path.join(frames, 'frame-%d.png'),
    '-filter_complex', '[0:v]scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer',
    '-loop', '0', path.join(output, 'viewer-demo.gif')], { stdio: 'ignore' });
  const board = fs.readFileSync(path.join(output, 'hero.png')).toString('base64');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640">
  <defs><clipPath id="screen"><rect x="554" y="94" width="676" height="423" rx="12"/></clipPath></defs>
  <rect width="1280" height="640" fill="#101d24"/>
  <path d="M48 40h1184" stroke="#2c4149"/>
  <g font-family="DejaVu Sans, sans-serif">
    <rect x="50" y="80" width="132" height="30" rx="15" fill="#223c37"/>
    <text x="68" y="101" font-size="14" fill="#9ae8bb">OPEN SOURCE</text>
    <text x="48" y="189" font-size="64" font-weight="700" fill="#f2f6f7">Fenolite</text>
    <text x="51" y="245" font-size="28" fill="#b5efce">PCB automation</text>
    <text x="51" y="283" font-size="28" fill="#b5efce">in Python.</text>
    <text x="51" y="348" font-size="20" fill="#d5dfe2">Create. Inspect. Review.</text>
    <text x="51" y="387" font-size="17" fill="#a8b8bf">For engineers and AI agents.</text>
    <text x="51" y="477" font-size="17" fill="#c0ccd1">KiCad · Altium · Browser viewer</text>
    <text x="51" y="560" font-size="18" fill="#f2f6f7">github.com/lgili/Fenolite</text>
    <text x="1230" y="595" text-anchor="end" font-size="15" fill="#a8b8bf">v0.5 · Apache-2.0</text>
  </g>
  <rect x="551" y="91" width="682" height="429" rx="15" fill="#30464f"/>
  <image x="554" y="94" width="676" height="423" clip-path="url(#screen)" href="data:image/png;base64,${board}"/>
  </svg>`;
  fs.writeFileSync(path.join(output, 'social-card.svg'), svg);
  await sharp(Buffer.from(svg)).png().toFile(path.join(output, 'social-card.png'));
  if (fs.statSync(path.join(output, 'social-card.png')).size >= 1_000_000) throw new Error('social card must be below 1 MB');
}
main().catch(error => { console.error(error); process.exit(1); });
