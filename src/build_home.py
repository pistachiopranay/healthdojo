"""Build the HealthDojo landing page (site/home.html) from data/.

Every number on the page is computed here from data/ at build time; missing inputs degrade to
placeholders rather than failing. Images the page needs are copied into site/home-assets/.

Usage: python3 src/build_home.py
"""
import collections
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, SITE = ROOT / "data", ROOT / "site"
ASSETS = SITE / "home-assets"
TEMPLATE = ROOT / "src" / "home_template.html"

PRETTY = {"claude-opus-5.5": "Claude Opus 5.5", "claude-sonnet-5": "Claude Sonnet 5", "claude-haiku-4.5": "Claude Haiku 4.5",
          "gpt-5.6-sol": "GPT-5.6 Sol", "gpt-5.6-terra": "GPT-5.6 Terra", "kimi-k3": "Kimi K3", "grok-4.6": "Grok 4.6",
          "nova-pro": "Nova Pro", "nova-2-lite": "Nova 2 Lite", "llama-4-maverick": "Llama 4 Maverick", "qwen3-vl": "Qwen3-VL",
          "mistral-large-3": "Mistral Large 3", "gemma-3-27b": "Gemma 3 27B", "nemotron-nano-vl": "Nemotron Nano VL"}
pn = lambda m: PRETTY.get(m, m)
esc = lambda s: html.escape(str(s if s is not None else ""))
pct = lambda x: f"{round(100 * x)}%"


def load(rel, default=None):
    try:
        return json.loads((DATA / rel).read_text())
    except Exception:
        return default if default is not None else {}


def copy(src: Path, name: str):
    """Copy src into site/home-assets/name; return site-relative path or None."""
    if not src or not src.exists():
        return None
    ASSETS.mkdir(parents=True, exist_ok=True)
    dst = ASSETS / name
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, dst)
    return f"home-assets/{name}"


def box_html(b, label):
    if not (isinstance(b, list) and len(b) == 4):
        return ""
    x0, y0, x1, y1 = [max(0, min(1000, v)) for v in b]
    return (f'<div class="bx" style="left:{x0/10}%;top:{y0/10}%;width:{(x1-x0)/10}%;height:{(y1-y0)/10}%">'
            f'<b>{esc(label)}</b></div>')


# ---------------------------------------------------------------- data
R = load("results.json")
DEM = load("benchmarks/dementia/results.json")
WALK = load("walks/index.json")
WORLDS = load("worlds/worlds.json")
ICD = load("icd10_fall_codes.json")
CUR = {b: load(f"curriculum/{b}/manifest.json") for b in ("falls", "dementia")}
TAX = R.get("taxonomy", {})
LB = sorted(R.get("leaderboard", []), key=lambda m: -m.get("score", 0))
rubric = {r["id"]: r for r in CUR["falls"].get("rubric", [])}


def is_verified(s):
    return s.get("verified", s.get("kind") != "edit")


# ---------------------------------------------------------------- 1 hero filmstrip
def pick_run():
    runs = [r for r in WALK.get("runs", []) if r.get("mode") != "live"]
    pref = [r for r in runs if r["model"] == "gpt-5.6-sol" and r["scene"].startswith("bathroom")]
    miss = [r for r in runs if r.get("metrics", {}).get("saw_hazard") and not r.get("metrics", {}).get("found")]
    return (pref or miss or runs or [None])[0]


