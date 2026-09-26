"""HomeDojo "brief in -> benchmark out" live demo.

Run:  .venv/bin/python -m uvicorn src.brief_server:app --host 0.0.0.0 --port 8791

Stages (streamed to the page over SSE):
  1 BRIEF   use case + guideline (text / URL / PDF) + customer model
  2 RUBRIC  Claude Sonnet 5 (Bedrock) compiles the guideline into rubric rows (hazard_taxonomy.json schema)
  3 SCENES  for 1-2 approved rows: Sonnet writes the label (box + edit plan) FIRST, then Stability (Bedrock)
            paints it into a clean base render; diff_box + Sonnet judge verify. Fallback: cached data/scenes edit.
  4 SCORE   customer model + 4 reference models on edit + clean base; hit / miss / false alarm.
Runs are saved to data/briefs/<run_id>.json and can be replayed instantly.
"""
import base64, io, json, os, re, sys, threading, time, uuid, pathlib, asyncio, concurrent.futures as cf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dotenv import load_dotenv
from common import ROOT, DATA, SCENES, RENDERS, taxonomy

load_dotenv(ROOT / ".env", override=True)
if os.getenv("AWS_ACCESS_KEY_ID"):
    os.environ.pop("AWS_PROFILE", None)

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw

import run_models as rm
from verify import diff_box, Q as JUDGE_Q

TAX = taxonomy()
BRIEFS = DATA / "briefs"
BRIEFS.mkdir(parents=True, exist_ok=True)
STATIC = pathlib.Path(__file__).resolve().parent / "brief"
RUBRIC_MODEL = "us.anthropic.claude-sonnet-5"
ROOMS = ["bathroom", "bedroom", "stairs", "kitchen", "living", "entry"]
GEN_DEADLINE = 60

# label -> (bedrock model id, supports temperature)
MODELS = {
    "nova-2-lite": ("us.amazon.nova-2-lite-v1:0", True),
    "claude-sonnet-5": ("us.anthropic.claude-sonnet-5", False),
    "claude-haiku-4.5": ("us.anthropic.claude-haiku-4-5-20251001-v1:0", True),
    "gpt-5.6-sol": ("us.openai.gpt-5.6-sol", False),
    "grok-4.6": ("us.xai.grok-4.6", False),
    "kimi-k3": ("us.moonshotai.kimi-k3", False),
    "nova-pro": ("amazon.nova-pro-v1:0", True),
    "qwen3-vl": ("qwen.qwen3-vl-235b-a22b", True),
    "llama-4-maverick": ("us.meta.llama4-maverick-17b-instruct-v1:0", True),
}
REFERENCE = ["claude-sonnet-5", "gpt-5.6-sol", "qwen3-vl", "llama-4-maverick", "claude-haiku-4.5"]

SAMPLE = {
    "customer": "Acme Health",
    "use_case": "Assess whether a home is safe for a walker user discharged after hip replacement",
    "model": "nova-2-lite",
    "guideline": """Home Safety Check: Stairs and Bathroom
Adapted from CDC STEADI 'Check for Safety' (public domain)

STAIRS AND STEPS
- Nothing should be left on the steps: pick up shoes, books, bags and anything else you could trip on.
- Any step that is broken, loose or uneven must be repaired.
- There should be a light over the staircase, with a switch you can reach at the top and at the bottom.
- Handrails should be firmly attached on both sides of the stairs and run the whole length of the stairway.
- Carpet on the stairs must be tight to every step; remove it or tack it down if it is loose or torn.

BATHROOM
- The floor of the tub or shower needs a non-slip mat or adhesive safety strips.
- Grab bars should be installed inside the tub or shower and beside the toilet to help you get in, out, up and down.
- Small bath rugs that slide or have curled edges should be removed, or replaced with rugs that have a non-skid backing.
- Keep a night light on so the path to the bathroom is visible at night.
- A raised toilet seat or a toilet safety frame makes it easier to sit and stand, especially after hip surgery.""",
}

