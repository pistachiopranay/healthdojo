"""Walkthrough mode: drop a vision model INTO a 360 home (equirect pano) and make it decide where to look.

Usage:
  .venv/bin/python src/walk.py run [model ...]      # run episodes (cached per model/world in data/walks/)
  .venv/bin/python src/walk.py build                # grade + write data/walks/index.json + site/walk.html
  .venv/bin/python src/walk.py gtcheck              # render the GT views for eyeballing

Geometry: pano is equirect, yaw 0 = image center column (the source photo's forward view), yaw +right,
pitch +up. Perspective views are gnomonic projections (bilinear) at (yaw, pitch, hfov), 768x576.

Ground truth: Marble re-generates the room around the source photo, so the photo does NOT map onto the
pano at a fixed fov (e.g. the staircase fills ~45% of the photo width but only ~45 deg of the pano), and
LIV-02 has no box. Projecting the scene box with an assumed 75 deg hfov is kept as `gt_box_proj`
for reference, but grading uses hand-annotated hazard regions in pano pixel coords (below), checked by
rendering views (`gtcheck`). A flag scores if its hazard_id matches and its direction is within
TOL deg (great-circle) of any GT region center (or inside region radius, if larger),
OR a GT region center falls inside the flagged box (padded by 50/1000).
"""
import io, json, math, os, re, sys, time, pathlib, concurrent.futures as cf
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run_models import MODELS, checklist, TAX  # loads .env + event creds
from common import ROOT, DATA, SCENES

WORLDS = DATA / "worlds"
WALKS = DATA / "walks"
W, H, FOV0 = 768, 576, 90
BUDGET = 8
TOL = 25.0
START_YAW = 180.0
SRC_HFOV = 75.0
RUN_MODELS = ["claude-sonnet-5", "gpt-5.6-sol", "nova-pro", "qwen3-vl", "kimi-k3", "claude-opus-5.5"]

# Hand-annotated GT regions, pixel coords on a 1280x640 downscale of the pano: (cx, cy, radius_deg, label)
GT_REGIONS = {
    "stairs-base0-STAIR-03": [(645, 372, 18, "sweater, books, shoes on treads"), (622, 298, 10, "laundry basket on upper treads")],
    "bathroom-base0-BATH-07": [(628, 432, 12, "crumpled mat over tub edge"),
                               (645, 565, 22, "loose bath rug on tile floor"),
                               (955, 515, 16, "loose bath rug by vanity")],
    "bedroom-base1-BED-04": [(655, 422, 20, "clothes, bag and box on floor by bed")],
    "living-base1-LIV-02": [(600, 385, 15, "power cord snaking across floor")],
}


def px_to_dir(x, y, w=1280, h=640):
    return (x / w - 0.5) * 360.0, (0.5 - y / h) * 180.0


def vec(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    return np.array([math.cos(p) * math.sin(y), math.sin(p), math.cos(p) * math.cos(y)])


def ang(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(vec(*a), vec(*b)))))))


def load_pano(scene):
    return np.asarray(Image.open(WORLDS / f"{scene}.pano.png").convert("RGB")).astype(np.float32)


def _rot(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(p), math.sin(p)], [0, -math.sin(p), math.cos(p)]])
    return Ry @ Rx  # camera (x right, y up, z fwd) -> world


def render(pano, yaw, pitch, fov, w=W, h=H):
    """Gnomonic perspective view from an equirect pano (bilinear)."""
    f = (w / 2) / math.tan(math.radians(fov) / 2)
    xs = np.arange(w) - w / 2 + 0.5
    ys = h / 2 - np.arange(h) - 0.5
    X, Y = np.meshgrid(xs, ys)
    d = np.stack([X, Y, np.full_like(X, f)], -1) @ _rot(yaw, pitch).T
    lon = np.arctan2(d[..., 0], d[..., 2])
    lat = np.arctan2(d[..., 1], np.hypot(d[..., 0], d[..., 2]))
    ph, pw = pano.shape[:2]
    u = (lon / (2 * np.pi) + 0.5) * pw - 0.5
    v = (0.5 - lat / np.pi) * ph - 0.5
    u0 = np.floor(u).astype(int); v0 = np.clip(np.floor(v).astype(int), 0, ph - 2)
    du = (u - u0)[..., None]; dv = np.clip(v - v0, 0, 1)[..., None]
    u0m, u1m = u0 % pw, (u0 + 1) % pw
    out = (pano[v0, u0m] * (1 - du) * (1 - dv) + pano[v0, u1m] * du * (1 - dv)
           + pano[v0 + 1, u0m] * (1 - du) * dv + pano[v0 + 1, u1m] * du * dv)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def view_point_dir(yaw, pitch, fov, bx, by, w=W, h=H):
    """0-1000 point in a view -> world (yaw, pitch)."""
    f = (w / 2) / math.tan(math.radians(fov) / 2)
    c = np.array([(bx / 1000 - 0.5) * w, (0.5 - by / 1000) * h, f])
    d = _rot(yaw, pitch) @ c
    return math.degrees(math.atan2(d[0], d[2])), math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))