run = pick_run()
film, film_imgs, ticks = [], [], []
film_title = film_model = film_end = ""
if run:
    world = WALK.get("worlds", {}).get(run["scene"], {})
    film_model = pn(run["model"])
    film_title = f"{world.get('title', run['scene'])} · target {world.get('hazard_id', '')}"
    rdir = DATA / "walks" / run["model"] / run["scene"]
    steps = run.get("steps", [])
    for k, s in enumerate(steps):
        src = copy(rdir / s.get("img", ""), f"walk-{run['model']}-{run['scene']}-{s.get('img')}")
        if not src:
            continue
        a = s.get("action", {})
        thought = (s.get("thought") or a.get("thought") or "").strip()
        short = thought if len(thought) < 150 else thought[:147].rsplit(" ", 1)[0] + "…"
        flag = a.get("hazard_id") if a.get("action") == "flag" else None
        ok = s.get("correct")
        verb = a.get("action", "")
        if flag:
            mark = f'<span class="chipk {"ck-live" if ok else "ck-miss"}">flagged {esc(flag)} {"✓" if ok else "✗"}</span>'
            k_html = f"Step {s['step']} · {esc(TAX.get(flag, {}).get('name', flag))} {mark}"
        else:
            k_html = f"Step {s['step']} · {esc(verb or 'look')}"
        film.append({"step": s["step"], "k": k_html, "t": f"“{short}”", "flag": (flag if flag and not ok else None)})
        film_imgs.append(f'<img src="{src}" alt="">')
        ticks.append(f'<i class="{"f" if flag and not ok else ""}"></i>')
    m = run.get("metrics", {})
    flags = [f for f in m.get("flags", [])]
    film_end = (f"Target {world.get('hazard_id', '?')} · {world.get('hazard_name', '')}. "
                f"{len(flags)} flags, {sum(1 for f in flags if f == world.get('hazard_id'))} on target.")

# hero proof strip (computed; see stats row spec)
proof = []
_models_all = {m["model"] for m in LB} | {m["model"] for m in DEM.get("leaderboard", [])} | {r["model"] for r in WALK.get("runs", [])}
v_scenes = sum(1 for s in R.get("scenes", []) if is_verified(s))
n_worlds = sum(1 for w in WORLDS.values() if w.get("status") == "done")
if _models_all:
    proof.append(f"<div><b>{len(_models_all)}</b><span>frontier models tested</span></div>")
if n_worlds:
    proof.append(f"<div><b>{n_worlds}</b><span>walkable 3D homes</span></div>")
_b3 = [m["by_hazard"]["BATH-03"] for m in LB if "BATH-03" in m.get("by_hazard", {})]
if _b3:
    proof.append(f"<div><b>{pct(sum(_b3) / len(_b3))}</b><span>of models caught a towel bar used as a grab bar</span></div>")
if LB:
    proof.append(f"<div><b>{pct(max(m.get('false_alarm', 0) for m in LB))}</b><span>false alarms, worst model</span></div>")

# ---------------------------------------------------------------- 3 how it works
how = ""
hard = collections.defaultdict(list)
for m in LB:
    for h, v in m.get("by_hazard", {}).items():
        hard[h].append(v)
hard_avg = sorted(((h, sum(v) / len(v)) for h, v in hard.items() if v), key=lambda x: x[1])


def how_scene():
    """A verified single-hazard scene with a box and many model predictions, where models split."""
    best = None
    for s in R.get("scenes", []):
        if not s.get("verified") or len(s.get("hazards", [])) != 1 or not s["hazards"][0].get("box"):
            continue
        if s.get("verify", {}).get("other_major_changes"):
            continue
        preds = R.get("predictions", {}).get(s["id"], {})
        hid = s["hazards"][0]["id"]
        hits = sum(1 for p in preds.values() if hid in p.get("pred", []))
        if len(preds) < 8 or not (0 < hits < len(preds)):
            continue
        key = (abs(hits / len(preds) - 0.5), -len(preds))
        if best is None or key < best[0]:
            best = (key, s, preds, hits)
    return best