_bedrock = None
_lock = threading.Lock()


def bedrock():
    global _bedrock
    with _lock:
        if _bedrock is None:
            import boto3
            from botocore.config import Config
            _bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"),
                                    config=Config(read_timeout=120, retries={"max_attempts": 2}, max_pool_connections=40))
    return _bedrock


def converse(model_id, content, temp=False, max_tokens=3000):
    cfg = {"maxTokens": max_tokens}
    if temp:
        cfg["temperature"] = 0
    r = bedrock().converse(modelId=model_id, messages=[{"role": "user", "content": content}], inferenceConfig=cfg)
    return "".join(b.get("text", "") for b in r["output"]["message"]["content"])


def jpeg_bytes(path, side=1280):
    im = Image.open(path).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def first_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


# ---------------------------------------------------------------- run state / SSE
class Run:
    def __init__(self, rid, brief, replay=False):
        self.id, self.brief, self.replay = rid, brief, replay
        self.t0 = time.time()
        self.events, self.rows, self.scenes = [], [], []
        self.approved = threading.Event()
        self.approval = None
        self.timings = {}

    def emit(self, type_, **data):
        ev = {"type": type_, "t": round(time.time() - self.t0, 2), **data}
        self.events.append(ev)
        return ev

    def save(self):
        out = {"id": self.id, "brief": self.brief, "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
               "timings": self.timings, "events": self.events}
        (BRIEFS / f"{self.id}.json").write_text(json.dumps(out, indent=1))


RUNS: dict[str, Run] = {}
POOL = cf.ThreadPoolExecutor(32)


# ---------------------------------------------------------------- stage 1: guideline ingest
def html_to_text(html):
    html = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<(br|p|li|h\d|div|tr)[^>]*>", "\n", html)
    txt = re.sub(r"<[^>]+>", " ", html)
    import html as h
    txt = h.unescape(txt)
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in txt.splitlines()]
    return "\n".join(l for l in lines if len(l) > 2)


def ingest(text, url, pdf_bytes):
    src = "text"
    if pdf_bytes:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((p.extract_text() or "") for p in r.pages[:20])
        src = f"pdf ({len(r.pages)} pages)"
    elif url and not (text or "").strip():
        import httpx
        resp = httpx.get(url, follow_redirects=True, timeout=20, headers={"User-Agent": "Mozilla/5.0 HomeDojo/0.1"})
        if url.lower().endswith(".pdf") or "pdf" in resp.headers.get("content-type", ""):
            return ingest("", "", resp.content)[0], f"url pdf"
        text = html_to_text(resp.text)
        src = "url"
    text = (text or "").strip()
    if len(text) < 40:
        raise HTTPException(400, "Guideline is empty or too short")
    return text[:14000], src


# ---------------------------------------------------------------- stage 2: rubric
def rubric_prompt(brief, chunk, max_rows):
    ex = {"id": "BATH-03", "room": "bathroom", "name": TAX["BATH-03"]["name"], "visual_description": TAX["BATH-03"]["visual_description"],
          "detection_cues": TAX["BATH-03"]["detection_cues"][:3], "recommended_fix": TAX["BATH-03"]["recommended_fix"][:1]}
    existing = "\n".join(f"- {h['id']} ({h['room']}): {h['name']}" for h in TAX.values())
    return f"""You compile a customer's clinical guideline into a machine-checkable hazard rubric for a vision-model benchmark.

Customer use case: {brief['use_case']}

Guideline excerpt:
<<<
{chunk}
>>>

Write one rubric row per distinct, VISUALLY CHECKABLE hazard in this excerpt (a photo of one room could show it); at most {max_rows} rows. Skip advice no photo can show.
Row schema (example): {json.dumps(ex)}
Also include in every row:
"type": object | absence | measurement | lighting  (object = something present that should not be; absence = required safety item missing; measurement = a dimension is wrong; lighting = too dark / no light),
"severity_default": low | medium | high for this use case,
"post_op_modifier": one short sentence on how a walker user after hip replacement changes the risk,
"citation": the guideline line that justifies the row, copied EXACTLY (verbatim substring, without the leading dash),
"maps_to": closest id from the existing rubric below, or null,
"room": one of {ROOMS}.
Keep strings short. Use id prefixes BATH, BED, STAIR, KIT, LIV, ENT (numbers are reassigned later).

Existing rubric ids:
{existing}

Output JSON Lines: exactly one complete row object per line. No array, no markdown fences, no commentary."""


