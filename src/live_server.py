"""HomeDojo live demo: "Check your own home".

Run:  .venv/bin/python -m uvicorn src.live_server:app --host 0.0.0.0 --port 8790
POST /check (multipart: image=<file>, model=<optional name>) ->
  {hazards:[{id,name,room,severity,severity_post_op,evidence,box,fix}], model, latency_ms, image}
"""
import base64, io, json, os, socket, sys, time, pathlib, concurrent.futures as cf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from PIL import Image, ImageOps

from common import ROOT, DATA, taxonomy
import run_models as rm  # reuse PROMPT / checklist() / parse()

load_dotenv(ROOT / ".env")
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:  # HEIC optional
    pass

TAX = taxonomy()
PROMPT = rm.PROMPT.format(checklist=rm.checklist())
MAX_SIDE = 1568
PORT = int(os.getenv("LIVE_PORT", "8790"))
STATIC = pathlib.Path(__file__).resolve().parent / "live"

# name (matches data/results.json leaderboard) -> (provider, model id, supports temperature)
MODELS = {
    "claude-sonnet-5": ("bedrock", "us.anthropic.claude-sonnet-5", False),
    "claude-opus-5": ("bedrock", "us.anthropic.claude-opus-5", False),
    "claude-opus-5.5": ("anthropic", "claude-opus-5-5", False),  # Bedrock marketplace access denied -> direct API
    "claude-haiku-4.5": ("bedrock", "us.anthropic.claude-haiku-4-5-20251001-v1:0", True),
    "nova-pro": ("bedrock", "us.amazon.nova-pro-v1:0", True),
    "nova-2-lite": ("bedrock", "us.amazon.nova-2-lite-v1:0", True),
    "pixtral-large": ("bedrock", "us.mistral.pixtral-large-2502-v1:0", True),
    "llama-4-maverick": ("bedrock", "us.meta.llama4-maverick-17b-instruct-v1:0", True),
    "qwen3-vl": ("bedrock", "qwen.qwen3-vl-235b-a22b", True),
}
if not os.getenv("ANTHROPIC_API_KEY"):
    MODELS.pop("claude-opus-5.5")

_bedrock = None
_anthropic = None


def _call(name, img_bytes):
    global _bedrock, _anthropic
    provider, mid, temp = MODELS[name]
    if provider == "bedrock":
        if _bedrock is None:
            import boto3
            from botocore.config import Config
            _bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"),
                                    config=Config(read_timeout=90, retries={"max_attempts": 2}))
        cfg = {"maxTokens": 2000}
        if temp:
            cfg["temperature"] = 0
        r = _bedrock.converse(modelId=mid, messages=[{"role": "user", "content": [
            {"image": {"format": "jpeg", "source": {"bytes": img_bytes}}}, {"text": PROMPT}]}], inferenceConfig=cfg)
        return "".join(b.get("text", "") for b in r["output"]["message"]["content"])
    if _anthropic is None:
        import anthropic
        _anthropic = anthropic.Anthropic()
    r = _anthropic.messages.create(model=mid, max_tokens=2000, messages=[{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode()}},
        {"type": "text", "text": PROMPT}]}])
    return "".join(b.text for b in r.content if b.type == "text")


def ranked_models():
    """Live-callable models in benchmark order (data/results.json leaderboard), then the rest."""
    try:
        lb = json.loads((DATA / "results.json").read_text())["leaderboard"]
        order = [row["model"] for row in lb]
        scores = {row["model"]: row.get("score") for row in lb}
    except Exception:
        order, scores = [], {}
    names = [m for m in order if m in MODELS] + [m for m in MODELS if m not in order]
    return names, scores


def default_model():
    env = os.getenv("LIVE_DEFAULT_MODEL")
    if env in MODELS:
        return env
    return ranked_models()[0][0]


def prep_image(raw):
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        raise HTTPException(400, f"Could not read image ({e.__class__.__name__}). Try JPEG/PNG/HEIC.")
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue(), img.size


def norm_box(box, size):
    """Model box (0-1000 normalized, sometimes pixels) -> [x0,y0,x1,y1] in 0-1, clamped. None if unusable."""
    try:
        x0, y0, x1, y1 = [float(v) for v in box[:4]]
    except Exception:
        return None
    w, h = size
    if max(x0, x1) > 1000 or max(y0, y1) > 1000:  # looks like pixel coords
        sx, sy = w, h
    elif max(x0, y0, x1, y1) <= 1.0:
        sx = sy = 1.0
    else:
        sx = sy = 1000.0
    b = [x0 / sx, y0 / sy, x1 / sx, y1 / sy]
    b = [min(1.0, max(0.0, v)) for v in b]
    b = [min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3])]
    if b[2] - b[0] < 0.01 or b[3] - b[1] < 0.01:
        return None
    if (b[2] - b[0]) * (b[3] - b[1]) > 0.85:  # whole-room issue; don't draw a frame-sized box
        return None
    return [round(v, 4) for v in b]


SEV = ["low", "medium", "high"]


def enrich(hazards, size):
    out, seen = [], set()
    for h in hazards:
        hid = str(h.get("id", "")).strip()
        t = TAX.get(hid)
        if not t or hid in seen:
            continue
        seen.add(hid)
        sev = str(h.get("severity", "medium")).lower()
        sev = sev if sev in SEV else "medium"
        esc = bool((t.get("post_op") or {}).get("escalate"))
        post = SEV[min(2, SEV.index(sev) + 1)] if esc else sev
        out.append({
            "id": hid, "name": t["name"], "room": t.get("room"), "severity": sev,
            "severity_post_op": post, "escalates": esc,
            "walker_note": (t.get("post_op") or {}).get("walker"),
            "evidence": h.get("evidence", ""),
            "box": norm_box(h["box"], size) if isinstance(h.get("box"), list) else None,
            "fix": t.get("recommended_fix") or [], "dme": t.get("dme") or [],
        })
    out.sort(key=lambda x: (-SEV.index(x["severity_post_op"]), -SEV.index(x["severity"])))
    return out


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


app = FastAPI(title="HomeDojo Live Check")
_pool = cf.ThreadPoolExecutor(8)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/models")
def models():
    names, scores = ranked_models()
    return {"default": default_model(), "models": [{"name": n, "score": scores.get(n)} for n in names],
            "lan_url": f"http://{lan_ip()}:{PORT}"}


@app.get("/qr.svg")
def qr():
    import qrcode, qrcode.image.svg
    img = qrcode.make(f"http://{lan_ip()}:{PORT}", image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@app.post("/check")
async def check(image: UploadFile = File(...), model: str = Form(None)):
    name = model if model in MODELS else default_model()
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "Empty upload")
    jpeg, size = prep_image(raw)
    t0 = time.time()
    try:
        import asyncio
        text = await asyncio.get_running_loop().run_in_executor(_pool, _call, name, jpeg)
    except Exception as e:
        # never echo credentials; botocore/anthropic messages don't include them
        return JSONResponse({"error": f"{name} failed: {str(e)[:300]}", "model": name}, status_code=502)
    latency = int((time.time() - t0) * 1000)
    hz = enrich(rm.parse(text), size)
    return {"hazards": hz, "model": name, "model_id": MODELS[name][1], "provider": MODELS[name][0],
            "latency_ms": latency, "image_size": list(size),
            "image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}
