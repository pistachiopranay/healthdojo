"""Generate HomeBench scenes: clean base rooms, then single-hazard edits.

The label is decided before the pixels: each edit scene inserts exactly one
taxonomy hazard into a base room we believe is clean. verify.py then checks it.
"""
import json, os, sys, concurrent.futures as cf
from common import DATA, RENDERS, SCENES, BENCH, bench_meta, taxonomy, gen_image, gen_image_bedrock_inpaint, hazard_type

STYLE = ("Photorealistic smartphone photo taken at eye level in a modest, lived-in American home of a 70-year-old. "
         "Natural light, realistic everyday objects, no people, no text.")

BASES = {
    "bathroom": "A bathroom with a walk-in or tub-shower that has sturdy stainless grab bars on the wall, a shower chair and handheld shower, a raised toilet seat with a toilet safety frame, non-slip strips in the tub, and a bare dry tile floor with no mats.",
    "bedroom": "A tidy bedroom with a bed at knee height, a nightstand with a lamp within arm's reach, a clear wide floor path around the bed, and a plug-in night light by the door.",
    "stairs": "An indoor staircase with sturdy continuous handrails on both sides, bright overhead lighting, clear high-contrast step edges, and nothing on the steps.",
    "kitchen": "A kitchen with everyday dishes on counter-height shelves, a bare clean dry floor with no mats, and no step stools.",
    "living": "A living room with a clear wide walkway, no rugs, all cords tucked behind furniture, a firm armchair with armrests, and bright even lighting.",
    "entry": "A front entrance seen from the walkway: two concrete steps with sturdy handrails on both sides, a smooth even path, a wide front door with a flush threshold, and a bright porch light.",
}

META = bench_meta()
if BENCH:  # a benchmark's taxonomy json carries its own base rooms + style; ids get a bench prefix so site images never collide
    STYLE, BASES = META.get("style", STYLE), META["bases"]

EDIT = ("Edit this photo. Keep the room, camera angle, lighting and every other object exactly the same. "
        "Make only this one change so that it is clearly visible: {change}")


def plan(n_bases_per_room=2):
    tax = taxonomy()
    scenes = []
    if BENCH:
        n_bases_per_room = int(META.get("bases_per_room", 1))
    for room, desc in BASES.items():
        for b in range(n_bases_per_room):
            base_id = f"{BENCH[:3]}-{room}-base{b}" if BENCH else f"{room}-base{b}"
            scenes.append({"id": base_id, "room": room, "kind": "base", "hazards": [],
                           "prompt": f"{STYLE} {desc}" if isinstance(desc, str) else f"reused: {desc.get('reuse')}"})
            room_haz = [h for h in tax.values() if h["room"] == room]
            # alternate hazards across the two bases so each hazard appears once per room set
            for i, h in enumerate(room_haz):
                if i % n_bases_per_room != b:
                    continue
                if BENCH and h.get("render", True) is None:
                    continue  # rubric row kept, but not renderable against this base (see render_note)
                change = f"introduce this {META.get('hazard_noun', 'fall hazard')}: {h['name']}. {h['visual_description']}"
                scenes.append({"id": f"{base_id}-{h['id']}", "room": room, "kind": "edit", "base": base_id,
                               "prompt": EDIT.format(change=change),
                               "hazards": [{"id": h["id"], "type": hazard_type(h["id"])}]})
    return scenes


def render(scene, base_urls):
    dest = RENDERS / f"{scene['id']}.jpg"
    meta = SCENES / f"{scene['id']}.json"
    if meta.exists():
        return json.loads(meta.read_text())
    urls = [base_urls[scene["base"]]] if scene["kind"] == "edit" else None
    spec = BASES.get(scene["room"]) if BENCH else None
    if BENCH and scene["kind"] == "base" and isinstance(spec, dict) and spec.get("reuse"):
        import shutil  # reuse a verified-clean HomeBench room as this benchmark's base
        shutil.copy(DATA.parent.parent / spec["reuse"], dest)
        scene["source_url"] = str(dest)
    elif BENCH and scene["kind"] == "edit" and os.getenv("IMAGE_BACKEND") == "bedrock":
        h = taxonomy()[scene["hazards"][0]["id"]]
        scene["mask"] = h["render"]["mask"]
        scene["prompt"] = f"{h['render']['inpaint']}, photorealistic, same lighting and camera as the rest of the photo"
        scene["source_url"] = gen_image_bedrock_inpaint(scene["prompt"], dest, urls[0], scene["mask"])
    else:
        scene["source_url"] = gen_image(scene["prompt"], dest, image_urls=urls)
    scene["image"] = f"renders/{dest.name}"
    meta.write_text(json.dumps(scene, indent=1))
    print("ok", scene["id"], flush=True)
    return scene


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None  # "bases" to render bases only
    scenes = plan()
    (SCENES.parent / "scene_plan.json").write_text(json.dumps(scenes, indent=1))
    bases = [s for s in scenes if s["kind"] == "base"]
    with cf.ThreadPoolExecutor(10) as ex:
        done = list(ex.map(lambda s: render(s, {}), bases))
    base_urls = {s["id"]: s["source_url"] for s in done}
    if only == "bases":
        sys.exit()
    edits = [s for s in scenes if s["kind"] == "edit"]
    with cf.ThreadPoolExecutor(10) as ex:
        for f in cf.as_completed([ex.submit(render, s, base_urls) for s in edits]):
            try: f.result()
            except Exception as e: print("FAIL", e, flush=True)