def chunks(text, n=3):
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) < 2:
        lines = text.splitlines()
        k = max(1, len(lines) // n + 1)
        paras = ["\n".join(lines[i:i + k]) for i in range(0, len(lines), k)]
    target = len(text) / n
    out, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > target * 1.3 and len(out) < n - 1:
            out.append(cur); cur = ""
        cur += p + "\n\n"
    if cur.strip():
        out.append(cur)
    # keep a leading title-only chunk attached to the next one
    if len(out) > 1 and len(out[0]) < 200:
        out[1] = out[0] + out[1]; out = out[1:]
    return out


_stream_client = None


def stream_rows(run, chunk, max_rows):
    global _stream_client
    if _stream_client is None:
        import boto3
        from botocore.config import Config
        _stream_client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"),
                                      config=Config(read_timeout=40, retries={"max_attempts": 1}, max_pool_connections=10))
    resp = _stream_client.converse_stream(modelId=RUBRIC_MODEL, messages=[{"role": "user", "content": [{"text": rubric_prompt(run.brief, chunk, max_rows)}]}],
                                          inferenceConfig={"maxTokens": 4000})
    buf = ""
    for ev in resp["stream"]:
        d = ev.get("contentBlockDelta", {}).get("delta", {}).get("text")
        if not d:
            continue
        buf += d
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            add_row(run, line)
    add_row(run, buf)


