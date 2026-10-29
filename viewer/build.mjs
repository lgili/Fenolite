// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The build of the viewer page (change c0272, design decisions 3 to 8). The TypeScript compiler type-checks
// viewer/src and emits each module; the modules are linked into one classic script in the order main.ts
// imports them, without their import declarations and export keywords, so every top-level name stays a page
// global (the visual tests read them). esbuild bundles Preact into an IIFE that assigns the global `preact`, and
// the stylesheet. Writes src/fenolite/view/static/{page.html,viewer.js,viewer.css,manifest.json}; with
// --check, builds in memory and fails when a committed file differs. The output depends only on the sources and
// the pinned tools: no time, no absolute path.
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";
import ts from "typescript";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(HERE, "src");
const OUT = resolve(HERE, "..", "src", "fenolite", "view", "static");
const SOURCE_FILES = ["build.mjs", "package.json", "package-lock.json", "tsconfig.json"];
const SPDX = ["// SPDX-License-Identifier: Apache-2.0", "// Copyright (c) 2026 Fenolite contributors"];
const W3 = 5;   // the namespace literals of Preact's dist that the build rewrites (decision 6)

class BuildError extends Error {}
const fail = message => { throw new BuildError(message); };
const posix = p => p.split(sep).join("/");
const version = name => JSON.parse(readFileSync(join(HERE, "node_modules", name, "package.json"), "utf8")).version;

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(path)); else out.push(path);
  }
  return out;
}

// ---- 1. type check and emit
function compile() {
  const config = ts.readConfigFile(join(HERE, "tsconfig.json"), ts.sys.readFile);
  if (config.error) fail(ts.flattenDiagnosticMessageText(config.error.messageText, "\n"));
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, HERE);
  const options = { ...parsed.options, rootDir: SRC, outDir: join(HERE, "emit"), noEmit: false, declaration: false, sourceMap: false };
  const program = ts.createProgram({ rootNames: parsed.fileNames, options });
  const diagnostics = ts.getPreEmitDiagnostics(program);
  const host = { getCanonicalFileName: f => f, getCurrentDirectory: () => HERE, getNewLine: () => "\n" };
  if (diagnostics.length) fail(`${diagnostics.length} TypeScript diagnostic(s):\n` + ts.formatDiagnostics(diagnostics, host));
  const emitted = new Map();
  const result = program.emit(undefined, (name, text) => { emitted.set(posix(relative(join(HERE, "emit"), name)), text); });
  if (result.emitSkipped || result.diagnostics.length) fail(ts.formatDiagnostics(result.diagnostics, host) || "emit skipped");
  return { program, emitted };
}