hs = how_scene()
if hs:
    _, s, preds, hits = hs
    h = s["hazards"][0]
    hid = h["id"]
    rr = rubric.get(hid, {})
    line = rr.get("citation", {}).get("line") or ""
    src = rr.get("citation", {}).get("source") or CUR["falls"].get("guideline", {}).get("url", "")
    # highlight the clause nearest the hazard name
    kw = {"STAIR-06": "fix loose or uneven steps", "STAIR-02": "fix loose handrails", "BATH-03": "grab bars"}.get(hid)
    qline = esc(line)
    if kw and kw in line:
        qline = qline.replace(esc(kw), f"<mark>{esc(kw)}</mark>")
    icd = ICD.get("map", {}).get(hid, {})
    sev = rr.get("severity_detail", {})
    gname = CUR["falls"].get("guideline", {}).get("publisher", "CDC")
    img = copy(SITE / s["image"], Path(s["image"]).name) if s.get("image") else None
    # verdicts: best hit (top of leaderboard) + best miss
    order = [m["model"] for m in LB]
    hitm = [m for m in order if m in preds and hid in preds[m].get("pred", [])]
    missm = [m for m in order if m in preds and hid not in preds[m].get("pred", [])]
    vd = []
    for m in hitm[:1]:
        vd.append(f'<div class="vd hit"><span class="mk">HIT</span><div><div class="vwho">{esc(pn(m))}</div>'
                  f'<div class="what">flagged {esc(", ".join(preds[m]["pred"][:3]))}</div></div></div>')
    for m in missm[:2]:
        vd.append(f'<div class="vd miss"><span class="mk">MISS</span><div><div class="vwho">{esc(pn(m))}</div>'
                  f'<div class="what">flagged {esc(", ".join(preds[m]["pred"][:3]) or "nothing")}, not {esc(hid)}</div></div></div>')
    how = f'''
    <div class="fc"><div class="chev"><b>01</b>Guideline</div><div class="gtitle"><img src="home-assets/cdc-logo.svg" alt="CDC" onerror="this.remove()"><h4>CDC STEADI · Check for Safety</h4></div><div class="gpub">{esc(gname)}</div>
      <blockquote>“{qline}”</blockquote><div class="src">{esc(src)}</div><div class="disc">Reference document. HealthDojo is not affiliated with or endorsed by CDC.</div></div>
    <div class="fc"><div class="chev"><b>02</b>Rubric</div><h4><span class="tag">{esc(hid)}</span> {esc(rr.get('name') or TAX.get(hid, {}).get('name', ''))}</h4>
      <dl class="kv"><dt>type</dt><dd>{esc(rr.get('type', TAX.get(hid, {}).get('type', '')))}</dd><dt>room</dt><dd>{esc(rr.get('room', ''))}</dd>
      <dt>severity</dt><dd><span class="chipk ck-miss">high</span> {esc(sev.get('high', ''))}</dd>
      <dt>ICD-10</dt><dd><span class="mono">{esc(icd.get('code', 'n/a'))}</dd><dt></dt><dd class="note" style="margin:0">{esc(icd.get('title', ''))}</dd>
      <dt>cites</dt><dd class="note" style="margin:0">{esc(', '.join(f"{k}: {v}" for k, v in rr.get('citation', {}).get('instruments', {}).items() if k != 'HOMEFAST'))}</dd></dl></div>
    <div class="fc"><div class="chev"><b>03</b>Synthetic home</div>
      <div class="frame">{f'<img src="{img}" alt="">' if img else ''}{box_html(h.get('box'), 'TRUTH · ' + hid)}</div>
      <div class="lbl">label written before the pixels · judge-verified ✓</div>
      <div class="note" style="margin:0">{esc(s.get('verify', {}).get('note', ''))}</div></div>
    <div class="fc"><div class="chev last"><b>04</b>Verdict</div><div class="verdicts">{''.join(vd)}</div>
      <div class="tally">{hits} of {len(preds)} models caught {esc(hid)}</div></div>'''

# ---------------------------------------------------------------- 4 finding
lb_rows = []
show = LB[:6] + ([None] if len(LB) > 8 else []) + (LB[-2:] if len(LB) > 8 else LB[6:])
for m in show:
    if m is None:
        lb_rows.append(f'<tr class="gap"><td colspan="4">· · · {len(LB) - 8} more · · ·</td></tr>')
        continue
    rk = LB.index(m) + 1
    fa = m.get("false_alarm", 0)
    fac = "hi" if fa >= .35 else "md" if fa >= .2 else "lo"
    lb_rows.append(f'<tr><td class="rk">{rk}</td><td class="mn">{esc(pn(m["model"]))}</td>'
                   f'<td><div class="sc"><b>{m.get("score", 0):.2f}</b><div class="sbar"><i style="width:{100*m.get("score",0):.0f}%"></i></div></div></td>'
                   f'<td class="fa {fac}">{pct(fa)}</td></tr>')
lb_html = f'<table class="lb"><thead><tr><th>#</th><th>Model</th><th>Score</th><th>False alarm</th></tr></thead><tbody>{"".join(lb_rows)}</tbody></table>'
lb_note = (f"Recall {pct(min(m['recall'] for m in LB))} to {pct(max(m['recall'] for m in LB))}; false alarms up to "
           f"{pct(max(m['false_alarm'] for m in LB))}." if LB else "")

