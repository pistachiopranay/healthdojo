"""Spot the hazard -- humans vs models. Hackathon quiz on port 8793.

Scoring mirrors src/grade.py: recall on seeded hazards; false alarms on known-absent
hazards (hazards seeded into sibling edits of the same base room, verified absent here).
"""
import io, json, os, re, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from dotenv import load_dotenv

import qrcode, qrcode.image.svg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
RES = json.loads((ROOT / "data" / "results.json").read_text())
STATIC = Path(__file__).resolve().parent / "spot"
OUT = ROOT / "data" / "spot"; OUT.mkdir(parents=True, exist_ok=True)
RESP = OUT / "responses.jsonl"
load_dotenv(ROOT / ".env", override=True); os.environ.pop("AWS_PROFILE", None)
GRADER = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
CACHE_F = OUT / "grade_cache.json"
CACHE = json.loads(CACHE_F.read_text()) if CACHE_F.exists() else {}
LOCK = threading.Lock()
_br = None

# Fixed set, in play order: 8 verified edits spanning object/absence/measurement/lighting + 2 clean base rooms.
QUIZ = ["living-base1-LIV-02", "kitchen-base0", "bathroom-base0-BATH-01", "stairs-base1-STAIR-02",
        "bedroom-base0-BED-01", "living-base0", "bathroom-base0-BATH-03", "entry-base1-ENT-04",
        "stairs-base1-STAIR-06", "bathroom-base1-BATH-06"]

PLAIN = {
    "BATH-01": "No grab bar by the tub", "BATH-02": "Nothing to hold by the toilet",
    "BATH-03": "Something flimsy used as a grab bar", "BATH-04": "Slippery tub floor",
    "BATH-05": "High tub edge, no transfer bench", "BATH-06": "Toilet seat too low",
    "BATH-07": "Loose bath mat", "BATH-08": "No shower seat / handheld shower",
    "BED-01": "Bed too low or too high", "BED-02": "Can't reach a light from bed",
    "BED-03": "Dark path to the bathroom", "BED-04": "Clutter on the floor by the bed",
    "BED-05": "Too tight to get a walker around the bed",
    "STAIR-01": "Handrail missing (or only one side)", "STAIR-02": "Handrail loose, short, or hard to grip",
    "STAIR-03": "Stuff left on the stairs", "STAIR-04": "Stairs poorly lit",
    "STAIR-05": "Step edges hard to see / loose carpet", "STAIR-06": "Broken or uneven steps",
    "KIT-01": "Everyday items stored up high", "KIT-02": "Everyday items stored down low",
    "KIT-03": "Wobbly stool or chair for reaching", "KIT-04": "Slippery floor / loose mat",
    "LIV-01": "Loose rug in the walkway", "LIV-02": "Cord across the walkway",
    "LIV-03": "Cluttered or narrow path", "LIV-04": "Low, soft chair with no arms",
    "LIV-05": "Poor lighting or glare", "LIV-06": "Unmarked step between areas",
    "LIV-07": "Pet or pet stuff underfoot",
    "ENT-01": "Outside steps with no handrail", "ENT-02": "Raised door threshold",
    "ENT-03": "Cracked or uneven path", "ENT-04": "Entry too dark",
    "ENT-05": "Doorway too narrow for a walker",
}
TAX = RES["taxonomy"]
SCENES = {s["id"]: s for s in RES["scenes"]}
MODELS = [r["model"] for r in RES["leaderboard"]]


def scene_spec(sid):
    s = SCENES[sid]
    gt = {h["id"] for h in s["hazards"]}
    neg = set(RES["known_absent"].get(s.get("base") or sid, [])) - gt
    return s, gt, neg


ITEMS = []; ROOM_TAX = {}
for sid in QUIZ:
    s, gt, neg = scene_spec(sid)
    chips = [{"id": k, "label": PLAIN.get(k, v["name"]), "type": v["type"]} for k, v in TAX.items() if v["room"] == s["room"]]
    ROOM_TAX[sid] = chips
    ITEMS.append({"id": sid, "room": s["room"], "image": "/" + s["image"],
                  "clean": not gt, "answer": sorted(gt), "answer_label": [PLAIN[h] for h in sorted(gt)],
                  "hazard_type": s["hazards"][0]["type"] if gt else None})


