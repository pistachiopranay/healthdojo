"""HealthDojo live walkthrough: watch a model look around a 360 home in real time, narrated.

Run:  .venv/bin/python -m uvicorn src.walk_live_server:app --host 0.0.0.0 --port 8792
GET /                         -> src/walk_live/gallery.html (pick a world + model)
GET /run                      -> src/walk_live/index.html (live / replay player)
GET /api/meta                 -> worlds (+GT), models, which saved traces exist
GET /api/episode?model=&world=&mode=live|replay   -> SSE: thinking / step / end events
Each step event: {step, action, view, thought, say, flag, view_jpg_url, audio_url, latency_s, grading}

TTS chain: ElevenLabs (eleven_flash_v2_5, mp3) -> macOS `say` (m4a) -> browser speechSynthesis (audio_url null).
Polly was AccessDenied on the workshop role. Public safety: 2 concurrent live runs, 10 live runs/IP/hour, replay unlimited.
Live traces are saved to data/walks/_live/<stamp>_<model>_<world>/ (same trace.json shape as walk.py).
"""
import concurrent.futures as cf, hashlib, json, os, re, subprocess, sys, threading, time, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import walk  # noqa: E402  (loads .env + event creds via run_models)
from walk import (BUDGET, START_YAW, FOV0, WALKS, WORLDS, MODELS, render, jpeg, parse_action, view_point_dir,
                  world_to_view, grade, gt, opus_call, checklist)
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: E402
from PIL import Image  # noqa: E402

STATIC = pathlib.Path(__file__).resolve().parent / "walk_live"
LIVE = WALKS / "_live"
TTS = WALKS / "_tts"
PANO_HI = WALKS / "_pano_hi"
for d in (LIVE, TTS, PANO_HI):
    d.mkdir(parents=True, exist_ok=True)
LIVE_MODELS = ["nova-pro", "qwen3-vl", "gpt-5.6-sol", "claude-sonnet-5", "claude-opus-5.5", "kimi-k3"]
REPLAY_ONLY = {"kimi-k3"}  # ~20 s/step on Bedrock: too slow to run live for the public


def _marble_gt():
    """MARBLE_GT_REGIONS from src/marble.py, parsed (not imported) so we don't pull its deps."""
    import ast
    tree = ast.parse((walk.ROOT / "src" / "marble.py").read_text())
    for n in tree.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "MARBLE_GT_REGIONS":
            return ast.literal_eval(n.value)
    return {}


for _k, _v in _marble_gt().items():  # in-process only; walk.py on disk is untouched
    walk.GT_REGIONS.setdefault(_k, _v)
_ALL = json.loads((WORLDS / "worlds.json").read_text())
WORLD_META = {k: v for k, v in _ALL.items()
              if not k.startswith("dem-") and k in walk.GT_REGIONS
              and (WORLDS / f"{k}.pano.png").exists() and (walk.SCENES / f"{k}.json").exists()}
ROOM_LABEL = {"stairs": "Staircase", "bathroom": "Bathroom", "living": "Living room", "bedroom": "Bedroom",
              "kitchen": "Kitchen", "entry": "Entryway"}


def room_of(scene):
    return ROOM_LABEL.get(json.loads((walk.SCENES / f"{scene}.json").read_text()).get("room", ""), "Room")


# ---------------- public safety ----------------
MAX_CONCURRENT_LIVE = 2
MAX_LIVE_PER_IP_HOUR = 10
_live_sem = threading.BoundedSemaphore(MAX_CONCURRENT_LIVE)
_ip_hits = {}


def client_ip(request):
    xf = request.headers.get("x-forwarded-for", "")
    return (xf.split(",")[0].strip() if xf else (request.client.host if request.client else "?")) or "?"


def allow_ip(ip):
    now = time.time()
    with _lock:
        hits = [t for t in _ip_hits.get(ip, []) if now - t < 3600]
        if len(hits) >= MAX_LIVE_PER_IP_HOUR:
            _ip_hits[ip] = hits
            return False
        hits.append(now)
        _ip_hits[ip] = hits
        return True
SAY_SUFFIX = ('\n\nAlso include a "say" key: ONE first-person sentence (max 20 words) a narrator will speak aloud, '
              'e.g. "Turning left to check the tub." or "I see a loose mat over the tub edge, flagging it."')

