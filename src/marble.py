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
]


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
    img = ROOT / "data" / "renders" / f"{scene['scene_id']}.jpg"
    body = {
        "display_name": f"HealthDojo - {scene['title']}",
        "model": MODEL,
        "tags": ["homedojo", "fall-hazard"],
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
    return {**scene, "operation_id": op["operation_id"], "started_at": time.time(), "model": MODEL, "status": "pending"}


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


def generate() -> None:
    state = _load()
    for scene in SHOWCASE:
        if scene["scene_id"] in state:
            continue
        e = start(scene)
        state[e["scene_id"]] = e
        _save(state)
        print(f"started {e['scene_id']} op={e['operation_id']}")
    poll_all()


def _data_uri(path: Path, max_px: int = 720) -> str:
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


SITE_TEMPLATE = r"""<!-- HealthDojo: "Walk the home in 3D" section. Generated by src/marble.py site. Self-contained; include
     inline inside #worlds-3d or iframe it. Marble's own viewer (marble.worldlabs.ai) sends X-Frame-Options: DENY,
     so the in-page preview renders the world's Gaussian splat with SparkJS instead. -->
<section class="hd-w3d">
<style>
.hd-w3d{--ink:#1b1f24;--muted:#5b6470;--card:#fff;--line:#e3e6ea;--accent:#d9480f;font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink)}
.hd-w3d h2{margin:0 0 .25rem;font-size:1.5rem}
.hd-w3d .sub{margin:0 0 1.25rem;color:var(--muted);max-width:60ch}
.hd-w3d .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem}
.hd-w3d .card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.hd-w3d .pair{display:grid;grid-template-columns:1fr 1fr;gap:2px;background:var(--line)}
.hd-w3d .pair figure{margin:0;position:relative}
.hd-w3d .pair img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block}
.hd-w3d .pair figcaption{position:absolute;left:6px;bottom:6px;font-size:.7rem;background:rgba(0,0,0,.6);color:#fff;padding:2px 6px;border-radius:4px}
.hd-w3d .body{padding:.9rem 1rem 1rem;display:flex;flex-direction:column;gap:.5rem;flex:1}
.hd-w3d h3{margin:0;font-size:1.05rem}
.hd-w3d .hz{margin:0;font-size:.88rem;color:var(--muted)}
.hd-w3d .hz b{color:var(--accent)}
.hd-w3d .actions{display:flex;gap:.5rem;margin-top:auto;flex-wrap:wrap}
.hd-w3d a.btn,.hd-w3d button.btn{font:inherit;font-size:.88rem;padding:.5rem .8rem;border-radius:8px;border:1px solid var(--ink);cursor:pointer;text-decoration:none}
.hd-w3d a.btn{background:var(--ink);color:#fff}
.hd-w3d button.btn{background:#fff;color:var(--ink)}
.hd-w3d .viewer{position:fixed;inset:0;background:rgba(10,12,15,.92);display:none;z-index:9999;flex-direction:column}
.hd-w3d .viewer.open{display:flex}
.hd-w3d .vbar{display:flex;justify-content:space-between;align-items:center;color:#fff;padding:.6rem 1rem;font-size:.9rem;gap:1rem}
.hd-w3d .vbar a{color:#ffd8a8}
.hd-w3d .vbar button{font:inherit;background:none;border:1px solid #fff;color:#fff;border-radius:6px;padding:.25rem .7rem;cursor:pointer}
.hd-w3d .vcanvas{flex:1;position:relative}
.hd-w3d .vcanvas canvas{width:100%;height:100%;display:block}
.hd-w3d .vmsg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#ccc;pointer-events:none}
</style>
<h2>Walk the home in 3D</h2>
<p class="sub">Each labeled hazard photo from the benchmark, grown into a navigable 3D world with World Labs Marble. Step inside and look around the hazard the way an occupational therapist would on a home visit.</p>
<div class="grid">__CARDS__</div>
<div class="viewer" role="dialog" aria-modal="true">
  <div class="vbar"><span class="vtitle"></span><span><a class="vfull" target="_blank" rel="noopener">Open full Marble viewer &#8599;</a> &nbsp; <button type="button" class="vclose">Close</button></span></div>
  <div class="vcanvas"><div class="vmsg">Loading splats&hellip; drag to look around, scroll to move</div></div>
</div>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/","@sparkjsdev/spark":"https://sparkjs.dev/releases/spark/2.2.0/spark.module.js"}}</script>
<script type="module">
const root=document.currentScript?.closest?.('.hd-w3d')||document.querySelector('.hd-w3d');
const V=root.querySelector('.viewer'),box=root.querySelector('.vcanvas'),msg=root.querySelector('.vmsg');
let ctx=null;
async function open(btn){
  V.classList.add('open');msg.style.display='flex';msg.textContent='Loading splats… drag to look around, scroll/WASD to move';
  root.querySelector('.vtitle').textContent=btn.dataset.title;root.querySelector('.vfull').href=btn.dataset.viewer;
  try{
    const THREE=await import('three');const {SparkRenderer,SplatMesh}=await import('@sparkjsdev/spark');
    const {OrbitControls}=await import('three/addons/controls/OrbitControls.js');
    if(!ctx){
      const renderer=new THREE.WebGLRenderer({antialias:false});box.appendChild(renderer.domElement);
      const scene=new THREE.Scene();const camera=new THREE.PerspectiveCamera(70,1,0.01,1000);
      scene.add(new SparkRenderer({renderer}));
      const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
      const resize=()=>{const w=box.clientWidth,h=box.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();};
      addEventListener('resize',resize);
      renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);});
      ctx={THREE,SplatMesh,renderer,scene,camera,controls,resize,mesh:null};
    }
    ctx.resize();
    if(ctx.mesh){ctx.scene.remove(ctx.mesh);ctx.mesh.dispose?.();}
    const mesh=new ctx.SplatMesh({url:btn.dataset.spz});
    mesh.quaternion.set(1,0,0,0); // Marble SPZ is OpenCV-frame; 180deg about X, as Marble's own viewer does
    ctx.scene.add(mesh);ctx.mesh=mesh;
    // Worlds are generated around the source photo's camera: start at the origin looking down -Z (the photo view).
    ctx.camera.position.set(0,0,0.01);ctx.controls.target.set(0,0,-0.5);ctx.controls.update();
    await mesh.initialized;msg.style.display='none';
  }catch(e){msg.style.display='flex';msg.textContent='In-page preview unavailable ('+e.message+'). Use "Open full Marble viewer".';}
}
root.querySelectorAll('button[data-spz]').forEach(b=>b.addEventListener('click',()=>open(b)));
root.querySelector('.vclose').addEventListener('click',()=>V.classList.remove('open'));
addEventListener('keydown',e=>{if(e.key==='Escape')V.classList.remove('open');});
</script>
</section>
"""

CARD = """
<article class="card">
  <div class="pair">
    <figure><img src="{photo}" alt="Source photo: {title}" loading="lazy"><figcaption>Labeled photo</figcaption></figure>
    <figure><img src="{thumb}" alt="Marble 3D world: {title}" loading="lazy"><figcaption>3D world</figcaption></figure>
  </div>
  <div class="body">
    <h3>{title}</h3>
    <p class="hz"><b>Hazard {hid}:</b> {hazard}</p>
    <div class="actions">
      <a class="btn" href="{viewer}" target="_blank" rel="noopener">Open 3D walkthrough &#8599;</a>
      {preview}
    </div>
  </div>
</article>"""


def build_site() -> Path:
    import html

    state = _load()
    cards = []
    for scene in SHOWCASE:
        if scene.get("showcase") is False:
            continue
        e = state.get(scene["scene_id"])
        if not e or e.get("status") != "done":
            continue
        world = json.loads((OUT / f"{e['scene_id']}.world.json").read_text())
        spz = ((world.get("assets") or {}).get("splats") or {}).get("spz_urls") or {}
        spz_url = spz.get("500k") or spz.get("full_res") or next(iter(spz.values()), None)
        photo = _data_uri(ROOT / "data" / "renders" / f"{e['scene_id']}.jpg")
        thumb_path = ROOT / e["thumbnail"] if e.get("thumbnail") else None
        thumb = _data_uri(thumb_path) if thumb_path and thumb_path.exists() else photo
        esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731
        preview = (
            f'<button type="button" class="btn" data-spz="{esc(spz_url)}" data-viewer="{esc(e["viewer_url"])}" '
            f'data-title="{esc(e["title"])}">Preview here</button>' if spz_url else ""
        )
        cards.append(CARD.format(photo=photo, thumb=thumb, title=esc(e["title"]), hid=esc(e["scene_id"].split("-", 2)[-1]),
                                 hazard=esc(e["hazard"]), viewer=esc(e["viewer_url"]), preview=preview))
    out = ROOT / "site" / "worlds_3d.html"
    out.write_text(SITE_TEMPLATE.replace("__CARDS__", "".join(cards)))
    print(f"wrote {out} with {len(cards)} worlds")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if cmd == "credits":
        print(json.dumps(credits(), indent=2))
    elif cmd == "poll":
        poll_all()
    elif cmd == "site":
        build_site()
    else:
        generate()
        build_site()
