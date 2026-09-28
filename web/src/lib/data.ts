// Build-time data access. Everything is read from ../data (the same JSON the Python builders use)
// and enriched with the same rules as src/build_site.py (coverage, false-flag counts, precision).
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.cwd(), "..");
const DATA = path.join(ROOT, "data");
const read = (p: string) => JSON.parse(fs.readFileSync(path.join(DATA, p), "utf8"));

export type Hazard = { id: string; type?: string; box?: number[] };
export type Scene = {
  id: string; room: string; kind: "edit" | "base"; base?: string; hazards: Hazard[];
  image: string; img: string; thumb: string; verify?: { note?: string; other_major_changes?: boolean };
};
export type Row = {
  model: string; name: string; provider: string; score: number; recall: number; tp: number; fn: number;
  false_alarm: number; fp: number; neg: number; precision: number | null; loc_iou: number | null;
  scenes_run: number; by_type: Record<string, number>; by_room: Record<string, number>; by_hazard: Record<string, number>;
};
export type Bench = {
  key: "homebench" | "dementia"; title: string; scenes: Scene[]; rows: Row[]; nScenes: number;
  taxonomy: Record<string, { name: string; room: string; type: string }>;
  predictions: Record<string, Record<string, { pred: string[]; raw: any[] }>>;
  knownAbsent: Record<string, string[]>;
};

export const PRETTY: Record<string, string> = {
  "claude-opus-5.5": "Claude Opus 5.5", "claude-sonnet-5": "Claude Sonnet 5", "claude-haiku-4.5": "Claude Haiku 4.5",
  "gpt-5.6-sol": "GPT-5.6 Sol", "gpt-5.6-terra": "GPT-5.6 Terra", "gpt-6-luna": "GPT-6 Luna", "gpt-6-astra": "GPT-6 Astra",
  "kimi-k3": "Kimi K3", "grok-4.6": "Grok 4.6", "nova-pro": "Nova Pro", "nova-2-lite": "Nova 2 Lite",
  "llama-4-maverick": "Llama 4 Maverick", "qwen3-vl": "Qwen3-VL", "mistral-large-3": "Mistral Large 3",
  "gemma-3-27b": "Gemma 3 27B", "nemotron-nano-vl": "Nemotron Nano VL",
};
export const pn = (m: string) =>
  PRETTY[m] || m.split("-").map(w => (/^\d/.test(w) ? w : w[0].toUpperCase() + w.slice(1))).join(" ");

export const TLABEL: Record<string, string> = {
  object: "Visible object", absence: "Missing feature", measurement: "Measurement", lighting: "Lighting",
  access: "Access / wandering", perception: "Misperception",
};