app = FastAPI(title="HealthDojo walkthrough live", docs_url=None, redoc_url=None, openapi_url=None)
_calls, _panos, _lock = {}, {}, threading.Lock()
TTS_STATE = {"engine": None}


def get_call(m):
    with _lock:
        if m not in _calls:
            _calls[m] = opus_call() if m == "claude-opus-5.5" else MODELS[m][0]()
        return _calls[m]


def get_pano(scene):
    with _lock:
        if scene not in _panos:
            _panos[scene] = walk.load_pano(scene)
        return _panos[scene]


# ---------------- TTS ----------------
def trim_say(text, n=20):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    first = re.split(r"(?<=[.!?])\s", text)[0]
    w = first.split()
    return " ".join(w[:n]).rstrip(",;:") + ("..." if len(w) > n else "")


def _polly(text, out):
    import boto3
    p = boto3.client("polly", region_name=os.getenv("AWS_REGION", "us-east-1"))
    r = p.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId="Matthew", Engine="neural")
    out.write_bytes(r["AudioStream"].read())


EL_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # ElevenLabs premade "George": warm, calm narrator
EL_MODEL = "eleven_flash_v2_5"


def _eleven(text, out):
    import urllib.request
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("no ElevenLabs key")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": EL_MODEL,
                         "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3}}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    b = urllib.request.urlopen(req, timeout=20).read()
    if len(b) < 1000:
        raise RuntimeError("short audio")
    out.write_bytes(b)


def _say(text, out):
    subprocess.run(["say", "-v", "Samantha", "-r", "185", "-o", str(out), "--file-format=m4af", "--data-format=aac", text],
                   check=True, capture_output=True, timeout=30)


def tts(text):
    """Returns /tts/<file> url or None (-> browser speechSynthesis)."""
    if not text:
        return None
    engines = [("eleven", "mp3", _eleven), ("say", "m4a", _say)]
    for name, ext, fn in engines:
        h = hashlib.sha1(f"{name}:{EL_VOICE}:{text}".encode()).hexdigest()[:16]
        out = TTS / f"{name}-{h}.{ext}"
        if out.exists():
            return f"/tts/{out.name}"
        try:
            fn(text, out)
            TTS_STATE["engine"] = name
            return f"/tts/{out.name}"
        except Exception as e:
            print("tts", name, "failed:", type(e).__name__, flush=True)
    return None


# ---------------- grading helpers ----------------
def running_grade(g, steps):
    """Grade the episode so far on copies; returns (metrics, last step's correctness)."""
    tr = {"steps": [dict(s, action=dict(s["action"])) for s in steps]}
    m = grade(tr, g)
    return m, tr["steps"][-1].get("correct")


def sse(obj):
    return f"data: {json.dumps(obj)}\n\n"


def step_event(rec, d_url, g, steps, say):
    a = rec["action"]
    flag = None
    m, correct = running_grade(g, steps)
    if a.get("action") == "flag":
        flag = {"hazard_id": a.get("hazard_id"), "evidence": a.get("evidence"), "dir": rec.get("flag_dir"),
                "correct": bool(correct), "name": walk.TAX.get(str(a.get("hazard_id")), {}).get("name")}
    if a.get("action") in ("error", "invalid"):
        a = {"action": a.get("action"), "raw": "model returned no usable action"}
    return {"type": "step", "step": rec["step"], "action": a, "view": rec["view"], "thought": rec["thought"], "say": say,
            "flag": flag, "view_jpg_url": d_url + rec["img"], "audio_url": tts(say), "latency_s": rec.get("latency_s"),
            "grading": m}


def fallback_say(a, thought):
    act = a.get("action")
    if act == "flag":
        return trim_say(thought, 16).rstrip(".") + ". Flagging it." if thought else trim_say(f"I see {walk.TAX.get(str(a.get('hazard_id')), {}).get('name', 'a hazard').lower()}. Flagging it.")
    if act == "done":
        return "I'm done with the walkthrough."
    return trim_say(thought)