def norm(text):
    return re.sub(r"[^a-z0-9 ]+", "", re.sub(r"\s+", " ", text.lower())).strip()


def grade_text(sid, text):
    """Map a player's free-text description to hazard ids from this room's taxonomy (Haiku on Bedrock, cached)."""
    global _br
    if not norm(text):
        return {"ids": [], "why": "No hazard described."}
    key = f"{sid}|{norm(text)}"
    if key in CACHE:
        return CACHE[key]
    opts = "\n".join(f'{c["id"]}: {TAX[c["id"]]["name"]} ({c["label"]})' for c in ROOM_TAX[sid])
    prompt = (f"A person looked at a photo of a {SCENES[sid]['room']} (home fall-safety check for an older adult using a walker) "
              f"and wrote what hazards they saw:\n\n\"\"\"{text[:600]}\"\"\"\n\nHazard checklist for this room:\n{opts}\n\n"
              "Map the person's text to the checklist ids they actually described. Be generous with paraphrase, synonyms and "
              "informal wording (e.g. 'towel rack isn't strong enough to hold' = non-load-rated fixture used as support; "
              "'no rail' = missing handrail). Do NOT add hazards they did not mention, and do not infer from the photo. "
              "Mentions that fit no checklist item are ignored. If they say it looks safe, return no ids.\n"
              'Reply with JSON only: {"ids": ["..."], "why": "one short line"}')
    try:
        if _br is None:
            _br = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        r = _br.converse(modelId=GRADER, messages=[{"role": "user", "content": [{"text": prompt}]}], inferenceConfig={"maxTokens": 200})
        raw = r["output"]["message"]["content"][0]["text"]
        j = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        valid = {c["id"] for c in ROOM_TAX[sid]}
        out = {"ids": [i for i in dict.fromkeys(j.get("ids", [])) if i in valid], "why": str(j.get("why", ""))[:200]}
    except Exception as e:  # don't cache failures
        return {"ids": [], "why": f"grader error: {type(e).__name__}", "error": True}
    with LOCK:
        CACHE[key] = out
        CACHE_F.write_text(json.dumps(CACHE, indent=1))
    return out


def grade(picks):
    """picks: {scene_id: [hazard ids]} -> totals + per-scene outcome."""
    tp = fn = fp = tn = 0; per = {}
    for sid in QUIZ:
        _, gt, neg = scene_spec(sid)
        p = set(picks.get(sid) or []) & set(TAX)
        hit = len(gt & p); tp += hit; fn += len(gt - p)
        f = len(neg & p); fp += f; tn += len(neg) - f
        per[sid] = {"hit": (hit == len(gt)) if gt else None, "false_alarms": f, "correct": (hit == len(gt) and f == 0) if gt else f == 0}
    recall = tp / max(1, tp + fn); fa = fp / max(1, fp + tn)
    return {"recall": round(recall, 3), "false_alarm": round(fa, 3), "score": round((recall + 1 - fa) / 2, 3),
            "tp": tp, "fn": fn, "fp": fp, "tn": tn, "per_scene": per}


MODEL_GRADES = {m: grade({sid: RES["predictions"].get(sid, {}).get(m, {}).get("pred", []) for sid in QUIZ}) for m in MODELS}


def load_humans():
    if not RESP.exists():
        return []
    rows = [json.loads(l) for l in RESP.read_text().splitlines() if l.strip()]
    for r in rows:
        r["grade"] = grade(r["picks"])
    return rows