hard_rows = []
for hid, avg in hard_avg[:3]:
    sc = [s for s in R.get("scenes", []) if s.get("verified") and any(h["id"] == hid for h in s.get("hazards", []))]
    th = copy(SITE / sc[0]["image"], Path(sc[0]["image"]).name) if sc and sc[0].get("image") else None
    nm = TAX.get(hid, {}).get("name", hid)
    if hid == "BATH-03":
        nm = "Towel bar positioned as a grab bar"
    hard_rows.append(f'<div class="hz">{f"<img src={chr(34)}{th}{chr(34)} alt>" if th else "<span></span>"}<div>'
                     f'<div class="pc">{pct(avg)}<small>of models catch it</small></div><div class="nm"><span class="tag">{esc(hid)}</span> {esc(nm)}</div></div></div>')

# walkthrough found-rates over the standard (non-live) worlds
wstats = collections.OrderedDict()
std_worlds = list(WALK.get("worlds", {}).keys())
for r in WALK.get("runs", []):
    if r.get("mode") == "live":
        continue
    wstats.setdefault(r["model"], {})[r["scene"]] = r.get("metrics", {})
wrows = []
ranked = sorted(wstats.items(), key=lambda kv: -sum(1 for v in kv[1].values() if v.get("found")))
for mdl, per in ranked:
    pips = "".join(f'<i class="{"y" if per.get(w, {}).get("found") else ""}" title="{esc(w)}"></i>' for w in std_worlds)
    f = sum(1 for v in per.values() if v.get("found"))
    wrows.append(f'<div class="wk"><span class="mn">{esc(pn(mdl))}</span><div class="pips">{pips}</div><b>{f}/{len(per)}</b></div>')
short = {w: w.split("-")[0].replace("bathroom", "bath") for w in std_worlds}
walks_html = ('<div class="wkh"><span>model</span><div class="pl">' + "".join(f"<span>{esc(short[w])}</span>" for w in std_worlds)
              + '</div><span></span></div>' + "".join(wrows))
saw_miss = [(m, w) for m, per in wstats.items() for w, v in per.items() if v.get("saw_hazard") and not v.get("found")]
never = [(m, w) for m, per in wstats.items() for w, v in per.items() if not v.get("saw_hazard") and not v.get("found")]
tot = sum(len(p) for p in wstats.values())
walk_callout = (f'<div class="callout"><b>{len(never)} of {tot}</b> walks never pointed the camera at the hazard; '
                f'<b>{len(saw_miss)}</b> had it in view and still flagged the wrong thing.</div>') if tot else ""
find_eyebrow = f"{len(LB)} models · {v_scenes} verified scenes · {tot} agent walks"

# ---------------------------------------------------------------- 5 difficulty
fm = CUR["falls"]
curve = fm.get("difficulty_curve") or {}
diff_h, diff_p, diff = "", "", ""
curve_html = ""


def _rec(v, l):
    x = v.get(str(l), v.get(l))
    if isinstance(x, dict):
        x = x.get("recall")
    return x if isinstance(x, (int, float)) else None