def stage_rubric(run: Run):
    run.emit("stage", stage="rubric", status="start", model="Claude Sonnet 5 (Bedrock)")
    t = time.time()
    parts = chunks(run.brief["guideline"])
    per = max(3, 12 // len(parts))
    futs = [POOL.submit(stream_rows, run, c, per) for c in parts]
    errs = []
    for f in futs:
        try:
            f.result(timeout=75)
        except Exception as e:
            errs.append(f"{type(e).__name__}: {str(e)[:120]}")
    if not run.rows:
        run.emit("error", stage="rubric", msg="rubric failed: " + "; ".join(errs))
        return
    run.timings["rubric_s"] = round(time.time() - t, 1)
    run.emit("stage", stage="rubric", status="done", secs=run.timings["rubric_s"], n=len(run.rows), chunks=len(parts), errors=errs)


PREFIX = {"bathroom": "BATH", "bedroom": "BED", "stairs": "STAIR", "kitchen": "KIT", "living": "LIV", "entry": "ENT"}


def add_row(run, line):
    line = line.strip().strip(",")
    if not line.startswith("{"):
        return
    try:
        row = json.loads(line)
    except Exception:
        return
    row["room"] = row.get("room") if row.get("room") in ROOMS else "bathroom"
    if row.get("maps_to") not in TAX:
        row["maps_to"] = None
    cit = (row.get("citation") or "").strip().strip('"')
    row["citation_verbatim"] = bool(cit) and cit[:60].lower() in run.brief["guideline"].lower()
    row["cached_scene"] = bool(cached_scene(row))
    im = (TAX.get(row["maps_to"]) or {}).get("instrument_map") or {}
    row["crosswalk"] = {k: im[k] for k in ("HOMEFAST", "CDC", "HSSAT") if im.get(k)}
    with _lock:
        pre = PREFIX[row["room"]]
        n = sum(1 for r in run.rows if r["id"].startswith(pre + "-")) + 1
        row["id"] = f"{pre}-{n:02d}"
        run.rows.append(row)
    run.emit("rubric_row", row=row)


# ---------------------------------------------------------------- stage 3: scenes
def cached_scene(row):
    hid = row.get("maps_to")
    if not hid:
        return None
    for p in sorted(SCENES.glob(f"*-{hid}.json")):
        s = json.loads(p.read_text())
        if s.get("verified") and s.get("kind") == "edit":
            return s
    return None


FLOOR_BASE = {"bathroom": "bathroom-base1"}  # widest open-floor view for object hazards


def pick_base(row):
    if row.get("type") == "object" and row["room"] in FLOOR_BASE:
        return FLOOR_BASE[row["room"]]
    c = cached_scene(row)
    if c:
        return c["base"]
    for n in range(3):
        if (RENDERS / f"{row['room']}-base{n}.jpg").exists():
            return f"{row['room']}-base{n}"
    return "bathroom-base0"


PLAN_Q = """This is a photo of a clean, safe {room}. We are building a benchmark image that contains exactly ONE fall hazard:
"{name}" - {desc} (hazard type: {type}).

Decide the ground-truth label BEFORE any pixels are edited. Return ONLY JSON:
{{"mode": "inpaint" | "search_replace",
  "box": [x0, y0, x1, y1],
  "prompt": "<photorealistic description of what the edited region should show>",
  "search_prompt": "<existing object to replace, only for search_replace>"}}
Rules:
- type absence (a safety item must be missing): use "search_replace"; search_prompt = the safety item visible in the photo in 1-3 plain words (e.g. "grab bar", "handrail", "night light"); prompt = what should be there instead (e.g. "bare tiled wall").
- otherwise use "inpaint": box = a region in 0-1000 normalized image coordinates (x right, y down) that is currently EMPTY floor/step/wall where the hazard should be painted, sized realistically (roughly 15-40% of the width), not covering existing furniture or fixtures. Floor objects (rugs, clutter, cords) go on OPEN VISIBLE FLOOR (not inside a tub or shower, not on a fixture); items on stairs go on a visible tread; the floor is usually the lowest part of the frame, so a floor box should reach down near the bottom of the visible floor; prompt describes the hazard object in place, matching the room's lighting and perspective.
- box for search_replace = where the item currently is."""


def stability(mode, img_png_b64, plan, size):
    if mode == "search_replace":
        body = {"image": img_png_b64, "search_prompt": plan.get("search_prompt") or "object", "prompt": plan["prompt"], "output_format": "png"}
        mid = "us.stability.stable-image-search-replace-v1:0"
    else:
        W, H = size
        x0, y0, x1, y1 = plan["box"]
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).rectangle([int(x0 / 1000 * W), int(y0 / 1000 * H), int(x1 / 1000 * W), int(y1 / 1000 * H)], fill=255)
        mb = io.BytesIO(); m.save(mb, "PNG")
        body = {"image": img_png_b64, "mask": base64.b64encode(mb.getvalue()).decode(), "prompt": plan["prompt"] + ", photorealistic, same lighting",
                "output_format": "png", "grow_mask": 8,
                "negative_prompt": "bathtub, clawfoot tub, furniture, toilet, sink, cabinet, text, people"}
        mid = "us.stability.stable-image-inpaint-v1:0"
    r = bedrock().invoke_model(modelId=mid, body=json.dumps(body))
    d = json.loads(r["body"].read())
    return base64.b64decode(d["images"][0])


def judge(base_path, edit_path, row):
    txt = converse(RUBRIC_MODEL, [
        {"image": {"format": "jpeg", "source": {"bytes": jpeg_bytes(base_path, 1024)}}},
        {"image": {"format": "jpeg", "source": {"bytes": jpeg_bytes(edit_path, 1024)}}},
        {"text": JUDGE_Q.format(name=row["name"], desc=row.get("visual_description", "")) +
         "\nBe strict: if the new object is a different kind of thing than the hazard described (e.g. furniture instead of a rug), or it is not where the hazard would realistically be, hazard_visible = false."}], max_tokens=800)
    return first_json(txt)