def world_to_view(yaw, pitch, fov, ty, tp, w=W, h=H):
    """world direction -> 0-1000 coords in a view (None if behind camera)."""
    c = _rot(yaw, pitch).T @ vec(ty, tp)
    if c[2] <= 0:
        return None
    f = (w / 2) / math.tan(math.radians(fov) / 2)
    return (c[0] * f / c[2] / w + 0.5) * 1000, (0.5 - c[1] * f / c[2] / h) * 1000


def coverage(views, gw=180, gh=90):
    """Fraction of sphere area seen by any view (area-weighted grid)."""
    lon = (np.arange(gw) + 0.5) / gw * 2 * np.pi - np.pi
    lat = np.pi / 2 - (np.arange(gh) + 0.5) / gh * np.pi
    LON, LAT = np.meshgrid(lon, lat)
    D = np.stack([np.cos(LAT) * np.sin(LON), np.sin(LAT), np.cos(LAT) * np.cos(LON)], -1)
    seen = np.zeros(LON.shape, bool)
    for yaw, pitch, fov in views:
        c = D @ _rot(yaw, pitch)  # world -> camera coords
        tx = math.tan(math.radians(fov) / 2); ty = tx * H / W
        z = c[..., 2]
        seen |= (z > 0) & (np.abs(c[..., 0]) <= tx * z) & (np.abs(c[..., 1]) <= ty * z)
    wts = np.cos(LAT)
    return float((seen * wts).sum() / wts.sum())


def gt_box_proj(scene):
    """Reference only: scene box center projected assuming the source photo = forward view, SRC_HFOV wide."""
    s = json.loads((SCENES / f"{scene}.json").read_text())
    b = s["hazards"][0].get("box")
    if not b:
        return None
    return view_point_dir(0, 0, SRC_HFOV, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, 1536, 1024)


def gt(scene):
    s = json.loads((SCENES / f"{scene}.json").read_text())
    regs = [dict(zip(("yaw", "pitch"), px_to_dir(x, y)), r=r, label=l, px=[x, y]) for x, y, r, l in GT_REGIONS[scene]]
    return {"hazard_id": s["hazards"][0]["id"], "hazard_name": TAX[s["hazards"][0]["id"]]["name"], "regions": regs,
            "box_proj_75deg": gt_box_proj(scene)}


PROMPT = """You are a home-safety assessor doing a virtual walkthrough of a real home before an older adult comes home after hip or knee replacement surgery. They will be using a walker. You are standing in one spot and can turn your head to look around the room (360 degrees). You see ONE camera view at a time.

Your job: find the fall hazards in this home, efficiently. You have {budget} steps total; this is step {step} of {budget}.

Current view: yaw={yaw:.0f} deg (0..360, clockwise; yaw is absolute), pitch={pitch:.0f} deg (+up / -down), fov={fov:.0f} deg.

Hazard checklist (only use these ids):
{checklist}

History so far:
{history}

Choose exactly ONE action and return ONLY JSON, no prose:
{{"thought": "<one line: what you see and where you chose to look next and why>", "action": "turn", "yaw": <absolute yaw 0-360>}}
{{"thought": "...", "action": "look", "pitch": <-60..60>}}
{{"thought": "...", "action": "zoom", "fov": <30-90>}}
{{"thought": "...", "action": "flag", "hazard_id": "<id>", "evidence": "<what you see>", "box": [x0, y0, x1, y1]}}   (box in 0-1000 coords of the CURRENT view)
{{"thought": "...", "action": "done"}}
turn/look/zoom may also include the other camera keys (yaw, pitch, fov) to move in one step. Flag a hazard only when it is visible in the current view."""