def summary():
    humans = load_humans()
    avg = lambda xs: round(sum(xs) / len(xs), 3) if xs else None
    board = [{"name": m, "kind": "model", **{k: g[k] for k in ("score", "recall", "false_alarm")}} for m, g in MODEL_GRADES.items()]
    board += [{"name": h["name"], "kind": "human", "id": h["id"], **{k: h["grade"][k] for k in ("score", "recall", "false_alarm")}} for h in humans]
    board.sort(key=lambda r: (-r["score"], -r["recall"], r["kind"] != "human"))
    best = max(MODEL_GRADES.items(), key=lambda kv: kv[1]["score"])
    per_image = []
    for it in ITEMS:
        sid = it["id"]
        key = "correct" if it["clean"] else "hit"  # edit: spotted the seeded hazard; clean: no false alarm
        mh = [g["per_scene"][sid][key] for g in MODEL_GRADES.values()]
        hh = [h["grade"]["per_scene"][sid][key] for h in humans]
        per_image.append({"id": sid, "image": it["image"], "room": it["room"], "clean": it["clean"],
                          "answer": it["answer_label"], "type": it["hazard_type"],
                          "model_rate": avg(mh), "human_rate": avg(hh), "n_humans": len(hh)})
    stat = lambda gs, k: avg([g[k] for g in gs])
    hg = [h["grade"] for h in humans]; mg = list(MODEL_GRADES.values())
    return {"n_humans": len(humans), "n_models": len(mg),
            "humans": {"score": stat(hg, "score"), "recall": stat(hg, "recall"), "false_alarm": stat(hg, "false_alarm")},
            "models": {"score": stat(mg, "score"), "recall": stat(mg, "recall"), "false_alarm": stat(mg, "false_alarm")},
            "best_model": {"name": best[0], **{k: best[1][k] for k in ("score", "recall", "false_alarm")}},
            "per_image": per_image, "leaderboard": board}


def lan_url():
    try:
        ip = subprocess.run(["ipconfig", "getifaddr", "en0"], capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception:
        ip = ""
    return f"http://{ip or 'localhost'}:8793"


app = FastAPI()
app.mount("/renders", StaticFiles(directory=ROOT / "site" / "renders"), name="renders")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/quiz")
def quiz():
    # answers are revealed only on the results screen, but this is a party game -- fine to ship them.
    return {"items": ITEMS, "seconds": 20, "models": len(MODELS)}


@app.post("/api/submit")
async def submit(req: Request):
    body = await req.json()
    name = re.sub(r"\s+", " ", str(body.get("name", "")).strip())[:24]
    if not name:
        raise HTTPException(400, "name required")
    ans = body.get("answers", {}) or {}
    answers = {sid: {"text": str((ans.get(sid) or {}).get("text", ""))[:600], "safe": bool((ans.get(sid) or {}).get("safe"))} for sid in QUIZ}
    with ThreadPoolExecutor(10) as ex:
        graded = dict(zip(QUIZ, ex.map(lambda sid: {"ids": [], "why": "Tapped looks safe."} if answers[sid]["safe"] and not norm(answers[sid]["text"])
                                       else grade_text(sid, answers[sid]["text"]), QUIZ)))
    picks = {sid: graded[sid]["ids"] for sid in QUIZ}
    row = {"id": f"{int(time.time()*1000)}", "name": name, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "answers": answers, "graded": graded, "picks": picks, "timeouts": body.get("timeouts", []), "ua": req.headers.get("user-agent", "")[:120]}
    with RESP.open("a") as f:
        f.write(json.dumps(row) + "\n")
    g = grade(picks); s = summary()
    rank = next(i + 1 for i, r in enumerate(s["leaderboard"]) if r.get("id") == row["id"])
    models_beaten = sum(1 for m in MODEL_GRADES.values() if g["score"] > m["score"])
    labels = {k: PLAIN.get(k, v["name"]) for k, v in TAX.items()}
    return {"id": row["id"], "grade": g, "answers": answers, "graded": graded, "labels": labels,
            "known_absent": {sid: sorted(scene_spec(sid)[2]) for sid in QUIZ}, "rank": rank, "of": len(s["leaderboard"]), "models_beaten": models_beaten,
            "summary": s, "items": ITEMS, "model_grades": {m: {k: v[k] for k in ("score", "recall", "false_alarm")} for m, v in MODEL_GRADES.items()}}


@app.get("/api/results")
def results_json():
    return summary()


@app.get("/results")
def results(req: Request, format: str = ""):
    if format == "json" or "text/html" not in req.headers.get("accept", ""):
        return JSONResponse(summary())
    return FileResponse(STATIC / "results.html", headers={"Cache-Control": "no-store"})


@app.get("/api/qr.svg")
def qr():
    img = qrcode.make(lan_url(), image_factory=qrcode.image.svg.SvgPathImage, box_size=20, border=1)
    buf = io.BytesIO(); img.save(buf)
    return HTMLResponse(buf.getvalue().decode(), media_type="image/svg+xml")


@app.get("/api/url")
def url():
    return {"url": lan_url()}