def generate_live(run, row, base_id):
    base_path = RENDERS / f"{base_id}.jpg"
    im = Image.open(base_path).convert("RGB")
    buf = io.BytesIO(); im.save(buf, "PNG")
    t = time.time()
    plan = first_json(converse(RUBRIC_MODEL, [
        {"image": {"format": "jpeg", "source": {"bytes": jpeg_bytes(base_path, 1024)}}},
        {"text": PLAN_Q.format(room=row["room"], name=row["name"], desc=row.get("visual_description", ""), type=row.get("type", "object"))}], max_tokens=600))
    if plan.get("mode") not in ("inpaint", "search_replace") or not plan.get("prompt"):
        raise RuntimeError("bad plan")
    if plan["mode"] == "inpaint":
        plan["box"] = [max(0, min(1000, int(v))) for v in plan["box"][:4]]
    run.emit("scene_label", row_id=row["id"], plan=plan, secs=round(time.time() - t, 1))
    png = stability(plan["mode"], base64.b64encode(buf.getvalue()).decode(), plan, im.size)
    d = BRIEFS / run.id
    d.mkdir(exist_ok=True)
    dest = d / f"{row['id']}.png"
    dest.write_bytes(png)
    return dest, plan


def stage_scene(run, row):
    base_id = pick_base(row)
    base_path = RENDERS / f"{base_id}.jpg"
    run.emit("scene_start", row_id=row["id"], name=row["name"], base=f"/data/renders/{base_id}.jpg", base_id=base_id)
    t = time.time()
    fut = POOL.submit(generate_live, run, row, base_id)
    cached, plan, err = False, None, None
    try:
        edit_path, plan = fut.result(timeout=GEN_DEADLINE)
        edit_url = f"/data/briefs/{run.id}/{edit_path.name}"
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:160]}"
        c = cached_scene(row)
        if not c:
            run.emit("scene_failed", row_id=row["id"], msg=err)
            return None
        cached = True
        edit_path, base_path, base_id = DATA / c["image"], RENDERS / f"{c['base']}.jpg", c["base"]
        edit_url = f"/data/{c['image']}"
    gen_s = round(time.time() - t, 1)
    run.emit("scene_edit", row_id=row["id"], edit=edit_url, base=f"/data/renders/{base_id}.jpg", cached=cached, secs=gen_s,
             backend="cached data/scenes" if cached else "Stability via Bedrock", note=err)
    # verify: pixel diff box + judge
    t2 = time.time()
    box, frac = diff_box(base_path, edit_path)
    jf = POOL.submit(judge, base_path, edit_path, row)
    if cached:
        c = cached_scene(row)
        box = c["hazards"][0].get("box") or box
        v = c.get("verify", {})
    else:
        try:
            v = jf.result(timeout=40)
        except Exception as e:
            v = {"hazard_visible": None, "note": f"judge error {str(e)[:80]}"}
    if not cached and v.get("hazard_visible") is False and cached_scene(row):
        c = cached_scene(row)
        run.emit("scene_rejected", row_id=row["id"], rejected=edit_url, note=v.get("note", ""))
        cached, plan = True, None
        edit_path, base_path, base_id = DATA / c["image"], RENDERS / f"{c['base']}.jpg", c["base"]
        edit_url = f"/data/{c['image']}"
        box = c["hazards"][0].get("box") or diff_box(base_path, edit_path)[0]
        v = c.get("verify", {})
        run.emit("scene_edit", row_id=row["id"], edit=edit_url, base=f"/data/renders/{base_id}.jpg", cached=True, secs=round(time.time() - t, 1),
                 backend="cached data/scenes", note="live edit rejected by judge")
    label_box = plan["box"] if plan and plan.get("mode") == "inpaint" else None
    gt_box = box or label_box
    scene = {"row_id": row["id"], "name": row["name"], "type": row.get("type"), "base_id": base_id,
             "base_path": str(base_path), "edit_path": str(edit_path), "edit": edit_url, "base": f"/data/renders/{base_id}.jpg",
             "cached": cached, "box": gt_box, "label_box": label_box, "changed_frac": round(frac, 4),
             "verified": v.get("hazard_visible"), "judge_note": v.get("note", ""), "gen_s": gen_s,
             "verify_s": round(time.time() - t2, 1)}
    run.emit("scene_verified", scene={k: v for k, v in scene.items() if not k.endswith("_path")})
    return scene


