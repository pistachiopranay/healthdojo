"""World Labs Marble: turn verified hazard images into walkable 3D showcase worlds.

API (verified 2026-09-26 against https://docs.worldlabs.ai/api/reference/worlds/generate.md):
  POST /marble/v1/worlds:generate   -> {operation_id, ...}
  GET  /marble/v1/operations/{id}   -> {done, error, response: World, metadata}
  GET  /marble/v1/worlds/{id}       -> World {world_id, world_marble_url, assets{thumbnail_url, imagery.pano_url, splats...}}
Auth header: WLT-Api-Key.

Usage:
  python src/marble.py credits
  python src/marble.py generate           # starts all SHOWCASE scenes in parallel, polls, saves data/worlds/
  python src/marble.py poll               # resume polling for pending ops in data/worlds/worlds.json
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
API = "https://api.worldlabs.ai/marble/v1"
OUT = ROOT / "data" / "worlds"
STATE = OUT / "worlds.json"
MODEL = "marble-1.1"

SHOWCASE = [
    {
        "scene_id": "stairs-base0-STAIR-03",
        "title": "Cluttered staircase",
        "hazard": "Objects on stairs: laundry basket, sweater, books and shoes left on the treads",
        "text_prompt": "Interior of a modest lived-in American home: a straight wooden staircase with handrails on both sides, "
        "a laundry basket, a sweater, a stack of books and sneakers left on the stair treads; living room to the left, kitchen to the right.",
    },
    {
        "scene_id": "bathroom-base0-BATH-07",
        "title": "Bathroom with loose bath mat",
        "hazard": "Loose bath mat draped over the tub edge onto a hard tile floor",
        "text_prompt": "Small lived-in bathroom of an older adult: tub-shower with grab bars and a shower chair, toilet safety frame, "
        "a loose crumpled bath mat hanging over the tub edge onto the beige tile floor.",
    },
    {
        "scene_id": "living-base1-LIV-02",
        "title": "Living room with cord across the walkway",
        "hazard": "Extension cord snaking across the main walking path",
        "showcase": False,  # generated, but Marble reduced the cord to a short stub near the TV: hazard not legible
        "text_prompt": "Bright living room of an older adult with hardwood floors, two recliners, a sofa, a TV stand, "
        "and a long black power cord running from the wall outlet across the open walkway in the middle of the floor.",
    },
    {
        "scene_id": "bedroom-base1-BED-04",
        "title": "Bedroom with floor clutter",
        "hazard": "Clothes, bag, shoes and an open box piled on the floor on the path from bed to door",
        "text_prompt": "Carpeted bedroom of an older adult: queen bed, wooden nightstand with lamp, dresser, doorway to a hallway; "
        "clothes, blankets, a leather handbag, sneakers and an open cardboard box scattered on the floor beside the bed, blocking the path to the door.",
    },
    # ---- 2026-09-26 batch 2: DementiaBench + falls rooms we lacked ----
    {
        "scene_id": "dem-bedroom-base0-DEM-R03", "bench": "dementia",
        "title": "Handgun on the nightstand",
        "hazard": "A handgun left in reach on the bedside nightstand",
        "text_prompt": "Carpeted bedroom of an older adult with a queen bed, dresser, corner cabinet, window with valance, and a wooden "
        "nightstand with a lamp; a black handgun lies on top of the nightstand beside the lamp.",
    },
    {
        "scene_id": "dem-bathroom-base0-DEM-B03", "bench": "dementia",
        "title": "Dark bath mat on a light floor",
        "hazard": "Solid black mat on light tile that can read as a hole in the floor",
        "text_prompt": "Bright bathroom with light beige tile floor, white tub with grab bars and a shower chair, toilet with a safety "
        "frame, vanity sink; a solid black bath mat lies on the light floor in front of the tub and toilet.",
    },
    {
        "scene_id": "dem-kitchen-base0-DEM-K04", "bench": "dementia",
        "title": "Medication bottles left out",
        "hazard": "Orange prescription bottles and pill containers out on the kitchen counter",
        "text_prompt": "Older American kitchen with wood cabinets, white refrigerator, black stove and dishwasher, open shelves of bowls; "
        "orange prescription pill bottles and pill containers sit openly on the counter left of the sink.",
    },
    {
        "scene_id": "dem-entry-base0-DEM-E02", "bench": "dementia",
        "title": "Back door left open to the outside",
        "hazard": "Glass back door standing open to the patio, an easy exit for wandering",
        "text_prompt": "Living room of an older adult with hardwood floors, two recliners, sofa, TV stand; at the back a glass-paned "
        "door stands wide open onto a sunny patio and garden outside.",
    },
    {
        "scene_id": "kitchen-base1-KIT-04", "bench": "falls",
        "title": "Kitchen runner with a curled corner",
        "hazard": "Unbacked runner mat at the sink with its near corner curled up",
        "text_prompt": "Galley kitchen of an older adult with open wood shelves of dishes, white lower cabinets, stainless fridge, "
        "doorway to a dining room; a thin unbacked runner mat on the wood floor in front of the sink with its corner curled up.",
    },
    {
        "scene_id": "living-base0-LIV-01", "bench": "falls",
        "title": "Living room rug with a lifted edge",
        "hazard": "Area rug in the central walkway with its front corner curled and lifted",
        "text_prompt": "Living room of an older adult with hardwood floors, a blue recliner, beige sofa, TV on a cabinet, china cabinet "
        "and bright window; a patterned area rug in the middle of the walkway with its front corner curled up.",
    },
    {
        "scene_id": "entry-base0-ENT-01", "bench": "falls",
        "title": "Entry steps without a handrail",
        "hazard": "Two concrete front steps with no handrail on either side",
        "text_prompt": "Front entry of a stone-and-siding house: a concrete walkway through shrubs and flower beds leads to two "
        "concrete steps up to a dark wooden front door with sidelights and a wall lantern; no handrail on either side of the steps.",
    },
    {
        "scene_id": "bedroom-base0-BED-01", "bench": "falls",
        "title": "Mattress on the floor",
        "hazard": "Bed is a mattress directly on the floor, far below knee height",
        "text_prompt": "Simple bedroom of an older adult with green carpet, white walls, a wooden nightstand with lamp, rocking chair, "
        "dresser and open door to a hallway; the bed is only a mattress lying directly on the floor.",
    },
]


def _meta(scene_id: str) -> dict:
    """bench / hazard_id / hazard_name / guideline for a scene id (additive worlds.json fields)."""
    dem = scene_id.startswith("dem-")
    hid = scene_id.split("-base", 1)[1].split("-", 1)[1]
    tax_p = ROOT / "data" / ("benchmarks/dementia/hazard_taxonomy.json" if dem else "hazard_taxonomy.json")
    h = {x["id"]: x for x in json.loads(tax_p.read_text())["hazards"]}.get(hid, {})
    if dem:
        c = h.get("citation") or {}
        src = c.get("source", "")
        org = "Alzheimer's Society (UK)" if "alzheimers.org.uk" in src else "Alzheimer's Association"
        guideline = {"org": org, "line": c.get("guideline_line"), "url": src}
    else:
        im = h.get("instrument_map") or {}
        guideline = {"org": "CDC STEADI", "line": f"Check for Safety: {im.get('CDC', '')}".strip(": "),
                     "url": "https://www.cdc.gov/steadi/pdf/STEADI-Brochure-CheckForSafety-508.pdf",
                     "also": {k: v for k, v in im.items() if k != "CDC"}}
    return {"bench": "dementia" if dem else "falls", "hazard_id": hid, "hazard_name": h.get("name"), "guideline": guideline}


def _image(scene_id: str) -> Path:
    if scene_id.startswith("dem-"):
        return ROOT / "data" / "benchmarks" / "dementia" / "renders" / f"{scene_id}.jpg"
    return ROOT / "data" / "renders" / f"{scene_id}.jpg"


def _headers() -> dict:
    key = os.environ.get("WORLDLABS_API_KEY")
    if not key:
        sys.exit("WORLDLABS_API_KEY missing from .env")
    return {"WLT-Api-Key": key, "Content-Type": "application/json"}


def _check(r: requests.Response) -> dict:
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} {r.request.method} {r.url}: {r.text[:800]}")
    return r.json()


def credits() -> dict:
    for path in ("/credits", "/credits:get"):
        r = requests.get(API + path, headers=_headers(), timeout=30)
        if r.status_code != 404:
            return _check(r)
    raise RuntimeError("credits endpoint not found")


def _load() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def _save(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def start(scene: dict) -> dict:
    img = _image(scene["scene_id"])
    body = {
        "display_name": f"HealthDojo - {scene['title']}",
        "model": MODEL,
        "tags": ["healthdojo", scene.get("bench", "falls")],
        "permission": {"public": True},
        "world_prompt": {
            "type": "image",
            "image_prompt": {
                "source": "data_base64",
                "data_base64": base64.b64encode(img.read_bytes()).decode(),
                "extension": "jpg",
            },
            "text_prompt": scene["text_prompt"],
            "is_pano": False,
        },
    }
    r = requests.post(API + "/worlds:generate", headers=_headers(), json=body, timeout=120)
    op = _check(r)
    return {**scene, **_meta(scene["scene_id"]), "operation_id": op["operation_id"], "started_at": time.time(), "model": MODEL, "status": "pending"}


def _download(url: str, dest: Path) -> str | None:
    try:
        urllib.request.urlretrieve(url, dest)
        return str(dest.relative_to(ROOT))
    except Exception as e:  # noqa: BLE001
        print(f"  download failed {url[:80]}: {e}")
        return None


def poll_one(entry: dict, timeout_s: int = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        r = requests.get(f"{API}/operations/{entry['operation_id']}", headers=_headers(), timeout=60)
        op = _check(r)
        if op.get("done"):
            if op.get("error"):
                entry.update(status="failed", error=op["error"])
                return entry
            world = op.get("response") or {}
            wid = world.get("world_id") or (op.get("metadata") or {}).get("world_id")
            if wid and not world.get("assets"):
                world = _check(requests.get(f"{API}/worlds/{wid}", headers=_headers(), timeout=60))
            (OUT / f"{entry['scene_id']}.world.json").write_text(json.dumps(world, indent=2))
            assets = world.get("assets") or {}
            entry.update(
                status="done",
                world_id=world.get("world_id", wid),
                viewer_url=world.get("world_marble_url"),
                caption=assets.get("caption"),
                elapsed_s=round(time.time() - entry["started_at"]),
                cost=op.get("cost") or (op.get("metadata") or {}).get("cost"),
            )
            if assets.get("thumbnail_url"):
                entry["thumbnail"] = _download(assets["thumbnail_url"], OUT / f"{entry['scene_id']}.thumb.jpg")
            pano = (assets.get("imagery") or {}).get("pano_url")
            if pano:
                entry["pano"] = _download(pano, OUT / f"{entry['scene_id']}.pano.png")
            return entry
        meta = op.get("metadata") or {}
        print(f"  {entry['scene_id']}: {meta.get('progress') or meta} ({round(time.time() - t0)}s)")
        time.sleep(20)
    entry["status"] = "timeout"
    return entry


def poll_all() -> None:
    state = _load()
    pending = [e for e in state.values() if e.get("status") == "pending"]
    with ThreadPoolExecutor(len(pending) or 1) as ex:
        for e in ex.map(poll_one, pending):
            state[e["scene_id"]] = e
            _save(state)
            print(f"{e['scene_id']}: {e['status']} {e.get('viewer_url') or e.get('error')}")


def generate(max_parallel: int = 4) -> None:
    import threading

    state = _load()
    lock = threading.Lock()
    todo = [s for s in SHOWCASE if s["scene_id"] not in state]

    def run(scene):
        with lock:
            time.sleep(1)  # stay well under the ~3 starts/min default rate limit burst
            e = start(scene)
            state[e["scene_id"]] = e
            _save(state)
        print(f"started {e['scene_id']} op={e['operation_id']}", flush=True)
        e = poll_one(e)
        with lock:
            state[e["scene_id"]] = e
            _save(state)
        print(f"{e['scene_id']}: {e['status']} {e.get('viewer_url') or e.get('error')}", flush=True)

    with ThreadPoolExecutor(max_parallel) as ex:
        list(ex.map(run, todo))
    backfill()


# Hand-annotated hazard centers for batch-2 worlds, same convention as walk.py GT_REGIONS:
# (cx, cy, radius_deg, label) in pixels of a 1280x640 downscale of the world's pano (x=640 is the source-photo view).
MARBLE_GT_REGIONS = {
    "dem-bedroom-base0-DEM-R03": [(705, 346, 6, "handgun on the nightstand")],
    "dem-bathroom-base0-DEM-B03": [(640, 430, 8, "dark mat in front of the tub"), (600, 565, 25, "dark mat on the light floor")],
    "dem-kitchen-base0-DEM-K04": [(230, 368, 9, "prescription bottles on the counter"), (455, 352, 7, "pill bottles by the canisters")],
    "dem-entry-base0-DEM-E02": [(960, 362, 22, "glass doors standing open to the patio")],
    "kitchen-base1-KIT-04": [(690, 395, 8, "runner mat in the galley"), (1040, 522, 14, "unbacked runner at the sink")],
    "living-base0-LIV-01": [(640, 375, 8, "area rug with a curled corner in the walkway")],
    "entry-base0-ENT-01": [(638, 340, 6, "front steps with no handrail")],
    "bedroom-base0-BED-01": [(705, 392, 12, "mattress directly on the floor")],
}


def _gt_regions() -> dict:
    """Hand-annotated pano GT regions from src/walk.py (parsed, not imported: walk.py pulls in model clients)."""
    import ast

    src = (ROOT / "src" / "walk.py").read_text()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "GT_REGIONS")
    return {**ast.literal_eval(node.value), **MARBLE_GT_REGIONS}


def fit_src_hfov(scene_id: str) -> float:
    """Marble places the source photo at pano yaw 0 but with its own FOV estimate. Fit it: render the pano
    (gnomonic, yaw 0) at candidate hfovs and pick the best normalized cross-correlation with the source photo."""
    import math

    import numpy as np
    from PIL import Image

    src = Image.open(_image(scene_id)).convert("L")
    w = 192
    h = round(w * src.height / src.width)
    a = np.asarray(src.resize((w, h)), np.float32)
    a = (a - a.mean()) / (a.std() + 1e-6)
    pano = np.asarray(Image.open(OUT / f"{scene_id}.pano.png").convert("L").resize((2048, 1024)), np.float32)
    ph, pw = pano.shape
    best = (-9.0, 75.0)
    for hf in range(50, 131, 3):
        f = (w / 2) / math.tan(math.radians(hf) / 2)
        X, Y = np.meshgrid(np.arange(w) - w / 2 + 0.5, h / 2 - np.arange(h) - 0.5)
        lon = np.arctan2(X, f)
        lat = np.arctan2(Y, np.hypot(X, f))
        u = ((lon / (2 * np.pi) + 0.5) * pw).astype(int) % pw
        v = np.clip(((0.5 - lat / np.pi) * ph).astype(int), 0, ph - 1)
        b = pano[v, u]
        b = (b - b.mean()) / (b.std() + 1e-6)
        score = float((a * b).mean())
        if score > best[0]:
            best = (score, float(hf))
    return best[1]


def hazard_dirs(scene_id: str) -> list[dict]:
    """Directions (yaw right+, pitch up+, degrees; yaw 0 = source-photo view) of the seeded hazard.
    Exact-ish for worlds with hand-annotated GT in walk.py; else projected from the scene's hazard box
    assuming the source photo is the forward view at 75 deg hfov (approximate)."""
    import math

    gt = _gt_regions().get(scene_id)
    if gt:
        return [{"yaw": round((x / 1280 - 0.5) * 360, 1), "pitch": round((0.5 - y / 640) * 180, 1), "r": r,
                 "label": lab, "approx": False} for x, y, r, lab in gt]
    sj = (ROOT / "data" / ("benchmarks/dementia/scenes" if scene_id.startswith("dem-") else "scenes") / f"{scene_id}.json")
    box = json.loads(sj.read_text())["hazards"][0].get("box") or [350, 550, 650, 900]
    from PIL import Image

    w, h = Image.open(_image(scene_id)).size
    hfov = fit_src_hfov(scene_id) if (OUT / f"{scene_id}.pano.png").exists() else 75.0
    f = (w / 2) / math.tan(math.radians(hfov) / 2)
    cx, cy = (box[0] + box[2]) / 2000, (box[1] + box[3]) / 2000
    x, y = (cx - 0.5) * w, (0.5 - cy) * h
    return [{"yaw": round(math.degrees(math.atan2(x, f)), 1), "pitch": round(math.degrees(math.atan2(y, math.hypot(x, f))), 1),
             "r": round(math.degrees(math.atan2((box[2] - box[0]) / 1000 * w / 2, f)), 1), "label": "seeded hazard (approx.)",
             "approx": True, "src_hfov_fit": hfov}]


def backfill() -> None:
    """Add bench/hazard_id/hazard_name/guideline/spz/collider fields to every entry (additive, schema-compatible)."""
    state = _load()
    for sid, e in state.items():
        for k, v in _meta(sid).items():
            e.setdefault(k, v)
        wj = OUT / f"{sid}.world.json"
        if e.get("status") == "done" and wj.exists():
            a = json.loads(wj.read_text()).get("assets") or {}
            sp = a.get("splats") or {}
            e["spz_urls"] = sp.get("spz_urls")
            e["semantics_metadata"] = sp.get("semantics_metadata")
            e["collider_mesh_url"] = (a.get("mesh") or {}).get("collider_mesh_url")
            e["walk_url"] = f"world.html?id={sid}"
            e["hazard_dirs"] = hazard_dirs(sid)
    _save(state)


def _data_uri(path: Path, max_px: int = 480) -> str:
    """Inline a small JPEG so site/worlds_3d.html is self-contained (no relative asset paths)."""
    import subprocess
    import tempfile

    src = path
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "t.jpg"
        try:
            subprocess.run(["sips", "-Z", str(max_px), "-s", "format", "jpeg", str(path), "--out", str(tmp)],
                           check=True, capture_output=True)
            src = tmp
        except Exception:  # noqa: BLE001  (non-mac: embed as-is)
            pass
        return "data:image/jpeg;base64," + base64.b64encode(src.read_bytes()).decode()


SITE_TEMPLATE = r"""<!doctype html>
<!-- HealthDojo: "Walk the home in 3D" section. Generated by `python src/marble.py site` (edit the template there).
     Self-contained (images inlined): include the <section> inside #worlds-3d or iframe this file.
     Each card opens world.html?id=<scene_id> (first-person walkable SparkJS viewer). Marble's own viewer sends
     X-Frame-Options: DENY, so it is linked, not embedded. -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Instrument+Serif:ital@0;1&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<section class="hd-w3d" id="worlds-3d-section">