// ---- 2. the link order: the imports of main.ts, every module once
function linkOrder(program) {
  const main = program.getSourceFile(join(SRC, "main.ts"));
  if (!main) fail("viewer/src/main.ts is missing");
  const order = [];
  for (const st of main.statements) {
    if (!ts.isImportDeclaration(st)) continue;
    const spec = st.moduleSpecifier.text;
    const base = posix(join(dirname(posix(relative(SRC, main.fileName))), spec)).replace(/^\.\//, "");
    const found = ["ts", "tsx"].map(x => `${base}.${x}`).filter(p => existsSync(join(SRC, p)));
    if (found.length !== 1) fail(`main.ts: cannot resolve ${spec}`);
    if (order.includes(found[0])) fail(`main.ts imports ${found[0]} twice`);
    order.push(found[0]);
  }
  const modules = walk(SRC).map(p => posix(relative(SRC, p)))
    .filter(p => /\.tsx?$/.test(p) && !p.endsWith(".d.ts") && p !== "main.ts" && !p.startsWith("vendor/"));
  const missing = modules.filter(p => !order.includes(p)).sort();
  if (missing.length) fail(`main.ts does not import: ${missing.join(", ")}`);
  return [...order, "main.ts"];
}

// ---- 3. a module without its imports and export keywords, and its top-level names
function bindingNames(name, out) {
  if (ts.isIdentifier(name)) out.push(name.text);
  else for (const el of name.elements) if (!ts.isOmittedExpression(el)) bindingNames(el.name, out);
}
function strip(module, js) {
  const sf = ts.createSourceFile(module, js, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  const cuts = [], names = [];
  const lineCut = (start, end) => {   // a whole statement: its line too when nothing else is on it
    while (end < js.length && (js[end] === " " || js[end] === "\t")) end++;
    if (js[end] === "\n" && (start === 0 || js[start - 1] === "\n")) end++;
    cuts.push([start, end]);
  };
  for (const st of sf.statements) {
    if (ts.isImportDeclaration(st)) { lineCut(st.getStart(sf), st.end); continue; }
    if (ts.isExportDeclaration(st)) {
      if (st.exportClause && st.exportClause.elements && st.exportClause.elements.length) fail(`${module}: re-exports are not linked: ${st.getText(sf)}`);
      lineCut(st.getStart(sf), st.end); continue;
    }
    if (ts.isExportAssignment(st)) fail(`${module}: export default is not linked`);
    for (const m of (ts.canHaveModifiers(st) && ts.getModifiers(st)) || []) {
      if (m.kind === ts.SyntaxKind.DefaultKeyword) fail(`${module}: export default is not linked`);
      if (m.kind !== ts.SyntaxKind.ExportKeyword) continue;
      let end = m.end; while (js[end] === " ") end++;
      cuts.push([m.getStart(sf), end]);
    }
    if ((ts.isFunctionDeclaration(st) || ts.isClassDeclaration(st)) && st.name) names.push(st.name.text);
    else if (ts.isVariableStatement(st)) for (const d of st.declarationList.declarations) bindingNames(d.name, names);
  }
  let text = js;
  for (const [a, b] of cuts.sort((x, y) => y[0] - x[0])) text = text.slice(0, a) + text.slice(b);
  const lines = text.split("\n");
  if (lines[0] === SPDX[0] && lines[1] === SPDX[1]) lines.splice(0, 2);
  while (lines.length && lines[0].trim() === "") lines.shift();
  return { text: lines.join("\n").trimEnd() + "\n", names };
}

function link(program, emitted) {
  const order = linkOrder(program), owner = new Map(), parts = [];
  for (const module of order) {
    const js = emitted.get(module.replace(/\.tsx?$/, ".js"));
    if (js === undefined) fail(`no output for ${module}`);
    const { text, names } = strip(module, js);
    for (const name of names) {
      if (name === "preact") fail(`${module} declares "preact", the global of the vendor chunk`);
      if (owner.has(name)) fail(`two modules declare the top-level name "${name}": ${owner.get(name)} and ${module}`);
      owner.set(name, module);
    }
    parts.push(`// ---- ${module}\n${text}`);
  }
  return parts.join("");
}

// ---- 4. Preact as an IIFE, and the stylesheet
const noUrl = {
  name: "preact-namespaces",
  setup(build) {
    build.onLoad({ filter: /[\\/]node_modules[\\/]preact[\\/]/ }, args => {
      if (!/[\\/]preact[\\/]dist[\\/]preact\.module\.js$/.test(args.path)) fail(`the vendor chunk reads ${posix(relative(HERE, args.path))}; only preact/dist/preact.module.js is reviewed`);
      let n = 0;
      const contents = readFileSync(args.path, "utf8").replace(/"http:\/\/www\.w3\.org\/([^"]*)"/g, (_, rest) => {
        n++; return `[${["http:", "", "www.w3.org", ...rest.split("/")].map(s => JSON.stringify(s)).join(",")}].join("/")`;
      });
      if (n !== W3) fail(`Preact's dist holds ${n} namespace literals, not ${W3}: review the rewrite before upgrading`);
      return { contents, loader: "js" };
    });
  },
};
async function vendor() {
  const r = await esbuild.build({ entryPoints: [join(SRC, "vendor", "preact.ts")], absWorkingDir: HERE, bundle: true, format: "iife",
    globalName: "preact", minify: true, legalComments: "none", target: "es2022", charset: "utf8", write: false, logLevel: "silent", plugins: [noUrl] });
  return r.outputFiles[0].text.trimEnd() + "\n";
}
async function styles() {
  const r = await esbuild.build({ entryPoints: [join(SRC, "styles", "index.css")], absWorkingDir: HERE, bundle: true, target: "esnext",
    legalComments: "none", charset: "utf8", write: false, logLevel: "silent" });
  return r.outputFiles[0].text;
}