function providers(): Record<string, string> {
  const out: Record<string, string> = {};
  try {
    const src = fs.readFileSync(path.join(ROOT, "src", "run_models.py"), "utf8");
    for (const m of src.matchAll(/^\s*"([\w.\-]+)":\s*\(lambda:.*"([^"]+)"\),?\s*$/gm)) out[m[1]] = m[2];
  } catch { /* fall back below */ }
  return out;
}
const PROV = providers();
const prov = (m: string) => PROV[m] || (m.startsWith("claude") ? "Anthropic API" : m.startsWith("gpt") ? "OpenAI API" : "AWS Bedrock");

function load(key: Bench["key"], file: string, title: string): Bench {
  const res = read(file);
  const scenes: Scene[] = res.scenes.map((s: any) => {
    const stem = path.basename(s.image).replace(/\.[a-z]+$/i, "");
    return { ...s, img: `/renders/${stem}.jpg`, thumb: `/thumbs/${stem}.jpg` };
  });
  const ka: Record<string, string[]> = res.known_absent || {};
  const preds = res.predictions || {};
  const rows: Row[] = res.leaderboard.map((r: any) => {
    let tp = 0, fp = 0, tn = 0, n = 0;
    for (const s of scenes) {
      const p = preds[s.id]?.[r.model];
      if (!p) continue;
      n++;
      const pred = new Set<string>(p.pred || []);
      const gt = new Set(s.hazards.map(h => h.id));
      for (const g of gt) if (pred.has(g)) tp++;
      for (const neg of ka[s.base || s.id] || []) { if (gt.has(neg)) continue; pred.has(neg) ? fp++ : tn++; }
    }
    return {
      model: r.model, name: pn(r.model), provider: prov(r.model), score: r.score, recall: r.recall, tp: r.tp, fn: r.fn,
      false_alarm: r.false_alarm, fp, neg: fp + tn, precision: tp + fp ? tp / (tp + fp) : null, loc_iou: r.loc_iou,
      scenes_run: n, by_type: r.by_type || {}, by_room: r.by_room || {}, by_hazard: r.by_hazard || {},
    };
  });
  return { key, title, scenes, rows, nScenes: scenes.length, taxonomy: res.taxonomy, predictions: preds, knownAbsent: ka };
}

let _benches: { homebench: Bench; dementia: Bench } | null = null;
export function benches() {
  return (_benches ??= {
    homebench: load("homebench", "results.json", "HomeBench"),
    dementia: load("dementia", "benchmarks/dementia/results.json", "DementiaBench"),
  });
}

/** Per-scene hit list: which models (with output) listed every seeded hazard id. */
export function sceneHits(b: Bench, sceneId: string) {
  const s = b.scenes.find(x => x.id === sceneId)!;
  const p = b.predictions[sceneId] || {};
  const gt = s.hazards.map(h => h.id);
  return b.rows.filter(r => p[r.model]).map(r => ({
    model: r.model, name: r.name, hit: gt.every(g => (p[r.model].pred || []).includes(g)),
    raw: p[r.model].raw || [],
  }));
}

export const mean = (a: (number | null | undefined)[]) => {
  const v = a.filter((x): x is number => typeof x === "number");
  return v.length ? v.reduce((x, y) => x + y, 0) / v.length : null;
};

/** Hazard ids sorted by mean recall across models (ascending), with the number of models that ran it. */
export function hardest(b: Bench, n = 10) {
  const ids = [...new Set(b.rows.flatMap(r => Object.keys(r.by_hazard)))];
  return ids.map(id => {
    const vals = b.rows.map(r => r.by_hazard[id]).filter(v => v != null);
    const scene = b.scenes.find(s => s.kind === "edit" && s.hazards.some(h => h.id === id));
    const hits = scene ? sceneHits(b, scene.id) : [];
    return { id, name: b.taxonomy[id]?.name || id, type: b.taxonomy[id]?.type || "object", recall: mean(vals) ?? 0,
      found: hits.filter(h => h.hit).length, ran: hits.length, sceneId: scene?.id };
  }).sort((a, b2) => a.recall - b2.recall).slice(0, n);
}

// ---------- curriculum (difficulty levels) + rubric ----------
export type Curriculum = {
  bench: string; guideline: any; rubric: any[]; levels: any[]; curve: Record<string, Record<string, any>>;
  items: any[]; meta: any;
};
export function curriculum(bench: "falls" | "dementia"): Curriculum {
  const m = read(`curriculum/${bench}/manifest.json`);
  return { bench, guideline: m.guideline, rubric: m.rubric, levels: m.levels, curve: m.difficulty_curve,
    items: m.items, meta: m.difficulty_curve_meta };
}
/** Verified vs generated counts per level. */
export function levelCounts(c: Curriculum) {
  return c.levels.map(l => {
    const all = c.items.filter(i => i.level === l.level);
    const ok = all.filter(i => i.verified === true);
    const labels = ok.reduce((n, i) => n + (i.hazards?.length || 0), 0);
    return { ...l, generated: all.length, verified: ok.length, labels, samples: ok.slice(0, 4) };
  });
}

// ---------- 3D worlds + walks ----------
export function worlds() {
  const w = read("worlds/worlds.json");
  return Object.entries<any>(w).filter(([, v]) => v.status === "done").map(([id, v]) => ({
    id, title: v.title, bench: v.bench, hazard_id: v.hazard_id, hazard_name: v.hazard_name || v.hazard,
    thumb: `/worlds/${id}.thumb.jpg`, viewer_url: v.viewer_url,
  }));
}
export function walks() {
  return read("walks/index.json");
}