# ---------------- episodes ----------------
def live_episode(model, scene):
    call = get_call(model)
    pano = get_pano(scene)
    g = gt(scene)
    stamp = time.strftime("%H%M%S")
    d = LIVE / f"{stamp}_{model}_{scene}"
    d.mkdir(parents=True, exist_ok=True)
    d_url = f"/walks/_live/{d.name}/"
    yaw, pitch, fov = START_YAW, 0.0, float(FOV0)
    steps, hist = [], []
    yield sse({"type": "start", "mode": "live", "model": model, "world": scene, "budget": BUDGET, "gt": g,
               "start": {"yaw": yaw, "pitch": pitch, "fov": fov}})
    for i in range(1, BUDGET + 1):
        img = render(pano, yaw, pitch, fov)
        name = f"step{i:02d}.jpg"
        img.save(d / name, quality=85)
        yield sse({"type": "thinking", "step": i, "view": {"yaw": yaw % 360, "pitch": pitch, "fov": fov}, "view_jpg_url": d_url + name})
        prompt = walk.PROMPT.format(budget=BUDGET, step=i, yaw=yaw % 360, pitch=pitch, fov=fov, checklist=checklist(),
                                    history="\n".join(hist) or "(none, this is your first view)") + SAY_SUFFIX
        t0 = time.time()
        text, err = "", None
        with cf.ThreadPoolExecutor(1) as ex:
            def attempt():
                t, e = "", None
                for k in range(3):
                    try:
                        t = call(jpeg(img), prompt)
                        if (t or "").strip():
                            return t, None
                        e = "empty response"
                    except Exception as ex_:
                        e = str(ex_)[:300]; time.sleep(2 * (k + 1))
                return t, e
            fut = ex.submit(attempt)
            while not fut.done():  # keep the SSE connection warm while the model thinks
                time.sleep(0.5)
                if not fut.done() and int(time.time() - t0) % 5 == 0:
                    yield ": keepalive\n\n"
            text, err = fut.result()
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
            ny, np_, nf = num("yaw", -720, 720, yaw) % 360, num("pitch", -60, 60, pitch), num("fov", 30, 90, fov)
            hist.append(f"step {i}: at yaw {yaw % 360:.0f} pitch {pitch:.0f} fov {fov:.0f} -> {act} to yaw {ny:.0f} pitch {np_:.0f} fov {nf:.0f}. Thought: {rec['thought'][:120]}")
            yaw, pitch, fov = ny, np_, nf
        elif act != "done":
            hist.append(f"step {i}: invalid response (must return one JSON action)")
        steps.append(rec)
        say = trim_say(a.get("say")) if a.get("say") else fallback_say(a, rec["thought"])
        rec["say"] = say
        ev = step_event(rec, d_url, g, steps, say)
        yield sse(ev)
        if act == "done":
            break
    tr = {"model": model, "scene": scene, "budget": BUDGET, "mode": "live", "start": {"yaw": START_YAW, "pitch": 0, "fov": FOV0}, "steps": steps}
    m = grade(tr, g)
    tr["metrics"] = m
    (d / "trace.json").write_text(json.dumps(tr, indent=1))
    yield sse({"type": "end", "metrics": m, "saved": str(d.relative_to(walk.ROOT))})


def replay_episode(model, scene):
    f = WALKS / model / scene / "trace.json"
    if not f.exists():
        yield sse({"type": "error", "message": f"no saved trace for {model} / {scene}"}); return
    tr = json.loads(f.read_text())
    g = gt(scene)
    d_url = f"/walks/{model}/{scene}/"
    says = [s.get("say") or fallback_say(s["action"], s["thought"]) for s in tr["steps"]]
    with cf.ThreadPoolExecutor(8) as ex:  # pre-warm TTS so replay is instant
        list(ex.map(tts, says))
    yield sse({"type": "start", "mode": "replay", "model": model, "world": scene, "budget": tr["budget"], "gt": g, "start": tr["start"]})
    steps = []
    for s, say in zip(tr["steps"], says):
        steps.append(s)
        ev = step_event(s, d_url, g, steps, say)
        ev["latency_s"] = s.get("latency_s")
        yield sse(ev)
    yield sse({"type": "end", "metrics": grade({"steps": [dict(s) for s in tr["steps"]]}, g), "saved": str(f.relative_to(walk.ROOT))})