// ---- 5. the outputs and their manifest
function sha256(text) { return createHash("sha256").update(text).digest("hex"); }
export function sourcesDigest() {   // tests/unit/view/test_viewer_bundle.py computes the same in Python
  const files = [...walk(SRC).map(p => posix(relative(HERE, p))), ...SOURCE_FILES].sort();
  const h = createHash("sha256");
  for (const f of files) h.update(f + "\0").update(readFileSync(join(HERE, f), "utf8").replace(/\r\n/g, "\n")).update("\0");
  return h.digest("hex");
}
function preactNotice() {
  const text = readFileSync(join(HERE, "node_modules", "preact", "LICENSE"), "utf8").trim().replace(/\r\n/g, "\n");
  return `/*\n * Preact ${version("preact")}, bundled below (variable \`preact\`).\n *\n` + text.split("\n").map(l => (" * " + l).trimEnd()).join("\n") + "\n */\n";
}

export async function build() {
  const { program, emitted } = compile();
  const app = link(program, emitted);
  const js = [
    "// SPDX-License-Identifier: Apache-2.0 AND MIT",
    ...SPDX.slice(1),
    "// The script of the Fenolite viewer page, built by viewer/build.mjs from viewer/src (change c0272). Do not edit:",
    "// change the sources and run `make viewer`. fenolite.view.export.template() inlines it after the page's",
    "// \"use strict\" prologue and its EMBED and LIVE constants.",
    "",
  ].join("\n") + preactNotice() + await vendor() + app;
  const css = "/* SPDX-License-Identifier: Apache-2.0 */\n/* The stylesheet of the Fenolite viewer page, built by viewer/build.mjs from viewer/src/styles (change c0272). */\n" + await styles();
  const shell = readFileSync(join(SRC, "page.html"), "utf8").replace(/\r\n/g, "\n");
  for (const [name, text, tag] of [["viewer.js", js, "script"], ["viewer.css", css, "style"]]) {
    if (text.toLowerCase().includes(`</${tag}`)) fail(`${name} holds "</${tag}", which would end its element in the page`);
    if (/https?:\/\//.test(text)) fail(`${name} holds a URL: ${text.match(/https?:\/\/\S*/)[0]}`);
  }
  for (const mark of ["/*__CSS__*/", "/*__JS__*/", "/*__DATA__*/null", "/*__LIVE__*/false"])
    if (shell.split(mark).length !== 2) fail(`page.html must hold ${mark} once`);
  const outputs = { "page.html": shell, "viewer.css": css, "viewer.js": js };
  const manifest = {
    schema: "fenolite.viewer_build.v1",
    sources: sourcesDigest(),
    outputs: Object.fromEntries(Object.entries(outputs).map(([k, v]) => [k, sha256(v)])),
    tools: { esbuild: version("esbuild"), preact: version("preact"), typescript: version("typescript") },
  };
  return { ...outputs, "manifest.json": JSON.stringify(manifest, null, 2) + "\n" };
}

async function main() {
  const check = process.argv.includes("--check");
  let files;
  try { files = await build(); } catch (e) {
    if (e instanceof BuildError) { console.error(`viewer build: ${e.message}`); process.exit(1); }
    throw e;
  }
  if (check) {
    const stale = Object.entries(files).filter(([name, text]) => !existsSync(join(OUT, name)) || readFileSync(join(OUT, name), "utf8") !== text).map(([n]) => n);
    if (stale.length) { console.error(`viewer build: src/fenolite/view/static/ is not a fresh build of viewer/src: ${stale.join(", ")}; run \`make viewer\``); process.exit(1); }
    console.log(`viewer build: the committed bundle is current (${Object.keys(files).join(", ")})`);
    return;
  }
  for (const [name, text] of Object.entries(files)) writeFileSync(join(OUT, name), text);
  console.log(Object.entries(files).map(([n, t]) => `${n} ${Buffer.byteLength(t)} bytes`).join("\n"));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