series = {m: v for m, v in curve.items() if isinstance(v, dict)} if isinstance(curve, dict) else {}
if series:
    lv = sorted({int(k) for v in series.values() for k in v if str(k).isdigit()})
    avg = {}
    for l in lv:
        vals = [r for r in (_rec(v, l) for v in series.values()) if r is not None]
        if vals:
            avg[l] = sum(vals) / len(vals)
    lv = [l for l in lv if l in avg]
    if len(lv) >= 2:
        W_, H_ = 620, 170
        xs = lambda i: 44 + i * (W_ - 110) / max(1, len(lv) - 1)
        ys = lambda v: 14 + (1 - v) * (H_ - 40)
        grid = "".join(f'<line x1="40" x2="{W_-60}" y1="{ys(g):.0f}" y2="{ys(g):.0f}" stroke="#f0f0ec"/><text x="34" y="{ys(g)+4:.0f}" font-size="10" text-anchor="end" fill="#8f9193" font-family="IBM Plex Mono">{int(g*100)}%</text>' for g in (0, .25, .5, .75, 1))
        mean = {m: sum(r for r in (_rec(v, l) for l in lv) if r is not None) / max(1, sum(1 for l in lv if _rec(v, l) is not None)) for m, v in series.items()}
        best, worst = max(mean, key=mean.get), min(mean, key=mean.get)
        lines = []
        for m, v in sorted(series.items(), key=lambda kv: kv[0] in (best, worst)):
            pts = [(xs(i), ys(_rec(v, l))) for i, l in enumerate(lv) if _rec(v, l) is not None]
            ps = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
            if m in (best, worst):
                c = "#2e7a18" if m == best else "#b23e14"
                lines.append(f'<polyline fill="none" stroke="{c}" stroke-width="2.5" points="{ps}"/>'
                             + "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3" fill="{c}"/>' for x, y in pts)
                             + f'<text x="{pts[-1][0]+8:.0f}" y="{pts[-1][1]+4:.0f}" font-size="11" fill="{c}" font-family="IBM Plex Mono">{esc(pn(m))}</text>')
            else:
                lines.append(f'<polyline fill="none" stroke="#d6d6d0" stroke-width="1.2" points="{ps}"><title>{esc(pn(m))}</title></polyline>')
        axis = "".join(f'<text x="{xs(i):.0f}" y="{H_-6}" font-size="11" text-anchor="middle" fill="#646668" font-family="IBM Plex Mono">L{l}</text>' for i, l in enumerate(lv))
        svg = (f'<svg viewBox="0 0 {W_ + 70} {H_}" width="100%" style="display:block;max-height:190px">{grid}{"".join(lines)}{axis}</svg>')
        l0, l1 = lv[0], lv[-1]
        both = [m for m, v in series.items() if _rec(v, l0) is not None and _rec(v, l1) is not None]
        down = sum(1 for m in both if _rec(series[m], l1) < _rec(series[m], l0))
        if down == len(both):
            head = f"Every model loses ground as the home gets harder: recall at L{l1} is below L{l0} for all {len(both)}."
        else:
            head = f"Recall at L{l1} is below L{l0} for {down} of {len(both)} models."
        ff = []
        for v in series.values():
            x = v.get("4", v.get(4))
            if isinstance(x, dict) and isinstance(x.get("distractor_false_flag"), (int, float)):
                ff.append(x["distractor_false_flag"])
        ffline = f'Models flagged a safe look-alike as a hazard up to <b>{pct(max(ff))}</b> of the time at L4.' if ff else ""
        curve_html = (f'<div class="appwin curve"><div class="ctxt"><div class="eyebrow" style="color:var(--text-muted)">Difficulty curve · falls · {len(series)} models</div>'
                      f'<div class="ch">{esc(head)}</div><div class="cstat">{ffline}</div>'
                      f'<div class="note"><span style="color:var(--green-ink)">■</span> best ({esc(pn(best))}) · <span style="color:var(--ember-ink)">■</span> weakest ({esc(pn(worst))}) · grey: others. Not a smooth decline: L2 adequacy calls are often hardest.</div></div>'
                      f'<div class="cplot">{svg}</div></div>')