# ---------------- routes ----------------
@app.get("/gallery")
def gallery():
    return FileResponse(STATIC / "gallery.html", headers={"Cache-Control": "no-store"})


@app.get("/")
def root():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/run")
def run_page():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/thumb/{scene}.jpg")
def thumb(scene: str):
    if scene not in WORLD_META:
        raise HTTPException(404)
    return FileResponse(WORLDS / f"{scene}.thumb.jpg")


@app.get("/static/{name}")
def static(name: str):
    p = (STATIC / name).resolve()
    if not str(p).startswith(str(STATIC)) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/meta")
def meta():
    worlds = {}
    for i, (s, w) in enumerate(WORLD_META.items(), 1):
        g = gt(s)
        worlds[s] = {"title": w["title"], "room": room_of(s), "label": f"Home {i} · {room_of(s)}", "hazard": w["hazard"],
                     "pano": f"/pano/{s}.jpg", "mini": f"/mini/{s}.jpg", "thumb": f"/thumb/{s}.jpg", **g}
    saved = {m: [s for s in WORLD_META if (WALKS / m / s / "trace.json").exists()] for m in LIVE_MODELS}
    return JSONResponse({"worlds": worlds, "models": LIVE_MODELS, "replay_only": sorted(REPLAY_ONLY), "saved": saved,
                         "budget": BUDGET, "limits": {"concurrent": MAX_CONCURRENT_LIVE, "per_ip_hour": MAX_LIVE_PER_IP_HOUR}})


@app.get("/mini/{scene}.jpg")
def mini(scene: str):
    if scene not in WORLD_META:
        raise HTTPException(404)
    p = WALKS / "_pano" / f"{scene}.jpg"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.open(WORLDS / f"{scene}.pano.png").convert("RGB").resize((1600, 800)).save(p, quality=85)
    return FileResponse(p)


@app.get("/pano/{scene}.jpg")
def pano(scene: str):
    if scene not in WORLD_META:
        raise HTTPException(404)
    p = PANO_HI / f"{scene}.jpg"
    if not p.exists():
        Image.open(WORLDS / f"{scene}.pano.png").convert("RGB").save(p, quality=90)
    return FileResponse(p)


@app.get("/walks/{path:path}")
def walks_file(path: str):
    p = (WALKS / path).resolve()
    if not str(p).startswith(str(WALKS.resolve())) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/tts/{name}")
def tts_file(name: str):
    p = (TTS / name).resolve()
    if not str(p).startswith(str(TTS.resolve())) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, media_type="audio/mpeg" if name.endswith(".mp3") else "audio/mp4")


def _guarded(gen, release=None):
    try:
        yield from gen
    except Exception as e:  # never leak a traceback to the client
        print("episode error:", type(e).__name__, str(e)[:200], flush=True)
        yield sse({"type": "error", "message": "Something went wrong on our side. Try replay."})
    finally:
        if release:
            release()


def _one(obj):
    yield sse(obj)


@app.get("/api/episode")
def episode(request: Request, model: str, world: str, mode: str = "live"):
    if model not in LIVE_MODELS or world not in WORLD_META or mode not in ("live", "replay"):
        raise HTTPException(400, "unknown model or world")
    hdr = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    if mode == "replay":
        return StreamingResponse(_guarded(replay_episode(model, world)), media_type="text/event-stream", headers=hdr)
    if model in REPLAY_ONLY:
        return StreamingResponse(_one({"type": "busy", "message": f"{model} is replay only (too slow to run live)."}), media_type="text/event-stream", headers=hdr)
    if not allow_ip(client_ip(request)):
        return StreamingResponse(_one({"type": "busy", "message": f"You've hit {MAX_LIVE_PER_IP_HOUR} live runs this hour. Try replay."}), media_type="text/event-stream", headers=hdr)
    if not _live_sem.acquire(blocking=False):
        with _lock:  # don't count a rejected attempt against the IP
            if _ip_hits.get(client_ip(request)):
                _ip_hits[client_ip(request)].pop()
        return StreamingResponse(_one({"type": "busy", "message": "Busy: two live runs are already going. Try replay, or retry in a minute."}), media_type="text/event-stream", headers=hdr)
    return StreamingResponse(_guarded(live_episode(model, world), _live_sem.release), media_type="text/event-stream", headers=hdr)
