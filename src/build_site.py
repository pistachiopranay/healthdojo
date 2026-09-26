"""Build site/index.html from data/results.json: hero, leaderboard, failure heatmaps, scene explorer.

Re-run any time results change:  .venv/bin/python src/build_site.py
Images are resized into site/renders (full, max 1600px) and site/thumbs (640px).
"""
import json, re, shutil, collections
from common import ROOT, DATA, BENCH, bench_meta

SITE = ROOT / "site"
TYPES = ["object", "absence", "measurement", "lighting"]


def providers():
    """Model name -> provider label, parsed from run_models.py MODELS table (fallback by name)."""
    out = {}
    try:
        src = (ROOT / "src" / "run_models.py").read_text()
        for name, call, rest in re.findall(r'^\s*"([\w.\-]+)":\s*\(lambda:\s*(\w+)_call(.*)$', src, re.M):
            label = re.findall(r'"([^"]+)"', rest.split("),", 1)[-1])  # explicit provider label, if the tuple has one
            out[name] = (label[-1] if len(label) >= 2 else None) or {"bedrock": "AWS Bedrock", "anthropic": "Anthropic API", "openai": "OpenAI API"}.get(call, call)
    except OSError:
        pass
    return out


def prov_for(m, table):
    if m in table:
        return table[m]
    if m.startswith("claude"):
        return "Anthropic API"
    if m.startswith("gpt"):
        return "OpenAI API"
    return "AWS Bedrock"


def enrich(res):
    """Add precision / false-alarm counts / coverage per model (computed from predictions, same rules as grade.py)."""
    scenes = {s["id"]: s for s in res["scenes"]}
    ka = {k: set(v) for k, v in res.get("known_absent", {}).items()}
    preds = res.get("predictions", {})
    ptable = providers()
    for row in res["leaderboard"]:
        m = row["model"]
        tp = fp = tn = n = 0
        for sid, s in scenes.items():
            p = preds.get(sid, {}).get(m)
            if p is None:
                continue
            n += 1
            pred = set(p.get("pred", []))
            gt = {h["id"] for h in s["hazards"]}
            tp += len(gt & pred)
            for neg in ka.get(s.get("base", sid), set()) - gt:
                if neg in pred:
                    fp += 1
                else:
                    tn += 1
        row.setdefault("precision", round(tp / (tp + fp), 3) if tp + fp else None)
        row.setdefault("fp", fp)
        row.setdefault("tn", tn)
        row.setdefault("scenes_run", n)
        r, pr = row.get("recall", 0), row.get("precision")
        row.setdefault("f1", round(2 * r * pr / (r + pr), 3) if pr and r + pr else 0)
        row["provider"] = row.get("provider") or prov_for(m, ptable)
    res["n_scenes_total"] = len(scenes)
    # verification funnel: every generated scene, incl. rejected ones (grade.py drops them from results)
    from common import SCENES, hazard_type
    allsc = [json.loads(p.read_text()) for p in sorted(SCENES.glob("*.json"))]
    edits = [s for s in allsc if s.get("kind") == "edit"]
    by_type = collections.defaultdict(lambda: {"generated": 0, "rejected": []})
    for s in edits:
        for t in {hazard_type(h["id"]) for h in s["hazards"]}:
            by_type[t]["generated"] += 1
            if s.get("verified") is False:
                by_type[t]["rejected"].append(s["id"])
    res["verification"] = {"generated": len(allsc), "rejected": [s["id"] for s in allsc if s.get("verified") is False],
                           "by_type": dict(by_type)}
    return res


def copy_images(res):
    (SITE / "renders").mkdir(parents=True, exist_ok=True)
    (SITE / "thumbs").mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for s in res["scenes"]:
        src = DATA / s["image"]
        if not src.exists():
            continue
        full, thumb = SITE / "renders" / (src.stem + ".jpg"), SITE / "thumbs" / (src.stem + ".jpg")
        if full.exists() and thumb.exists() and full.stat().st_mtime >= src.stat().st_mtime:
            continue
        if Image is None:
            shutil.copy(src, full); shutil.copy(src, thumb); continue
        im = Image.open(src).convert("RGB")
        for dest, w in ((full, 1600), (thumb, 640)):
            c = im.copy(); c.thumbnail((w, w)); c.save(dest, "JPEG", quality=84 if w > 1000 else 78)


def bench_copy(html, n_haz):
    """Swap HomeBench-specific page copy for a BENCH's own (from its taxonomy json 'site' block). No-op for HomeBench."""
    if not BENCH:
        return html
    site = bench_meta().get("site", {})
    for old, new in site.get("replace", []):
        html = html.replace(old, new)
    html = html.replace("HomeBench leaderboard", f"{site.get('title', BENCH)} leaderboard")
    html = html.replace("the same 35-hazard checklist", f"the same {n_haz}-hazard checklist")
    return html


def main():
    res = enrich(json.loads((DATA / "results.json").read_text()))
    copy_images(res)
    for s in res["scenes"]:  # site-relative image paths
        stem = (DATA / s["image"]).stem
        s["img"], s["thumb"] = f"renders/{stem}.jpg", f"thumbs/{stem}.jpg"
    html = (ROOT / "src" / "site_template.html").read_text().replace("/*DATA*/null", json.dumps(res, separators=(",", ":")))
    out = SITE / (f"{BENCH}.html" if BENCH else "index.html")
    html = bench_copy(html, len(res.get("taxonomy", {})))
    html = html.replace(f'data-bench="{BENCH or "homebench"}"', f'data-bench="{BENCH or "homebench"}" style="color:var(--ink);text-decoration:underline"')
    out.write_text(html)
    print("wrote", out, f"({len(res['leaderboard'])} models, {len(res['scenes'])} scenes)")


if __name__ == "__main__":
    main()