if True:
    fall_worlds = [w for w in WORLDS.values() if w.get("status") == "done" and w.get("bench") == "falls" and w.get("scene_id")]
    by_level = collections.defaultdict(list)
    for it in fm.get("items", []):
        by_level[it.get("level")].append(it)
    cards = []
    levels = fm.get("levels", [])
    LINE = {1: "One clear hazard, clean room, good light.",
            2: "Judge adequacy: a towel bar, a short rail, a low-contrast mat.",
            3: "Two hazards plus a safe look-alike that must not be flagged.",
            4: "Three or four hazards in dim, noisy, unfamiliar rooms.",
            5: "Safe-but-scary rooms next to dense hazard rooms, in poor light."}
    used_bases = set()
    COND = {1: "good light", 2: "good light", 3: "good light", 4: "dim, night, soft focus", 5: "poor light"}

    def nmax(v):
        return max([0] + [int(x) for x in re.findall(r"\d+", str(v if v is not None else "0"))])

    def pips(v, cls):
        n = nmax(v)
        if not n:
            return '<span class="zz">none</span>'
        sq = "".join(f'<i class="{cls}"></i>' for _ in range(min(n, 4)))
        rng = "" if re.fullmatch(r"\d+", str(v)) else f'<span class="rng">{esc(v)}</span>'
        return f'<span class="pips2">{sq}</span>{rng}'

    for k, L in enumerate(levels):
        lvl = L.get("level")
        ver = [it for it in by_level.get(lvl, []) if it.get("verified")]
        img = None
        pick = [it for it in ver if it.get("base") not in used_bases][:1] or ver[:1]
        for it in pick:
            used_bases.add(it.get("base"))
            src = SITE / "curriculum" / "falls" / "img" / f"{it['id']}.jpg"
            if not src.exists():
                src = SITE / "curriculum" / "falls" / "thumb" / f"{it['id']}.jpg"
            if not src.exists():
                src = DATA / "curriculum" / "falls" / (it.get("thumb") or it.get("image") or "")
            img = copy(src, f"cur-{it['id']}.jpg")
        rooms = [it.get("room") for it in (ver or by_level.get(lvl, []))]
        wmatch = next((w for r_ in rooms for w in fall_worlds if r_ and w["scene_id"].startswith(r_)), None)
        media = '<span class="mchip">Image</span>' + (f'<a class="mchip m3" href="world.html?id={esc(wmatch["scene_id"])}">3D →</a>' if wmatch else "")
        ph = f'<div class="stimg"><img src="{img}" alt=""></div>' if img else '<div class="stimg none"></div>'
        cards.append(f'<div class="stp" style="min-height:{330 + k * 40}px">{ph}<div class="slv">L{lvl}</div><h4>{esc(L.get("name", ""))}</h4>'
                     f'<p>{esc(LINE.get(lvl, ""))}</p>'
                     f'<div class="srow"><span class="k">Hazards</span>{pips(L.get("hazards_per_image"), "h")}</div>'
                     f'<div class="srow"><span class="k">Look-alikes</span>{pips(L.get("distractors"), "d")}</div>'
                     f'<div class="srow"><span class="k">Conditions</span><span>{esc(COND.get(lvl, ", ".join(L.get("conditions", []))))}</span></div>'
                     f'<div class="media">{media}</div></div>')
    diff = f'<div class="stair2">{"".join(cards)}</div>'
    diff_p = ""

# 3D strip under the curriculum
w3strip = []
for w in [w for w in WORLDS.values() if w.get("status") == "done" and w.get("bench") == "falls"][:6]:
    t = copy(DATA / "worlds" / f"{w['scene_id']}.thumb.jpg", f"world-{w['scene_id']}.jpg")
    if t:
        w3strip.append(f'<a href="world.html?id={esc(w["scene_id"])}"><img src="{t}" alt=""><span>{esc(w.get("hazard_id", ""))} · Walk in 3D →</span></a>')

# ---------------------------------------------------------------- 6 worlds
walked = set(WALK.get("worlds", {}).keys())
wcards = []
wl = sorted([w for w in WORLDS.values() if w.get("status") == "done"],
            key=lambda w: (w.get("scene_id") not in walked, w.get("bench") != "falls"))[:4]
for w in wl:
    wid = w.get("scene_id")
    th = copy(DATA / "worlds" / f"{wid}.thumb.jpg", f"world-{wid}.jpg")
    per = [r for r in WALK.get("runs", []) if r["scene"] == wid and r.get("mode") != "live"]
    res = f"AI walkers: {sum(1 for r in per if r.get('metrics', {}).get('found'))}/{len(per)} found it" if per else "Agent walk: pending"
    bench = "Falls · CDC STEADI" if w.get("bench") == "falls" else "Dementia · Alz. Assoc./NIA"
    wcards.append(f'''<div class="appwin wc"><div class="ph">{f'<img src="{th}" alt="">' if th else ''}<span class="chipk ck-live">{esc(bench)}</span></div>
      <div class="bd"><h4>{esc(w.get('title', wid))}</h4><p><span class="tag">{esc(w.get('hazard_id', ''))}</span> {esc(w.get('hazard', ''))}</p>
      <div class="bt"><a class="btn pri sm" href="world.html?id={esc(wid)}">Walk in 3D</a>{f'<a class="btn sm" href="walk.html?w={esc(wid)}">Watch the AI walk it</a>' if wid in walked else ''}</div></div></div>''')
worlds_p = f"{n_worlds} photoreal 3D homes generated from the same labelled scenes; hazard locations carried into 3D so an agent's gaze can be scored."