# ---------------------------------------------------------------- stage 4: score
def score_one(run, model, scene, which, checklist):
    mid, temp = MODELS[model]
    path = scene["edit_path"] if which == "edit" else scene["base_path"]
    prompt = rm.PROMPT.format(checklist=checklist)
    t = time.time()
    try:
        txt = converse(mid, [{"image": {"format": "jpeg", "source": {"bytes": jpeg_bytes(path)}}}, {"text": prompt}], temp=temp, max_tokens=3000)
        preds = rm.parse(txt)
        err = None
    except Exception as e:
        preds, err = [], f"{type(e).__name__}: {str(e)[:120]}"
    ids = [str(p.get("id")) for p in preds]
    rid = scene["row_id"]
    hit = rid in ids
    pbox = next((p.get("box") for p in preds if str(p.get("id")) == rid and isinstance(p.get("box"), list)), None)
    res = {"model": model, "row_id": rid, "which": which, "hit": hit, "ids": ids, "box": pbox,
           "latency": round(time.time() - t, 1), "error": err}
    run.emit("score_result", **res)
    return res


def stage_score(run, scenes):
    theirs = run.brief["model"]
    models = [theirs] + [m for m in REFERENCE if m != theirs][:4]
    run.emit("stage", stage="score", status="start", models=models, theirs=theirs)
    t = time.time()
    checklist = "\n".join(f"- {r['id']}: {r['name']}" for r in run.rows if r["id"] in (run.approval or {}).get("approved", [r["id"] for r in run.rows]))
    jobs = [POOL.submit(score_one, run, m, s, w, checklist) for m in models for s in scenes for w in ("edit", "base")]
    results = []
    for f in jobs:
        try:
            results.append(f.result(timeout=90))
        except Exception:
            pass
    board = []
    for m in models:
        rs = [r for r in results if r["model"] == m]
        e = [r for r in rs if r["which"] == "edit"]
        b = [r for r in rs if r["which"] == "base"]
        hits = sum(r["hit"] for r in e)
        fas = sum(r["hit"] for r in b)
        errs = sum(1 for r in rs if r["error"])
        score = (hits / max(1, len(e)) + 1 - fas / max(1, len(b))) / 2
        board.append({"model": m, "theirs": m == theirs, "hits": hits, "n": len(e), "false_alarms": fas, "n_clean": len(b),
                      "score": round(score, 3), "errors": errs, "latency": round(max([r["latency"] for r in rs] or [0]), 1)})
    board.sort(key=lambda r: (-r["score"], r["latency"]))
    run.timings["score_s"] = round(time.time() - t, 1)
    run.emit("leaderboard", rows=board)
    run.emit("stage", stage="score", status="done", secs=run.timings["score_s"])


def pipeline(run: Run):
    stage_rubric(run)
    if not run.rows:
        run.emit("done", ok=False)
        return
    run.emit("await_approval")
    run.approved.wait(timeout=1800)
    if not run.approval:
        return
    picked = [r for r in run.rows if r["id"] in run.approval["picked"]][:2]
    run.emit("stage", stage="scenes", status="start", picked=[r["id"] for r in picked])
    t = time.time()
    futs = [POOL.submit(stage_scene, run, r) for r in picked]
    scenes = [s for s in (f.result() for f in futs) if s]
    run.timings["scenes_s"] = round(time.time() - t, 1)
    run.emit("stage", stage="scenes", status="done", secs=run.timings["scenes_s"], n=len(scenes))
    if scenes:
        stage_score(run, scenes)
    run.timings["total_s"] = round(time.time() - run.t0, 1)
    run.emit("done", ok=bool(scenes), timings=run.timings)
    run.save()