<style>
.hd-w3d{--font-sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--font-serif:"Instrument Serif",Georgia,serif;--font-mono:"IBM Plex Mono",ui-monospace,monospace;
--green-active:#46a82c;--green-ink:#2e7a18;--lime:#d5fd51;--gold:#f6c86a;--gold-soft:#fbeed3;--gold-ink:#8a6420;--cream:#f7f2e5;--cream-strong:#efe6cf;--cream-ink:#6b6350;
--canvas:#fcfcfa;--card:#fff;--border:#e6e6e1;--ink:#1f2123;--text-body:#3a3d3f;--text-muted:#646668;--text-faint:#8f9193;
font-family:var(--font-sans);color:var(--ink);background:var(--canvas);padding:24px 0;-webkit-font-smoothing:antialiased}
.hd-w3d h2{font-family:var(--font-serif);font-weight:400;font-size:40px;line-height:1.05;margin:0 0 6px}
.hd-w3d .sub{margin:0 0 24px;color:var(--text-muted);max-width:68ch;font-size:15px;line-height:1.5}
.hd-w3d .grp{margin:0 0 28px}
.hd-w3d .gh{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;border-bottom:1px solid var(--border);padding-bottom:8px;margin-bottom:14px}
.hd-w3d .gh h3{font-family:var(--font-serif);font-weight:400;font-size:28px;margin:0}
.hd-w3d .gh span{font-size:13px;color:var(--text-muted)}
.hd-w3d .gh .n{font-family:var(--font-mono);font-size:12px;color:var(--text-faint)}
.hd-w3d .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.hd-w3d .card{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;display:flex;flex-direction:column;transition:border-color .16s}
.hd-w3d .card:hover{border-color:var(--text-faint)}
.hd-w3d .pair{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border)}
.hd-w3d .pair figure{margin:0;position:relative}
.hd-w3d .pair img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block}
.hd-w3d .pair figcaption{position:absolute;left:6px;bottom:6px;font-family:var(--font-mono);font-size:10px;letter-spacing:.04em;background:rgba(31,33,35,.72);color:#fcfcfa;padding:2px 6px;border-radius:4px}
.hd-w3d .body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:8px;flex:1}
.hd-w3d h4{margin:0;font-size:16px;font-weight:600}
.hd-w3d .hz{margin:0;font-size:13px;color:var(--text-body);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.hd-w3d .hid{font-family:var(--font-mono);font-size:11px;background:var(--gold-soft);color:var(--gold-ink);border:1px solid var(--gold);border-radius:999px;padding:1px 8px}
.hd-w3d .chip{font-size:12px;background:var(--cream);color:var(--cream-ink);border:1px solid var(--cream-strong);border-radius:999px;padding:2px 10px;align-self:flex-start;text-decoration:none;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hd-w3d .chip b{font-weight:600;color:var(--ink)}
.hd-w3d .actions{display:flex;gap:8px;margin-top:auto;flex-wrap:wrap;padding-top:4px}
.hd-w3d .btn{font:inherit;font-size:13px;font-weight:500;padding:7px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--ink);text-decoration:none}
.hd-w3d .btn.primary{background:var(--lime);color:var(--green-ink);border-color:var(--green-active)}
</style>
<h2>Walk the home in 3D</h2>
<p class="sub">Each labeled hazard photo from the benchmarks grown into a navigable 3D room with World Labs Marble. Walk in, turn around, and find the hazard the way an occupational therapist would on a home visit; toggle <b>Show hazard</b> to see where it was seeded.</p>
__GROUPS__
</section>
"""

GROUP = """<div class="grp" id="w3d-{bench}"><div class="gh"><h3>{name}</h3><span>{guideline}</span><span class="n">{n} worlds</span></div>
<div class="grid">{cards}</div></div>"""

CARD = """
<article class="card" data-world="{sid}">
  <div class="pair">
    <figure><img src="{photo}" alt="Source photo: {title}" loading="lazy"><figcaption>LABELED PHOTO</figcaption></figure>
    <figure><img src="{thumb}" alt="Marble 3D world: {title}" loading="lazy"><figcaption>3D WORLD</figcaption></figure>
  </div>
  <div class="body">
    <h4>{title}</h4>
    <p class="hz"><span class="hid">{hid}</span>{hname}</p>
    <a class="chip" href="{gurl}" target="_blank" rel="noopener" title="{gline}"><b>{gorg}</b> {gline}</a>
    <div class="actions">
      <a class="btn primary" href="world.html?id={sid}">Walk in 3D &rarr;</a>
      <a class="btn" href="{viewer}" target="_blank" rel="noopener">Marble viewer &#8599;</a>
    </div>
  </div>
</article>"""

BENCHES = [("falls", "Falls", "CDC STEADI Check for Safety · HOME FAST · HSSAT"),
           ("dementia", "DementiaBench", "Alzheimer's Association home-safety checklist · Alzheimer's Society (UK)")]


def build_world_manifest() -> None:
    """Inline the done worlds into site/world.html between the manifest script tags (site deploys without data/)."""
    import re

    state = _load()
    keep = ("scene_id", "title", "hazard", "bench", "hazard_id", "hazard_name", "guideline", "world_id", "viewer_url",
            "spz_urls", "semantics_metadata", "collider_mesh_url", "hazard_dirs")
    showcase = {s["scene_id"]: s for s in SHOWCASE}
    man = {sid: {k: e.get(k) for k in keep} | {"showcase": showcase.get(sid, {}).get("showcase", True)}
           for sid, e in state.items() if e.get("status") == "done"}
    p = ROOT / "site" / "world.html"
    html_ = p.read_text()
    blob = json.dumps(man, separators=(",", ":")).replace("</", "<\\/")
    html_ = re.sub(r'(<script id="manifest" type="application/json">).*?(</script>)',
                   lambda m: m.group(1) + blob + m.group(2), html_, flags=re.S)
    p.write_text(html_)
    print(f"world.html manifest: {len(man)} worlds")


def build_site() -> Path:
    import html

    esc = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731
    state = _load()
    groups = []
    for bench, name, gl in BENCHES:
        cards = []
        for scene in SHOWCASE:
            if scene.get("showcase") is False:
                continue
            e = state.get(scene["scene_id"])
            if not e or e.get("status") != "done" or e.get("bench", "falls") != bench:
                continue
            photo = _data_uri(_image(e["scene_id"]))
            tp = ROOT / e["thumbnail"] if e.get("thumbnail") else None
            thumb = _data_uri(tp) if tp and tp.exists() else photo
            g = e.get("guideline") or {}
            cards.append(CARD.format(sid=esc(e["scene_id"]), photo=photo, thumb=thumb, title=esc(e["title"]),
                                     hid=esc(e.get("hazard_id")), hname=esc(e.get("hazard_name") or e.get("hazard")),
                                     gurl=esc(g.get("url")), gorg=esc(g.get("org")), gline=esc(g.get("line")),
                                     viewer=esc(e["viewer_url"])))
        if cards:
            groups.append(GROUP.format(bench=bench, name=name, guideline=esc(gl), n=len(cards), cards="".join(cards)))
    out = ROOT / "site" / "worlds_3d.html"
    out.write_text(SITE_TEMPLATE.replace("__GROUPS__", "\n".join(groups)))
    print(f"wrote {out} with {sum(g.count('<article') for g in groups)} worlds")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if cmd == "credits":
        print(json.dumps(credits(), indent=2))
    elif cmd == "poll":
        poll_all()
    elif cmd == "site":
        backfill()
        build_world_manifest()
        build_site()
    else:
        generate()
        build_site()