# ---------------------------------------------------------------- 7 library
def bench_stats(b, results):
    m = CUR.get(b, {})
    return (len(m.get("rubric", [])), sum(1 for s in results.get("scenes", []) if is_verified(s)),
            sum(1 for w in WORLDS.values() if w.get("bench") == b and w.get("status") == "done"),
            len(results.get("leaderboard", [])))


def lib_img(results, prefer):
    sc = [x for x in results.get("scenes", []) if x.get("verified") and x.get("image")]
    sc = [x for x in sc if x["id"] == prefer] or sc
    return copy(SITE / sc[0]["image"], "lib-" + Path(sc[0]["image"]).name) if sc else None


LIVE = [("Post-op fall prevention", '<img src="home-assets/cdc-logo.svg" alt="CDC" onerror="this.remove()"><span class="tb"><b>CDC</b> STEADI</span>',
         "Check for Safety, compiled into labelled homes where a missing grab bar or a cluttered stair is the test.",
         "guideline-falls.html", lib_img(R, "stairs-base0-STAIR-03")),
        ("Dementia home safety", '<span class="tb">Alzheimer\'s Association / NIA</span>',
         "Wandering exits, medications left out and floors that read as holes, judged the way a caregiver would.",
         "guideline-dementia.html", lib_img(DEM, "dem-kitchen-base0-DEM-K04"))]
cards = "".join(f'<a class="appwin lcard" href="{href}"><div class="lim">{f"<img src={chr(34)}{img}{chr(34)} alt>" if img else ""}</div>'
                f'<div class="lbd"><span class="chipk ck-live" style="align-self:flex-start">Simulator live</span><h3>{esc(name)}</h3>'
                f'<div class="lsrc">{badge}</div><p>{esc(desc)}</p><span class="btn pri">Open the simulator →</span></div></a>'
                for name, badge, desc, href, img in LIVE)
nexts = "".join(f'<div><span class="chipk ck-nx">Next</span><b>{esc(n)}</b><span class="s">{esc(src)}</span></div>'
                for n, src in [("Pressure injuries", "NPIAP"), ("Medication safety", "AHRQ / ISMP"),
                               ("Pediatric home injury", "AAP"), ("Smoke & CO alarms", "NFPA 72")])
lib = [f'<div class="lcat">{cards}</div><div class="lnext">{nexts}</div>']

# ---------------------------------------------------------------- 9 counts
models = {m["model"] for m in LB} | {m["model"] for m in DEM.get("leaderboard", [])} | {r["model"] for r in WALK.get("runs", [])}
n_guides = sum(1 for b in CUR.values() if b.get("rubric"))
v_dem = sum(1 for s in DEM.get("scenes", []) if is_verified(s))
v_cur = sum(1 for m in CUR.values() for it in m.get("items", []) if it.get("verified"))
n_pred = sum(len(v) for v in R.get("predictions", {}).values()) + sum(len(v) for v in DEM.get("predictions", {}).values())
n_steps = sum(len(r.get("steps", [])) for r in WALK.get("runs", []))
n_rub = sum(len(b.get("rubric", [])) for b in CUR.values())
counts = [(len(models), "models tested"), (n_guides, "guidelines compiled"),
          (v_scenes + v_dem + v_cur, "labelled homes"), (n_worlds, "walkable 3D worlds")]
counts_html = "".join(f"<div><b>{n}</b><span>{esc(t)}</span></div>" for n, t in counts)
smalln = f"{v_scenes} falls scenes, {v_dem} dementia scenes, {len(std_worlds)} walk worlds per model"

# ---------------------------------------------------------------- hero 3D world
W3_ID = next((w for w in ("stairs-base0-STAIR-03", "living-base0-LIV-01") if WORLDS.get(w, {}).get("status") == "done"),
             next(iter(WORLDS), ""))
w3 = WORLDS.get(W3_ID, {})
w3_pano = None
pano_src = DATA / "worlds" / f"{W3_ID}.pano.png"
if pano_src.exists():
    dst = ASSETS / f"pano-{W3_ID}.jpg"
    if not dst.exists() or dst.stat().st_mtime < pano_src.stat().st_mtime:
        from PIL import Image
        ASSETS.mkdir(parents=True, exist_ok=True)
        im = Image.open(pano_src).convert("RGB")
        im.thumbnail((1600, 1600))
        im.save(dst, quality=82)
    w3_pano = f"home-assets/pano-{W3_ID}.jpg"
