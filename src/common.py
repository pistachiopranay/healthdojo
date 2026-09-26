"""Shared helpers: paths, taxonomy, treg image generation."""
import json, subprocess, time, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RENDERS = DATA / "renders"
SCENES = DATA / "scenes"
RENDERS.mkdir(parents=True, exist_ok=True)
SCENES.mkdir(parents=True, exist_ok=True)

ABSENCE = {"BATH-01", "BATH-02", "BATH-08", "BED-02", "STAIR-01", "ENT-01"}
MEASURE = {"BATH-05", "BATH-06", "BED-01", "BED-05", "ENT-02", "ENT-05", "LIV-06"}
LIGHTING = {"BED-03", "STAIR-04", "LIV-05", "ENT-04"}


def hazard_type(hid):
    if hid in ABSENCE: return "absence"
    if hid in MEASURE: return "measurement"
    if hid in LIGHTING: return "lighting"
    return "object"


def taxonomy():
    d = json.loads((DATA / "hazard_taxonomy.json").read_text())
    return {h["id"]: h for h in d["hazards"]}


def _treg(args):
    out = subprocess.run(["treg", "call", *args], capture_output=True, text=True)
    body = out.stdout[out.stdout.find("{"):]
    return json.loads(body)


def gen_image_openai(prompt, dest, base_path=None, model="gpt-image-2"):
    """Generate or edit via OpenAI images API; returns a local path used as the 'url' for edits."""
    import base64, os
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv(ROOT / ".env")
    c = OpenAI()
    if base_path:
        with open(base_path, "rb") as f:
            r = c.images.edit(model=model, image=f, prompt=prompt, size="1536x1024", quality="medium")
    else:
        r = c.images.generate(model=model, prompt=prompt, size="1536x1024", quality="medium")
    pathlib.Path(dest).write_bytes(base64.b64decode(r.data[0].b64_json))
    return str(dest)


def gen_image(prompt, dest, image_urls=None, size="4:3", timeout=240):
    import os
    if os.getenv("IMAGE_BACKEND", "openai") == "openai":
        return gen_image_openai(prompt, dest, base_path=image_urls[0] if image_urls else None)
    return gen_image_treg(prompt, dest, image_urls, size, timeout)


def gen_image_treg(prompt, dest, image_urls=None, size="4:3", timeout=240):
    """Generate (or edit, if image_urls) one image via Gemini 3 Pro Image on treg; save to dest."""
    req = {"model": "gemini-3-pro-image-preview", "prompt": prompt, "size": size, "resolution": "1K"}
    if image_urls:
        req["image_urls"] = image_urls
    task = _treg(["reapi.image-gen.gemini-3-pro-image", "--method", "POST", "--data", json.dumps(req)])
    tid = task["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(6)
        r = _treg(["reapi.tasks.get", "--query", f"id={tid}"])
        if r.get("status") == "completed":
            print("task", tid, flush=True)
            url = r["output"]["image_urls"][0]
            req2 = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) HomeDojo/0.1"})
            pathlib.Path(dest).write_bytes(urllib.request.urlopen(req2, timeout=60).read())
            return url
        if r.get("status") == "failed":
            raise RuntimeError(f"task {tid} failed: {r.get('error')}")
    raise TimeoutError(tid)