# ---------------------------------------------------------------- replay
def replay(run: Run, saved):
    """Re-emit a saved run's events with compressed timing (demo safety net)."""
    evs = saved["events"]
    speed = {"rubric_row": 0.22, "scene_start": 0.5, "scene_label": 0.8, "scene_edit": 1.2, "scene_verified": 0.9,
             "score_result": 0.07, "leaderboard": 0.5, "await_approval": 0.3, "approve": 1.4}
    for ev in evs:
        time.sleep(speed.get(ev["type"], 0.35))
        e = dict(ev)
        e["replay"] = True
        run.events.append(e)


# ---------------------------------------------------------------- app
app = FastAPI(title="HomeDojo Brief -> Benchmark")
app.mount("/data", StaticFiles(directory=str(DATA)), name="data")
app.mount("/report", StaticFiles(directory=str(ROOT / "site"), html=True), name="report")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/sample")
def sample():
    return {**SAMPLE, "models": list(MODELS), "reference": REFERENCE}


@app.post("/api/brief")
async def brief(use_case: str = Form(...), model: str = Form("nova-2-lite"), customer: str = Form("Acme Health"),
                guideline: str = Form(""), url: str = Form(""), pdf: UploadFile | None = File(None)):
    pdf_bytes = await pdf.read() if pdf is not None and pdf.filename else None
    loop = asyncio.get_running_loop()
    text, src = await loop.run_in_executor(POOL, ingest, guideline, url, pdf_bytes)
    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    run = Run(rid, {"use_case": use_case, "customer": customer, "model": model if model in MODELS else "nova-2-lite",
                    "guideline": text, "guideline_source": src})
    RUNS[rid] = run
    run.emit("brief", brief={k: v for k, v in run.brief.items()}, chars=len(text))
    threading.Thread(target=pipeline, args=(run,), daemon=True).start()
    return {"run_id": rid}


@app.post("/api/run/{rid}/approve")
async def approve(rid: str, req: Request):
    run = RUNS.get(rid)
    if not run:
        raise HTTPException(404)
    body = await req.json()
    approved = [i for i in body.get("approved", []) if any(r["id"] == i for r in run.rows)]
    picked = [i for i in body.get("picked", []) if i in approved][:2]
    if not picked:
        raise HTTPException(400, "Pick 1-2 approved rows to render")
    run.approval = {"approved": approved, "picked": picked}
    run.emit("approve", approved=approved, picked=picked)
    run.approved.set()
    return {"ok": True}


@app.get("/api/run/{rid}/events")
async def events(rid: str, request: Request):
    run = RUNS.get(rid)
    if not run:
        raise HTTPException(404)

    async def gen():
        i = 0
        while True:
            if await request.is_disconnected():
                break
            while i < len(run.events):
                ev = run.events[i]
                i += 1
                yield f"data: {json.dumps(ev)}\n\n"
                if ev["type"] == "done":
                    return
            await asyncio.sleep(0.1)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/replays")
def replays():
    out = []
    for p in sorted(BRIEFS.glob("*.json"), reverse=True):
        try:
            d = json.loads(p.read_text())
            out.append({"id": d["id"], "saved": d.get("saved"), "use_case": d["brief"]["use_case"], "timings": d.get("timings")})
        except Exception:
            pass
    return out


@app.post("/api/replay")
async def start_replay(rid: str = Form("")):
    files = sorted(BRIEFS.glob("*.json"), reverse=True)
    p = BRIEFS / f"{rid}.json" if rid else (files[0] if files else None)
    if not p or not p.exists():
        raise HTTPException(404, "No saved runs yet")
    saved = json.loads(p.read_text())
    nid = "replay-" + uuid.uuid4().hex[:6]
    run = Run(nid, saved["brief"], replay=True)
    RUNS[nid] = run
    threading.Thread(target=replay, args=(run, saved), daemon=True).start()
    return {"run_id": nid, "source": saved["id"], "brief": saved["brief"]}