w3_haz = f"{w3.get('hazard_id', '')} · {(w3.get('guideline') or {}).get('org', 'CDC STEADI')}" if w3 else ""
film_story = ""
if run:
    m = run.get("metrics", {})
    wd = WALK.get("worlds", {}).get(run["scene"], {})
    film_story = (f"{pn(run['model'])} walked the {wd.get('title', run['scene']).lower()} for {len(run.get('steps', []))} steps. "
                  f"It pointed the camera at the {wd.get('hazard_name', 'hazard').lower()} and flagged {len(m.get('flags', []))} other things "
                  f"(grab bars, toilet height, tub floor, a towel bar), none of them the seeded hazard. It knows what's in the room. "
                  f"It doesn't know what matters.")

# ---------------------------------------------------------------- leaderboard (full)
PROV = [("claude", "Anthropic"), ("gpt", "OpenAI"), ("kimi", "Moonshot"), ("grok", "xAI"), ("nova", "Amazon"), ("llama", "Meta"),
        ("qwen", "Alibaba"), ("mistral", "Mistral"), ("gemma", "Google"), ("nemotron", "NVIDIA")]
prov = lambda m: next((v for k, v in PROV if m.startswith(k)), "")
rows = []
for i, m in enumerate(LB, 1):
    fa = m.get("false_alarm", 0)
    fac = "hi" if fa >= .35 else "md" if fa >= .2 else "lo"
    rows.append(f'<tr class="{"top1" if i == 1 else ""}"><td class="rk">{i}</td><td class="mn">{esc(pn(m["model"]))}</td><td><span class="pv">{esc(prov(m["model"]))}</span></td>'
                f'<td class="scc"><div class="sc"><b>{m.get("score", 0):.2f}</b><div class="sbar"><i style="width:{100*m.get("score",0):.0f}%"></i></div></div></td>'
                f'<td class="r">{pct(m.get("recall", 0))}</td><td class="fa {fac}">{pct(fa)}</td></tr>')
lb_full = ('<table class="lbf"><thead><tr><th>#</th><th>Model</th><th>Provider</th><th>Score</th><th>Recall</th><th>False alarms</th></tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table>')
lb_line = f"{len(LB)} models on {v_scenes} verified scenes. Score blends recall and false alarms."

# ---------------------------------------------------------------- render
sub = {
    "FILM_TITLE": esc(film_title), "FILM_MODEL": esc(film_model), "FILM_END": esc(film_end),
    "FILM_IMGS": "".join(film_imgs), "FILM_STORY": esc(film_story), "FILM_SCENE": esc(run["scene"] if run else ""),
    "W3_ID": esc(W3_ID), "W3_TITLE": esc(f"{w3.get('title', W3_ID)} · {W3_ID}"), "W3_HAZ": esc(w3_haz), "W3_PANO": w3_pano or "art/bg-stairs.jpg", "FILM_TICKS": "".join(ticks), "FILM_JSON": json.dumps(film),
    "HOW": how or '<div class="note">No verified scene available.</div>',
    "FIND_EYEBROW": esc(find_eyebrow), "LB": lb_html, "LB_NOTE": esc(lb_note), "HARD": "".join(hard_rows),
    "WALKS": walks_html, "WALK_CALLOUT": walk_callout,
    "DIFF_H": esc(diff_h), "CURVE": curve_html, "W3STRIP": "".join(w3strip), "DIFF_P": diff_p, "DIFF": diff,
    "WORLDS": "".join(wcards), "WORLDS_P": esc(worlds_p), "LIB": "".join(lib),
    "COUNTS": counts_html, "LB_FULL": lb_full, "LB_LINE": esc(lb_line), "SMALLN": esc(smalln), "FOOT": "built at the Healthcare AI Hackathon, AWS Builder Loft, San Francisco, September 26, 2026.",
}
out = TEMPLATE.read_text()
for k, v in sub.items():
    out = out.replace("{{" + k + "}}", str(v))
left = re.findall(r"\{\{[A-Z_]+\}\}", out)
(SITE / "home.html").write_text(out)
print(f"wrote site/home.html ({len(out)//1024} KB); unfilled: {left or 'none'}")