def parse_action(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {"action": "invalid", "raw": (text or "")[:300]}
    s = m.group(0)
    for cand in (s, s[: s.rfind("}") + 1]):
        try:
            a = json.loads(cand)
            if isinstance(a, dict):
                return a
        except Exception:
            pass
    m2 = re.search(r"\{[^{}]*\"action\"[^{}]*\}", text, re.S)
    try:
        return json.loads(m2.group(0))
    except Exception:
        return {"action": "invalid", "raw": text[:300]}


def jpeg(img, q=85):
    b = io.BytesIO(); img.save(b, "JPEG", quality=q); return b.getvalue()


def episode(model, scene, call, pano):
    d = WALKS / model / scene
    f = d / "trace.json"
    if f.exists():
        return json.loads(f.read_text())
    d.mkdir(parents=True, exist_ok=True)
    yaw, pitch, fov = START_YAW, 0.0, float(FOV0)
    steps, hist = [], []
    ck = checklist()
    for i in range(1, BUDGET + 1):
        img = render(pano, yaw, pitch, fov)
        name = f"step{i:02d}.jpg"
        img.save(d / name, quality=85)
        prompt = PROMPT.format(budget=BUDGET, step=i, yaw=yaw % 360, pitch=pitch, fov=fov, checklist=ck,
                               history="\n".join(hist) or "(none, this is your first view)")
        t0 = time.time()
        text, err = "", None
        for attempt in range(3):
            try:
                text = call(jpeg(img), prompt); err = None
                if (text or "").strip():
                    break
                err = "empty response"  # e.g. Opus spending max_tokens on thinking; retry
            except Exception as e:
                err = str(e)[:300]; time.sleep(3 * (attempt + 1))
        a = parse_action(text) if (text or "").strip() else {"action": "error", "raw": err or "empty"}
        rec = {"step": i, "view": {"yaw": yaw % 360, "pitch": pitch, "fov": fov}, "img": name, "action": a,
               "thought": str(a.get("thought", ""))[:400], "latency_s": round(time.time() - t0, 1)}
        act = a.get("action")
        if act == "flag":
            box = a.get("box")
            try:
                bx, by = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            except Exception:
                bx, by = 500, 500
            rec["flag_dir"] = view_point_dir(yaw, pitch, fov, bx, by)
            hist.append(f"step {i}: at yaw {yaw % 360:.0f} pitch {pitch:.0f} flagged {a.get('hazard_id')} ({str(a.get('evidence', ''))[:80]})")
        elif act in ("turn", "look", "zoom"):
            def num(k, lo, hi, cur):
                try:
                    return max(lo, min(hi, float(a[k])))
                except Exception:
                    return cur
            ny = num("yaw", -720, 720, yaw) % 360
            np_ = num("pitch", -60, 60, pitch)
            nf = num("fov", 30, 90, fov)
            hist.append(f"step {i}: at yaw {yaw % 360:.0f} pitch {pitch:.0f} fov {fov:.0f} -> {act} to yaw {ny:.0f} pitch {np_:.0f} fov {nf:.0f}. Thought: {rec['thought'][:120]}")
            yaw, pitch, fov = ny, np_, nf
        elif act == "done":
            steps.append(rec); break
        else:
            hist.append(f"step {i}: invalid response (must return one JSON action)")
        steps.append(rec)
    tr = {"model": model, "scene": scene, "budget": BUDGET, "start": {"yaw": START_YAW, "pitch": 0, "fov": FOV0}, "steps": steps}
    f.write_text(json.dumps(tr, indent=1))
    print(model, scene, "done", len(steps), "steps", flush=True)
    return tr


def grade(tr, g):
    views = [(s["view"]["yaw"], s["view"]["pitch"], s["view"]["fov"]) for s in tr["steps"]]
    found_step, false_flags, flags = None, 0, []
    for s in tr["steps"]:
        if s["action"].get("action") != "flag":
            continue
        fd = s["flag_dir"]
        dist = min(ang(fd, (r["yaw"], r["pitch"])) - max(0, r["r"] - TOL) for r in g["regions"])
        hid = str(s["action"].get("hazard_id", ""))
        inbox = False
        box = s["action"].get("box")
        if isinstance(box, list) and len(box) == 4:
            v = s["view"]
            for r in g["regions"]:
                p = world_to_view(v["yaw"], v["pitch"], v["fov"], r["yaw"], r["pitch"])
                try:
                    inbox |= p is not None and box[0] - 50 <= p[0] <= box[2] + 50 and box[1] - 50 <= p[1] <= box[3] + 50
                except TypeError:
                    pass
        s["gt_in_box"] = inbox = bool(inbox)
        ok = hid == g["hazard_id"] and (dist <= TOL or inbox)
        s["correct"] = ok; s["gt_dist"] = round(dist, 1)
        flags.append(hid)
        if ok and found_step is None:
            found_step = s["step"]
        elif not ok:
            # a different real hazard id near nothing we seeded still counts as a false flag vs. seeded GT
            false_flags += 1
    def inview(v, r):
        q = world_to_view(v[0], v[1], v[2], r["yaw"], r["pitch"])
        return q is not None and 0 <= q[0] <= 1000 and 0 <= q[1] <= 1000
    seen_gt = bool(any(inview(v, r) for v in views for r in g["regions"]))
    return {"found": found_step is not None, "steps_to_find": found_step, "false_flags": false_flags,
            "coverage": round(coverage(views), 3), "saw_hazard": seen_gt, "flags": flags,
            "errors": sum(s["action"].get("action") in ("error", "invalid") for s in tr["steps"])}


def opus_call(model="claude-opus-5-5"):
    """Own Anthropic call: run_models' max_tokens=1500 sometimes yields empty text from Opus (budget spent before text)."""
    import anthropic, base64
    client = anthropic.Anthropic()
    def call(img_bytes, prompt):
        r = client.messages.create(model=model, max_tokens=6000, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode()}},
            {"type": "text", "text": prompt}]}])
        return "".join(b.text for b in r.content if b.type == "text")
    return call


