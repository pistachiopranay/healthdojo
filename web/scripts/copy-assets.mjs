// Copy the image/video assets the v2 site actually uses from ../site and ../data into public/.
// Re-run safely; files are only copied when missing or newer. Keeps the deploy small (no curriculum steps, no panos).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = path.resolve(WEB, "..");
const SITE = path.join(ROOT, "site");
const DATA = path.join(ROOT, "data");
const PUB = path.join(WEB, "public");
let n = 0;

function copy(src, dest) {
  if (!fs.existsSync(src)) { console.warn("missing", path.relative(ROOT, src)); return; }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  if (fs.existsSync(dest) && fs.statSync(dest).mtimeMs >= fs.statSync(src).mtimeMs) return;
  fs.copyFileSync(src, dest); n++;
}
function copyDir(src, dest, filter = () => true) {
  if (!fs.existsSync(src)) return;
  for (const f of fs.readdirSync(src)) {
    const s = path.join(src, f);
    if (fs.statSync(s).isFile() && filter(f)) copy(s, path.join(dest, f));
  }
}

// 1. benchmark scene images (falls + dementia share site/renders and site/thumbs)
copyDir(path.join(SITE, "renders"), path.join(PUB, "renders"), f => f.endsWith(".jpg"));
copyDir(path.join(SITE, "thumbs"), path.join(PUB, "thumbs"), f => f.endsWith(".jpg"));
// 2. recorded walk replays
copyDir(path.join(SITE, "videos"), path.join(PUB, "videos"));
// 3. 3D world thumbnails
copyDir(path.join(DATA, "worlds"), path.join(PUB, "worlds"), f => f.endsWith(".thumb.jpg"));
// 3b. Overview pipeline artifacts (one hazard, STAIR-03, followed through every stage)
for (const f of ["pano-stairs-base0-STAIR-03.jpg", "w3crop-stairs-base0-STAIR-03.jpg"]) copy(path.join(SITE, "home-assets", f), path.join(PUB, "home", f));
// 4. curriculum thumbs: only images that passed the automated check
for (const bench of ["falls", "dementia"]) {
  const m = JSON.parse(fs.readFileSync(path.join(DATA, "curriculum", bench, "manifest.json"), "utf8"));
  for (const it of m.items) {
    if (it.verified !== true || !it.thumb) continue;
    copy(path.join(SITE, "curriculum", bench, it.thumb), path.join(PUB, "curriculum", bench, it.thumb));
  }
}
// 5. legacy interactive viewers, kept as static pages under /explore/
const LINKS = [
  [/href="home\.html"/g, 'href="/"'],
  [/href="index\.html"/g, 'href="/results/"'],
  [/href="dementia\.html"/g, 'href="/results/#dementia"'],
  [/href="guidelines\.html"/g, 'href="/method/"'],
  [/href="guideline-(falls|dementia)\.html"/g, 'href="/method/"'],
  [/href="worlds_3d\.html"/g, 'href="/explore/#worlds"'],
  [/href="walk-videos\.html"/g, 'href="/explore/#replays"'],
  [/href="walk\.html"/g, 'href="/explore/walk"'],
  [/`walk\.html\?w=/g, "`/explore/walk?w="],
  [/\.\.\/data\/walks\//g, "/data/walks/"],
  // v2 nav labels and honest wording on the legacy walk page
  [/<div class="hd-links">[\s\S]*?<\/div>\s*<a href="[^"]*" class="hd-cta">[^<]*<\/a>/,
    '<div class="hd-links"><a href="/">Overview</a><a href="/method/">How it works</a><a href="/explore/" class="on">Explore</a><a href="/results/">Early results</a><a href="https://github.com/pistachiopranay/healthdojo">GitHub</a></div>\n  <a href="/explore/" class="hd-cta">Back to Explore</a>'],
  [/Drop the model <em>into the home\.<\/em>/, "Drop the model <em>into a synthetic room.</em>"],
  [/Each model stands inside a 360° home,/, "Each model stands inside a synthetic 360° room,"],
];
for (const f of ["world.html", "walk.html"]) {
  let html = fs.readFileSync(path.join(SITE, f), "utf8");
  for (const [re, to] of LINKS) html = html.replace(re, to);
  const dest = path.join(PUB, "explore", f);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  if (!fs.existsSync(dest) || fs.readFileSync(dest, "utf8") !== html) { fs.writeFileSync(dest, html); n++; }
  // walk.html needs the panoramas and per-step frames it references
  for (const m of html.matchAll(/\/data\/walks\/([^"'`\s]+)/g)) {
    const rel = m[1];
    if (rel.endsWith("/")) copyDir(path.join(DATA, "walks", rel), path.join(PUB, "data", "walks", rel), x => x.endsWith(".jpg"));
    else copy(path.join(DATA, "walks", rel), path.join(PUB, "data", "walks", rel));
  }
}
console.log(`assets: ${n} file(s) copied into web/public`);