def run(models):
    scenes = list(json.loads((WORLDS / "worlds.json").read_text()))
    panos = {s: load_pano(s) for s in scenes}
    jobs = []
    for m in models:
        factory, env, _ = MODELS[m]
        if not os.getenv(env):
            print("skip", m, "no", env); continue
        call = opus_call() if m == "claude-opus-5.5" else factory()
        jobs += [(m, s, call) for s in scenes]
    with cf.ThreadPoolExecutor(len(jobs) or 1) as ex:
        futs = [ex.submit(episode, m, s, c, panos[s]) for m, s, c in jobs]
        for fu in futs:
            try:
                fu.result()
            except Exception as e:
                print("ERR", e, flush=True)


def build():
    worlds = json.loads((WORLDS / "worlds.json").read_text())
    out = {"worlds": {}, "runs": [], "leaderboard": [], "tol_deg": TOL, "budget": BUDGET}
    for s, w in worlds.items():
        if s not in GT_REGIONS or not (SCENES / f"{s}.json").exists():
            continue  # walkthrough runs only cover HomeBench worlds with scene ground truth
        g = gt(s)
        out["worlds"][s] = {"title": w["title"], "hazard": w["hazard"], "pano": f"../data/walks/_pano/{s}.jpg", **g}
        (WALKS / "_pano").mkdir(parents=True, exist_ok=True)
        pj = WALKS / "_pano" / f"{s}.jpg"
        if not pj.exists():
            Image.open(WORLDS / f"{s}.pano.png").convert("RGB").resize((1600, 800)).save(pj, quality=85)
    for f in sorted(WALKS.glob("*/*/trace.json")):
        tr = json.loads(f.read_text())
        if tr["scene"] not in out["worlds"]:
            continue
        m = grade(tr, out["worlds"][tr["scene"]])
        tr["metrics"] = m
        tr["dir"] = f"../data/walks/{tr['model']}/{tr['scene']}/"
        out["runs"].append(tr)
    by = {}
    for r in out["runs"]:
        by.setdefault(r["model"], []).append(r["metrics"])
    for mdl, ms in by.items():
        fs = [m["steps_to_find"] for m in ms if m["found"]]
        out["leaderboard"].append({"model": mdl, "n": len(ms), "found": sum(m["found"] for m in ms),
                                   "found_rate": sum(m["found"] for m in ms) / len(ms),
                                   "avg_steps": round(sum(fs) / len(fs), 2) if fs else None,
                                   "false_flags": sum(m["false_flags"] for m in ms),
                                   "saw_but_missed": sum(m["saw_hazard"] and not m["found"] for m in ms),
                                   "coverage": round(sum(m["coverage"] for m in ms) / len(ms), 3)})
    out["leaderboard"].sort(key=lambda x: (-x["found_rate"], x["avg_steps"] or 99, x["false_flags"]))
    (WALKS / "index.json").write_text(json.dumps(out, indent=1))
    tpl = (ROOT / "src" / "walk_viewer.html").read_text()
    (ROOT / "site" / "walk.html").write_text(tpl.replace("/*__DATA__*/null", json.dumps(out)))
    for r in out["leaderboard"]:
        print(r)
    for r in out["runs"]:
        print(r["model"], r["scene"], r["metrics"])


def gtcheck():
    d = ROOT / ".scratch" / "walk"; d.mkdir(parents=True, exist_ok=True)
    for s in GT_REGIONS:
        pano = load_pano(s)
        g = gt(s)
        for k, r in enumerate(g["regions"]):
            render(pano, r["yaw"], r["pitch"], 60).save(d / f"gt_{s}_{k}.jpg")
        print(s, [(round(r["yaw"]), round(r["pitch"])) for r in g["regions"]], "box@75deg:", g["box_proj_75deg"])
        render(pano, 0, 0, 90).save(d / f"fwd_{s}.jpg")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "run":
        run(sys.argv[2:] or RUN_MODELS)
    elif cmd == "gtcheck":
        gtcheck()
    else:
        build()
