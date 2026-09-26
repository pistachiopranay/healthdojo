"""HealthDojo curriculum engine: per guideline, a ~100-image ladder whose difficulty compounds by level.

Exact labels, label-before-pixels: for each item, Sonnet 5 (Bedrock) plans every edit (label + region) up front;
Stability inpaint (Bedrock) then paints ONE region per step, stacked on a clean base. The pixel diff between
consecutive steps is that edit's box. Distractors (safe look-alikes) are inpaints labelled negative. Lighting /
camera degradations are applied last as a deterministic global grade (box-preserving) and recorded.

Usage:
  python src/curriculum.py <bench: falls|dementia> [scale=1.0]          # bases + generation + verify
  python src/curriculum.py <bench> curve                                # 3-model difficulty curve
Outputs: data/curriculum/<bench>/{img,thumb,bases,steps}/ + manifest.json (rewritten after every level).
"""
import base64, io, json, os, random, re, sys, threading, time, traceback, concurrent.futures as cf, pathlib
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)
if os.getenv("AWS_ACCESS_KEY_ID"):
    os.environ.pop("AWS_PROFILE", None)

LLM = "us.anthropic.claude-sonnet-5"
INPAINT = "us.stability.stable-image-inpaint-v1:0"
STRUCTURE = "us.stability.stable-image-control-structure-v1:0"  # no text-to-image Stability model on this account
IMG_SEM = threading.Semaphore(int(os.getenv("IMG_CONC", "3")))
COST = {"image_calls": 0, "llm_calls": 0}
_client, _lk = None, threading.Lock()


def br():
    global _client
    with _lk:
        if _client is None:
            import boto3
            from botocore.config import Config
            _client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"),
                                   config=Config(read_timeout=150, retries={"max_attempts": 1}, max_pool_connections=40))
    return _client


def retry(fn, tries=6):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            s = str(e)
            if i == tries - 1 or not any(k in s for k in ("404", "429", "rate", "Too many", "in flight", "Throttl", "Too many", "timeout", "Timeout", "ServiceUnavailable", "InternalServer", "ModelError", "503", "500", "Read timed out")):
                raise
            print("retry", i, s[:120], flush=True)
            time.sleep(min(20, 2 ** i) + random.random() * 2)


def png_b64(im):
    b = io.BytesIO(); im.save(b, "PNG"); return base64.b64encode(b.getvalue()).decode()


def jpg(im, side=1024, q=85):
    im = im.copy(); im.thumbnail((side, side)); b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=q); return b.getvalue()


def open_img(raw):  # Stability may return PNG or JPEG bytes; PIL sniffs magic
    return Image.open(io.BytesIO(raw)).convert("RGB")


def stability(model, body):
    def go():
        with IMG_SEM:
            r = br().invoke_model(modelId=model, body=json.dumps(body))
        d = json.loads(r["body"].read())
        if d.get("finish_reasons") and d["finish_reasons"][0]:
            raise RuntimeError(f"stability filtered: {d['finish_reasons']}")
        return base64.b64decode(d["images"][0])
    t0 = time.time()
    out = retry(go)
    COST["image_calls"] += 1
    print(f"  img {model.split('.')[-1][:24]} {time.time() - t0:.0f}s", flush=True)
    return out


def llm(content, max_tokens=2500, model=LLM):
    def go():
        r = br().converse(modelId=model, messages=[{"role": "user", "content": content}], inferenceConfig={"maxTokens": max_tokens})
        return "".join(b.get("text", "") for b in r["output"]["message"]["content"])
    t0 = time.time()
    out = retry(go)
    COST["llm_calls"] += 1
    print(f"  llm {time.time() - t0:.0f}s", flush=True)
    return out


def first_json(t):
    m = re.search(r"\{.*\}", t, re.S)
    return json.loads(m.group(0)) if m else {}


def imgblock(im, side=1024):
    return {"image": {"format": "jpeg", "source": {"bytes": jpg(im, side)}}}


# ---------------------------------------------------------------- guideline configs
CDC = "https://www.cdc.gov/steadi/pdf/STEADI-Brochure-CheckForSafety-508.pdf"
CDC_LINES = {
    "floors": "Floors: move furniture so your path is clear; remove throw rugs or use double-sided tape so they don't slip; pick up papers, books, towels, shoes and other objects on the floor; coil or tape cords and wires next to the wall.",
    "stairs": "Stairs and steps: keep objects off the stairs; fix loose or uneven steps; make sure carpet is firmly attached to every step, or remove it and put non-slip rubber treads on the stairs; handrails on both sides, as long as the stairs; fix loose handrails.",
    "light": "Make sure there is a light over the stairway and good lighting everywhere you walk; put night-lights in bedroom, hall and bathroom.",
    "kitchen": "Kitchen: move items in cabinets you use often to lower shelves (about waist level); if you must use a step stool, get one with a bar to hold on to - never use a chair as a step stool.",
    "bath": "Bathrooms: put a non-slip rubber mat or self-stick strips on the floor of the tub or shower; have grab bars put in next to and inside the tub and next to the toilet.",
    "bed": "Bedrooms: place a lamp close to the bed where it's easy to reach; put in a night-light so you can see where you're walking.",
}
FALLS_CITE = {"BATH": "bath", "BED": "bed", "STAIR": "stairs", "KIT": "kitchen", "LIV": "floors", "ENT": "stairs"}
FALLS_CITE_OVERRIDE = {"LIV-05": "light", "STAIR-04": "light", "BED-03": "light", "ENT-04": "light", "ENT-03": "floors", "BED-04": "floors"}

BENCHES = {
    "falls": {
        "title": "FallsDojo curriculum: post-op fall prevention (CDC STEADI Check for Safety)",
        "taxonomy": ROOT / "data/hazard_taxonomy.json",
        "guideline": {"name": "Check for Safety: A Home Fall Prevention Checklist for Older Adults (STEADI)", "publisher": "U.S. Centers for Disease Control and Prevention (CDC)",
                      "url": CDC, "license": "U.S. federal government work (public domain); lines paraphrased",
                      "excerpt": list(CDC_LINES.values())},
        "patient": "an older adult returning home after hip or knee replacement surgery (uses a walker)",
        "bases": {"bathroom": ["data/renders/bathroom-base0.jpg", "data/renders/bathroom-base1.jpg"], "bedroom": ["data/renders/bedroom-base0.jpg", "data/renders/bedroom-base1.jpg"],
                  "stairs": ["data/renders/stairs-base0.jpg", "data/renders/stairs-base1.jpg"], "kitchen": ["data/renders/kitchen-base0.jpg", "data/renders/kitchen-base1.jpg"],
                  "living": ["data/renders/living-base0.jpg", "data/renders/living-base1.jpg"], "entry": ["data/renders/entry-base0.jpg", "data/renders/entry-base1.jpg"]},
        # paintable hazards per room (absence-type rows need removal edits, excluded from painting)
        "pool": {"bathroom": ["BATH-07", "BATH-03", "LIV-02", "LIV-03", "LIV-07"], "bedroom": ["BED-04", "LIV-01", "LIV-02", "LIV-07", "KIT-03"],
                 "stairs": ["STAIR-03", "STAIR-05", "STAIR-02", "STAIR-06", "LIV-02"], "kitchen": ["KIT-03", "KIT-04", "KIT-02", "LIV-07", "LIV-02"],
                 "living": ["LIV-01", "LIV-02", "LIV-03", "LIV-07", "KIT-03"], "entry": ["LIV-01", "LIV-03", "LIV-07", "LIV-02", "ENT-02"]},
        "subtle": {"BATH-03": "a chrome towel bar mounted right beside the toilet/tub exactly where a person would grab to stand, with no grab bar anywhere (inadequate support)",
                   "BATH-07": "a thin low-contrast bath mat the same color as the floor, one corner slightly curled",
                   "STAIR-02": "a handrail that stops short two steps before the bottom of the flight",
                   "STAIR-05": "the carpet on one tread is slightly lifted/frayed at the nosing, same color as the rest, hard to see",
                   "STAIR-06": "one tread edge is chipped with a small broken piece missing",
                   "STAIR-03": "a single slipper resting at the edge of one tread",
                   "KIT-04": "a small clear water spill with a faint wet sheen on the floor in front of the sink",
                   "KIT-02": "a heavy pot and pet food bag stored on the floor at the base of the cabinets",
                   "LIV-01": "a thin beige rug on a beige floor with one edge slightly curled up",
                   "LIV-02": "a thin white charging cable running across the floor path, partially under furniture",
                   "LIV-03": "a low footstool placed partly in the walking path, half-hidden behind furniture",
                   "LIV-07": "a small pet toy and a flat water bowl near the doorway, partially behind a chair leg",
                   "BED-04": "a single pair of shoes partly under the bed edge on the exit side",
                   "KIT-03": "a regular kitchen chair pushed under the upper cabinets as if used to reach",
                   "ENT-02": "a raised wooden door threshold strip about an inch high at the doorway"},
        "distractors": {"bathroom": [("BATH-03", "a sturdy stainless-steel ADA grab bar properly anchored to the wall with flanges"), ("BATH-07", "a rubber-backed non-slip bath mat lying perfectly flat"), ("BATH-08", "a white shower chair with rubber feet")],
                        "bedroom": [("BED-02", "a bedside lamp switched on, on the nightstand within reach"), ("LIV-01", "a large low-pile area rug lying flat under the bed, edges fully flat"), ("LIV-02", "a white cord cover channel running along the baseboard")],
                        "stairs": [("STAIR-02", "a continuous wooden handrail on the wall running the full length of the stairs"), ("STAIR-05", "bright contrasting non-slip nosing strips on the tread edges"), ("STAIR-04", "a lit wall sconce light above the stairs")],
                        "kitchen": [("KIT-03", "a sturdy step stool with a tall grab handle folded and stored flat against the wall"), ("KIT-04", "a rubber anti-fatigue mat lying perfectly flat with beveled edges"), ("KIT-01", "everyday plates stacked on a waist-height open shelf")],
                        "living": [("LIV-04", "a firm upright armchair with sturdy armrests"), ("LIV-01", "a large low-pile rug with fully flat edges under the coffee table"), ("LIV-02", "a cord neatly clipped along the baseboard")],
                        "entry": [("ENT-01", "a sturdy handrail mounted beside the doorway steps"), ("LIV-03", "a neat shoe rack against the wall with shoes on it"), ("LIV-01", "a rubber-backed doormat lying flat")]},
        "lighting_hazard": ("LIV-05", {"bedroom", "kitchen", "entry", "living"}),
    },
    "dementia": {
        "title": "DementiaDojo curriculum: home safety for a person living with dementia (Alzheimer's Association / NIA)",
        "taxonomy": ROOT / "data/benchmarks/dementia/hazard_taxonomy.json",
        "guideline": {"name": "Home Safety Checklist for Alzheimer's Disease and Dementia; Alzheimer's Caregiving: Home Safety Tips", "publisher": "Alzheimer's Association; U.S. National Institute on Aging (NIA)",
                      "url": "https://www.alz.org/getmedia/dc740fbd-9cdc-4b64-b274-9fc9ee4ec64e/alzheimers-dementia-home-safety-checklist.pdf",
                      "license": "Alzheimer's Association content is copyrighted - lines paraphrased; NIA content is U.S. government work (public domain)", "excerpt": []},
        "patient": "an older adult living with dementia (Alzheimer's disease)",
        "bases": {"kitchen": ["data/benchmarks/dementia/renders/dem-kitchen-base0.jpg", "data/renders/kitchen-base0.jpg", "data/renders/kitchen-base1.jpg"],
                  "bathroom": ["data/benchmarks/dementia/renders/dem-bathroom-base0.jpg", "data/renders/bathroom-base1.jpg"],
                  "bedroom": ["data/benchmarks/dementia/renders/dem-bedroom-base0.jpg", "data/renders/bedroom-base1.jpg", "data/renders/bedroom-base0.jpg"],
                  "entry": ["data/benchmarks/dementia/renders/dem-entry-base0.jpg", "data/renders/living-base1.jpg"]},
        "pool": {"kitchen": ["DEM-K01", "DEM-K02", "DEM-K03", "DEM-K04"], "bathroom": ["DEM-B01", "DEM-B03", "DEM-B04"],
                 "bedroom": ["DEM-R01", "DEM-R02", "DEM-R04"], "entry": ["DEM-E01", "DEM-E02", "DEM-E03"]},
        "subtle": {"DEM-K01": "one small burner glowing faintly orange at the back of the stove, no pot on it",
                   "DEM-K02": "a single paring knife lying half under a dish towel on the counter",
                   "DEM-K03": "a small bottle of bleach tucked behind the dish soap by the sink",
                   "DEM-K04": "one orange prescription pill bottle next to the coffee maker",
                   "DEM-B01": "a small disposable razor lying beside the soap dish",
                   "DEM-B03": "a dark charcoal-gray bath mat in front of the tub",
                   "DEM-B04": "a hair straightener plugged in, its cord draped near the sink basin",
                   "DEM-R01": "a medium wall mirror on the closet door that reflects the bed",
                   "DEM-R02": "a rug with a bold dark striped border pattern at the bedside",
                   "DEM-R04": "a small space heater on the floor close to the hanging bedspread",
                   "DEM-E01": "a car key fob lying in a small dish on the entry table by the door",
                   "DEM-E02": "the front door left slightly ajar with daylight showing through the gap",
                   "DEM-E03": "a small stack of boxes partly blocking the hallway edge"},
        "distractors": {"kitchen": [("DEM-K01", "a stove that is off with plastic safety covers on all the knobs"), ("DEM-K04", "a closed locked gray medication lockbox"), ("DEM-K02", "a ceramic utensil crock holding wooden spoons and spatulas")],
                        "bathroom": [("DEM-B04", "an electric toothbrush standing in its charging base far from the sink basin, unplugged"), ("DEM-B03", "a light beige non-slip bath mat matching the light floor"), ("DEM-B01", "a toothbrush cup and pump soap dispenser")],
                        "bedroom": [("DEM-R01", "a small framed family photograph on the wall"), ("DEM-R04", "an unplugged oil-filled radiator standing against the far wall, away from any fabric"), ("DEM-R02", "a plain solid-color low-pile rug beside the bed")],
                        "entry": [("DEM-E01", "a small closed metal key lockbox mounted on the wall"), ("DEM-E02", "the front door closed with a door chime alarm sensor on the frame"), ("DEM-E03", "a neat low shoe rack against the wall")]},
        "lighting_hazard": None,
    },
}

EXCLUDED = {"DEM-R03"}

LEVELS = [
    {"level": 1, "name": "Obvious", "n": 10, "hazards_per_image": "1", "distractors": 0, "conditions": ["good light"],
     "description": "One salient hazard, clean room, good light, original base rooms."},
    {"level": 2, "name": "Subtle", "n": 15, "hazards_per_image": "1", "distractors": 0, "conditions": ["good light"],
     "description": "One hazard that requires judging ADEQUACY (towel bar used as grab bar, short handrail, low-contrast mat) or is small / partially occluded."},
    {"level": 3, "name": "Compound", "n": 20, "hazards_per_image": "2", "distractors": 1, "conditions": ["good light"],
     "description": "Two hazards stacked in one room plus one SAFE look-alike distractor (e.g. a proper anchored grab bar, a flat non-slip mat) that must NOT be flagged."},
    {"level": 4, "name": "Cluttered", "n": 25, "hazards_per_image": "3-4", "distractors": 2, "conditions": ["dim evening / night / underexposed-blur grade", "varied new base rooms"],
     "description": "3-4 hazards (some subtle) plus 2 distractors, with realism degradations: dim or night lighting, soft focus/noise, new base homes."},
    {"level": 5, "name": "Adversarial", "n": 30, "hazards_per_image": "0 or 4+", "distractors": "2-3", "conditions": ["poor light for positives", "safe-but-scary negatives"],
     "description": "~40% safe-but-scary rooms (0 hazards, only look-alikes: negatives) and ~60% rooms with 4+ hazards, several subtle adequacy/measurement ones, in poor light."},
]

CONDITIONS = {  # deterministic global grades: box-preserving, so labels stay exact
    "dim_evening": lambda im: ImageEnhance.Color(ImageEnhance.Brightness(im).enhance(0.55)).enhance(0.8),
    "night_lamp": lambda im: _tint(ImageEnhance.Brightness(im).enhance(0.35), (255, 190, 120), 0.18),
    "underexposed_blur": lambda im: _noise(ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(1.6))).enhance(0.5), 10),
    "blue_night": lambda im: _tint(ImageEnhance.Brightness(im).enhance(0.3), (90, 110, 200), 0.25),
    "flat_overcast": lambda im: ImageEnhance.Contrast(ImageEnhance.Brightness(im).enhance(0.85)).enhance(0.75),
}


def _tint(im, rgb, a):
    return Image.blend(im, Image.new("RGB", im.size, rgb), a)


def _noise(im, s):
    a = np.asarray(im).astype(float) + np.random.default_rng(0).normal(0, s, (im.size[1], im.size[0], 3))
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


# ---------------------------------------------------------------- state
class Bench:
    def __init__(self, name):
        self.name, self.cfg = name, BENCHES[name]
        self.out = ROOT / "data/curriculum" / name
        for d in ("img", "thumb", "bases", "steps"):
            (self.out / d).mkdir(parents=True, exist_ok=True)
        t = json.loads(self.cfg["taxonomy"].read_text())
        t["hazards"] = [h for h in t["hazards"] if h["id"] not in EXCLUDED]  # firearms removed at owner's request
        self.tax = {h["id"]: h for h in t["hazards"]}
        self.meta = t
        self.mpath = self.out / "manifest.json"
        self.m = json.loads(self.mpath.read_text()) if self.mpath.exists() else {}
        self.lock = threading.Lock()
        if self.m.get("items"):
            self.m["items"] = [it for it in self.m["items"] if not any(h["id"] in EXCLUDED for h in it["hazards"]) and not any(d.get("looks_like") in EXCLUDED for d in it["distractors"])]

        if name == "dementia":
            self.cfg["guideline"]["excerpt"] = list(dict.fromkeys(h["citation"]["guideline_line"] for h in t["hazards"]))
        self.m["excluded_hazards"] = {"DEM-R03": "firearm hazard removed at the owner's request; no weapon imagery generated"} if name == "dementia" else {}

    def citation(self, hid):
        h = self.tax[hid]
        if "citation" in h:
            return {"source": h["citation"]["source"], "line": h["citation"]["guideline_line"]}
        key = FALLS_CITE_OVERRIDE.get(hid) or FALLS_CITE[hid.split("-")[0]]
        return {"source": CDC, "line": CDC_LINES[key], "instruments": h.get("instrument_map")}

    def rubric(self):
        rows = []
        for h in self.tax.values():
            sev = h.get("severity")
            rows.append({"id": h["id"], "name": h["name"], "room": h["room"], "type": h.get("type") or _falls_type(h["id"]),
                         "severity": sev if isinstance(sev, str) else "varies (low/medium/high by context)", "severity_detail": sev if isinstance(sev, dict) else None,
                         "modifier": h.get("dementia_modifier") or (h.get("post_op") or {}).get("walker"), "citation": self.citation(h["id"])})
        return rows

    def save(self):
        with self.lock:
            m = self.m
            m.update({"bench": self.name, "title": self.cfg["title"], "guideline": self.cfg["guideline"], "rubric": self.rubric(),
                      "levels": LEVELS, "worlds": m.get("worlds", []), "difficulty_curve": m.get("difficulty_curve", {}),
                      "method": "Label-before-pixels: Sonnet 5 (Bedrock) plans each edit's label+region, Stability inpaint (Bedrock) paints one region per step on a clean base; box = pixel diff between consecutive steps. Distractors are labelled negatives. Conditions are deterministic global grades applied last. New bases: Stability control-structure restyles of existing clean rooms (no Stability text-to-image model is enabled on this account), judge-checked for hazards.",
                      "cost": m.get("cost") if not any(COST.values()) else {"stability_calls": COST["image_calls"], "llm_calls": COST["llm_calls"], "treg_gemini_calls": COST.get("treg_gemini_calls", 0), "est_usd": round(COST["image_calls"] * 0.06 + COST["llm_calls"] * 0.015 + COST.get("treg_gemini_calls", 0) * 0.03, 2)}})
            m.setdefault("items", [])
            m["items"].sort(key=lambda it: (it["level"], it["id"]))
            m["bases"] = m.get("bases", [])
            tmp = self.mpath.with_suffix(".tmp"); tmp.write_text(json.dumps(m, indent=1)); tmp.replace(self.mpath)


def _falls_type(hid):
    if hid in {"BATH-01", "BATH-02", "BATH-08", "BED-02", "STAIR-01", "ENT-01"}: return "absence"
    if hid in {"BATH-05", "BATH-06", "BED-01", "BED-05", "ENT-02", "ENT-05", "LIV-06", "BATH-03", "STAIR-02"}: return "adequacy/measurement"
    if hid in {"BED-03", "STAIR-04", "LIV-05", "ENT-04"}: return "lighting"
    return "object"


# ---------------------------------------------------------------- new bases
STYLES = ["a 1970s ranch home with wood paneling and warm tungsten lamps, older adult's house", "a modest 1990s suburban home with beige carpet and soft daylight from a window",
          "a small city apartment with white walls and cool overcast window light, older resident", "a farmhouse-style older home with worn hardwood and late afternoon sun",
          "a mid-century home with teal and mustard accents, evening indoor lighting", "a senior living apartment with neutral tones and bright overhead fluorescent light"]


def make_bases(b: Bench, n=6):
    have = {x["id"]: x for x in b.m.get("bases", [])}
    rooms = list(b.cfg["bases"])
    jobs = []
    for i in range(n):
        room = rooms[i % len(rooms)]
        bid = f"{b.name}-{room}-gen{i}"
        if bid in have and have[bid].get("accepted"):
            continue
        have.pop(bid, None)
        jobs.append((bid, room, b.cfg["bases"][room][i % len(b.cfg["bases"][room])], STYLES[i % len(STYLES)]))

    def one(j):
        bid, room, src, style = j
        try:
            im = Image.open(ROOT / src).convert("RGB"); im.thumbnail((1280, 1280))
            p = b.out / "bases" / f"{bid}.jpg"
            prompt = f"photorealistic smartphone photo of a clean, tidy, safe {room} in {style}. Same room layout, uncluttered floor, no people, no text"
            raw = p.read_bytes() if p.exists() else stability(STRUCTURE, {"image": png_b64(im), "prompt": prompt, "control_strength": 0.65, "output_format": "jpeg",
                                         "negative_prompt": "clutter, rugs, cords, mess, people, text, cartoon"})
            out = open_img(raw).resize(im.size)
            out.save(p, "JPEG", quality=90)
            chk = first_json(llm([imgblock(out), {"text": f"We need a CLEAN base photo of a {room} to which we will later add hazards. Judge only removable/added hazards (loose rugs, cords, clutter or objects on the floor, dangerous items left out, spills, lit stove); ignore the building's structure, stairs themselves, furniture style, carpet, or missing grab bars. clean = none of those removable hazards are obvious. photoreal = looks like a real photo with plausible geometry (no duplicated fixtures or melted objects). Answer ONLY JSON {{\"clean\": true|false, \"photoreal\": true|false, \"issues\": \"<short>\"}}"}], 300))
            rec = {"id": bid, "room": room, "path": f"bases/{bid}.jpg", "source": src, "style": style, "generator": STRUCTURE, "judge": chk,
                   "accepted": bool(chk.get("clean") and chk.get("photoreal"))}
        except Exception as e:
            rec = {"id": bid, "room": room, "accepted": False, "error": str(e)[:200]}
        print("base", bid, rec.get("accepted"), rec.get("judge", rec.get("error")), flush=True)
        return rec
    with cf.ThreadPoolExecutor(4) as ex:
        recs = list(ex.map(one, jobs))
    b.m["bases"] = list(have.values()) + recs
    for src_room, paths in b.cfg["bases"].items():
        for p in paths:
            bid = pathlib.Path(p).stem
            if not any(x["id"] == bid for x in b.m["bases"]):
                b.m["bases"].append({"id": bid, "room": src_room, "path": "../../../" + p, "source": p, "generator": "existing clean base", "accepted": True})
    b.save()


ULTRA = "stability.stable-image-ultra-v1:1"


def make_ultra_bases(b: Bench, n=8):
    """Brand-new clean rooms from Stable Image Ultra (us-west-2, Pranay's 'pistachio' profile; event account has no text-to-image)."""
    import boto3
    b.m["bases"] = [x for x in b.m.get("bases", []) if x.get("accepted") or ULTRA not in x.get("generator", "")]
    have = {x["id"] for x in b.m["bases"]}
    sess = boto3.Session(profile_name="pistachio", region_name="us-west-2", aws_access_key_id=None)
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        pass
    creds = sess.get_credentials()
    cli = boto3.client("bedrock-runtime", region_name="us-west-2", aws_access_key_id=creds.access_key, aws_secret_access_key=creds.secret_key, aws_session_token=creds.token)
    rooms = [r for r in b.cfg["pool"] if len(b.cfg["pool"][r]) >= 3]
    lights = ["dim evening lamp light", "overcast grey daylight", "warm afternoon sun through blinds", "harsh overhead ceiling light at night"]
    angles = ["wide-angle view from the doorway", "low camera angle from knee height", "high corner view looking down", "eye-level view"]
    jobs = [(f"{b.name}-{rooms[i % len(rooms)]}-ultra{i}", rooms[i % len(rooms)], STYLES[(i + 2) % len(STYLES)], lights[i % 4], angles[(i // 2) % 4]) for i in range(n)]
    jobs = [j for j in jobs if j[0] not in have]

    def one(j):
        bid, room, style, light, angle = j
        try:
            prompt = f"photorealistic smartphone photo, {angle}, of a clean tidy {room} in {style}, {light}. Uncluttered clear floor, nothing on the floor, no rugs, no cords, no people, no text"
            if room == "stairs":
                prompt = prompt.replace("of a clean tidy stairs", "of a clean indoor carpeted staircase with a full-length handrail")
            r = retry(lambda: json.loads(cli.invoke_model(modelId=ULTRA, body=json.dumps({"prompt": prompt, "aspect_ratio": "3:2", "output_format": "jpeg",
                                                                            "negative_prompt": "clutter, rug, cords, mess, people, text, cartoon, distorted"}))["body"].read()), 5)
            COST["image_calls"] += 1
            im = open_img(base64.b64decode(r["images"][0])); im.thumbnail((1280, 1280))
            im.save(b.out / "bases" / f"{bid}.jpg", "JPEG", quality=90)
            chk = first_json(llm([imgblock(im), {"text": f"We need a CLEAN base photo of a {room} to which we will later add hazards. Judge only removable/added hazards (loose rugs, cords, clutter or objects on the floor, dangerous items left out, spills, lit stove); ignore structure, furniture style, carpet, or missing grab bars. photoreal = looks like a real photo with plausible geometry. Answer ONLY JSON {{\"clean\": true|false, \"photoreal\": true|false, \"issues\": \"<short>\"}}"}], 300))
            rec = {"id": bid, "room": room, "path": f"bases/{bid}.jpg", "source": None, "style": f"{style}; {light}; {angle}", "prompt": prompt, "generator": ULTRA + " (us-west-2)", "judge": chk,
                   "accepted": bool(chk.get("clean") and chk.get("photoreal"))}
        except Exception as e:
            rec = {"id": bid, "room": room, "accepted": False, "generator": ULTRA, "error": str(e)[:200]}
        print("ultra base", bid, rec.get("accepted"), rec.get("judge", rec.get("error")), flush=True)
        return rec
    with cf.ThreadPoolExecutor(2) as ex:
        b.m["bases"] = b.m.get("bases", []) + list(ex.map(one, jobs))
    b.save()


def base_path(b, rec):
    return b.out / "bases" / f"{rec['id']}.jpg" if rec["generator"] != "existing clean base" else ROOT / rec["source"]


# ---------------------------------------------------------------- item specs
def specs(b: Bench, scale, rng):
    cfg, bases = b.cfg, [x for x in b.m["bases"] if x.get("accepted")]
    orig = [x for x in bases if x["generator"] == "existing clean base"]
    new = [x for x in bases if x["generator"] != "existing clean base"]
    out = []
    for L in LEVELS:
        nl = os.getenv("N_PER_LEVEL")
        n = int(nl.split(",")[L["level"] - 1]) if nl else max(3, round(L["n"] * scale))
        for k in range(n):
            lv = L["level"]
            pool_bases = orig if lv <= 2 else (bases if lv == 3 else (new + orig if new else orig))
            if lv == 5 and k % 5 in (0, 2):  # ~40% negatives
                negative = True
            else:
                negative = False
            need = {1: 1, 2: 1, 3: 2, 4: rng.choice([3, 4]), 5: 4}[lv] if not negative else 0
            cands = [x for x in pool_bases if len(cfg["pool"].get(x["room"], [])) >= max(need, 1)]
            if lv >= 4 and new and rng.random() < 0.7:
                cands = [x for x in cands if x["generator"] != "existing clean base"] or cands
            base = cands[(k * 7 + lv) % len(cands)] if lv <= 2 else rng.choice(cands)
            pool = cfg["pool"][base["room"]][:]
            rng.shuffle(pool)
            hz = pool[:need]
            nd = {1: 0, 2: 0, 3: 1, 4: 2, 5: 3 if negative else 2}[lv]
            dpool = [d for d in cfg["distractors"][base["room"]] if d[0] not in hz]
            rng.shuffle(dpool)
            ds = dpool[:nd]
            subtle = set(hz) if lv == 2 else (set(hz[: max(1, len(hz) // 2)]) if lv >= 4 else set())
            cond = None
            if lv == 4:
                cond = rng.choice(["dim_evening", "night_lamp", "underexposed_blur"])
            if lv == 5:
                cond = "flat_overcast" if negative else rng.choice(["night_lamp", "blue_night", "underexposed_blur"])
            out.append({"id": f"{b.name[:3]}-L{lv}-{k:03d}", "level": lv, "base": base, "hazards": hz, "subtle": sorted(subtle), "distractors": ds, "condition": cond, "negative": negative})
    return out


PLAN_Q = """Photo: a clean {room} (image is {W}x{H}). We are building a labelled training image for home-safety assessment for {patient}.
Plan these LOCAL edits, each painted by an inpainting model inside its own rectangular region. Decide labels + regions BEFORE any pixels change.
{edits}
Return ONLY JSON: {{"edits": [{{"key": "<key as given>", "box": [x0, y0, x1, y1], "prompt": "<photoreal description of what the region should show after the edit>"}}]}}
Rules: box in 0-1000 normalized coords (x right, y down). Boxes must NOT overlap each other and must not cover existing major fixtures/furniture unless the edit needs that surface (e.g. an item ON a counter/nightstand: box sits on that surface, covering only the empty area above it). Floor items go on open visible floor (not inside a tub, not on the bed or furniture): a floor box's bottom edge is usually in the lower third of the image. Before answering, locate the target surface in the image and double-check your coordinates land on it. Size realistically: each box about 12-35% of image width. Prompts describe the object in place, matching the room's perspective and light; for SUBTLE edits keep it small/low-contrast but still identifiable by a careful expert; for SAFE edits make clear it is the correct, safe version."""


def plan(b, spec, im):
    lines = []
    for hid in spec["hazards"]:
        h = b.tax[hid]
        if hid in spec["subtle"]:
            desc = b.cfg["subtle"].get(hid, h["visual_description"]) + " (SUBTLE)"
        else:
            desc = h["visual_description"] + " (make it clearly visible)"
        lines.append(f'- key "{hid}": HAZARD "{h["name"]}": {desc}. Guideline: {b.citation(hid)["line"]}')
    for i, (look, d) in enumerate(spec["distractors"]):
        lines.append(f'- key "D{i}": SAFE look-alike (must look safe, NOT a hazard): {d}')
    W, H = im.size
    want = set(spec["hazards"]) | {f"D{i}" for i in range(len(spec["distractors"]))}
    eds = {}
    for attempt in range(3):
        t = llm([imgblock(im), {"text": PLAN_Q.format(room=spec["base"]["room"], W=W, H=H, patient=b.cfg["patient"], edits="\n".join(lines)) + "\nOutput ONLY the JSON object, no reasoning or prose, no markdown."}], 3000)
        p = {}
        for cand in [t[t.find("{"):t.rfind("}") + 1]] + re.findall(r"\{\s*\"edits\".*\}", t, re.S):
            try:
                p = json.loads(cand); break
            except Exception:
                continue
        eds = {str(e.get("key", "")).strip(): e for e in p.get("edits", []) if isinstance(e, dict) and e.get("box") and e.get("prompt")}
        if want <= set(eds):
            break
        print("  plan incomplete, retry", spec["id"], sorted(set(eds)), flush=True)
    return eds


def inpaint(im, box, prompt):
    W, H = im.size
    x0, y0, x1, y1 = [max(0, min(1000, int(v))) for v in box[:4]]
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rectangle([x0 * W / 1000, y0 * H / 1000, x1 * W / 1000, y1 * H / 1000], fill=255)
    raw = stability(INPAINT, {"image": png_b64(im), "mask": png_b64(m), "prompt": prompt + ", photorealistic, same lighting and perspective",
                              "negative_prompt": "text, watermark, people, cartoon, blurry", "output_format": "jpeg", "grow_mask": 6})
    return open_img(raw).resize(im.size)


_OR = {"slug": None}


def openrouter_key():
    from dotenv import dotenv_values
    return (dotenv_values(ROOT / ".env").get("OPENROUTER_API_KEY") or "").strip() or None


def gemini_slug(key):
    if not _OR["slug"]:
        import urllib.request
        d = json.loads(urllib.request.urlopen(urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {key}"}), timeout=30).read())
        ids = [m["id"] for m in d["data"] if "image" in (m.get("architecture", {}).get("output_modalities") or [])]
        pick = [i for i in ids if "gemini-3" in i and "pro" in i and "image" in i] or [i for i in ids if "gemini" in i and "image" in i]
        _OR["slug"] = pick[0]
    return _OR["slug"]


GEM_SEM = threading.Semaphore(6)


def gemini_edit(im, box, prompt, key):
    import urllib.request
    slug = gemini_slug(key)
    x0, y0, x1, y1 = [int(v) for v in box[:4]]
    instr = (f"Edit this photo. Add ONLY this, inside the region x={x0/10:.0f}%-{x1/10:.0f}% from the left and y={y0/10:.0f}%-{y1/10:.0f}% from the top: {prompt}. "
             "Keep every other pixel of the photo identical: same framing, same camera, same lighting, same objects. Photorealistic. Return the edited image.")
    body = {"model": slug, "modalities": ["image", "text"], "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpg(im, 1280, 92)).decode()}}, {"type": "text", "text": instr}]}]}

    def go():
        with GEM_SEM:
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(req, timeout=180).read())
        url = d["choices"][0]["message"]["images"][0]["image_url"]["url"]
        return base64.b64decode(url.split(",", 1)[1])
    t0 = time.time()
    raw = retry(go, 6)
    COST["gemini_calls"] = COST.get("gemini_calls", 0) + 1
    print(f"  gemini {time.time() - t0:.0f}s", flush=True)
    return open_img(raw).resize(im.size), slug


TREGHOME = str(ROOT / ".scratch/treghome")
TREG_SEM = threading.Semaphore(int(os.getenv("TREG_CONC", "7")))
_s3 = {}


def treg(args):
    import subprocess
    out = subprocess.run(["treg", "call", *args], capture_output=True, text=True, env={**os.environ, "HOME": TREGHOME}, timeout=120)
    body = out.stdout[out.stdout.find("{"):]
    return json.loads(body)


def treg_balance():
    import subprocess
    try:
        out = subprocess.run(["treg", "balance"], capture_output=True, text=True, env={**os.environ, "HOME": TREGHOME}, timeout=30).stdout
        return float(re.search(r"\$([0-9.]+)", out).group(1))
    except Exception:
        return 0.0


_BAL = {"t": 0, "v": 0.0}


def treg_ok():
    if os.getenv("NO_TREG"):
        return False
    if time.time() - _BAL["t"] > 60:
        _BAL.update(t=time.time(), v=treg_balance())
    return _BAL["v"] >= 0.10


def public_url(im, key):
    """Presigned S3 URL (pistachio profile) so treg's Gemini can fetch the current step image."""
    import boto3
    with _lk:
        if "c" not in _s3:
            _s3["c"] = boto3.Session(profile_name="pistachio").client("s3", region_name="us-east-1")
    c = _s3["c"]
    c.put_object(Bucket="healthdojo-demo-pear", Key=f"curriculum-tmp/{key}.jpg", Body=jpg(im, 1280, 92), ContentType="image/jpeg")
    return c.generate_presigned_url("get_object", Params={"Bucket": "healthdojo-demo-pear", "Key": f"curriculum-tmp/{key}.jpg"}, ExpiresIn=7200)


def gemini_treg_edit(im, box, prompt, key):
    import urllib.request
    x0, y0, x1, y1 = [int(v) for v in box[:4]]
    horiz = "left" if x1 < 400 else "right" if x0 > 600 else "center"
    vert = "top" if y1 < 400 else "bottom" if y0 > 600 else "middle"
    instr = (f"Edit this exact photo. Add ONLY this one change, placed in the {vert}-{horiz} of the frame, inside the rectangle from {x0/10:.0f}% to {x1/10:.0f}% of the width (from the left) "
             f"and {y0/10:.0f}% to {y1/10:.0f}% of the height (from the top): {prompt}. Keep everything else exactly identical - same framing, camera, lighting, objects and colors. Photorealistic.")
    W, H = im.size
    ar = W / H
    size = "3:2" if ar > 1.4 else "4:3" if ar > 1.2 else "1:1"
    def go():
        with TREG_SEM:
            url = public_url(im, key)  # fresh upload on every attempt (deploy sync once wiped the prefix -> 404)
            task = treg(["reapi.image-gen.gemini-3-pro-image", "--method", "POST", "--data", json.dumps(
                {"model": "gemini-3-pro-image-preview", "prompt": instr, "size": size, "resolution": "1K", "image_urls": [url]})])
            if "id" not in task:
                raise RuntimeError(f"treg submit: {str(task)[:150]}")
            t0 = time.time()
            while time.time() - t0 < 200:
                time.sleep(5)
                r = treg(["reapi.tasks.get", "--query", f"id={task['id']}"])
                if r.get("status") == "completed":
                    u = r["output"]["image_urls"][0]
                    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 HomeDojo/0.1"}), timeout=60).read()
                if r.get("status") == "failed":
                    raise RuntimeError(f"treg task failed: {str(r.get('error'))[:150]}")
            raise RuntimeError("treg timeout")
    t0 = time.time()
    raw = retry(go, 6)
    COST["treg_gemini_calls"] = COST.get("treg_gemini_calls", 0) + 1
    print(f"  treg-gemini {time.time() - t0:.0f}s", flush=True)
    return open_img(raw).resize(im.size)


def edit(im, box, prompt, key="x"):
    """Backend switch: Gemini 3 Pro Image via treg (isolated HOME) while balance >= $0.10; else OpenRouter Gemini if key in .env; else Bedrock Stability inpaint."""
    if treg_ok():
        try:
            return gemini_treg_edit(im, box, prompt, key), {"backend": "treg", "model": "gemini-3-pro-image-preview"}
        except Exception as e:
            print("  treg gemini failed, falling back:", str(e)[:150], flush=True)
    key = openrouter_key()
    if key:
        try:
            out, slug = gemini_edit(im, box, prompt, key)
            return out, {"backend": "openrouter", "model": slug}
        except Exception as e:
            print("  gemini failed, falling back to Bedrock:", str(e)[:120], flush=True)
    return inpaint(im, box, prompt), {"backend": "bedrock", "model": INPAINT}


def diff_box(a, c, hint, wide=False):
    A = np.asarray(a.convert("L").resize((500, 375)), float); C = np.asarray(c.convert("L").resize((500, 375)), float)
    d = np.asarray(Image.fromarray(np.abs(A - C).astype("uint8")).filter(ImageFilter.GaussianBlur(3)))
    x0, y0, x1, y1 = hint
    pad = 40
    if wide:  # whole-image editor: global drift is low-amplitude, the added object is the strong change near the planned region
        pad = 160
        d = np.where(d > max(40, np.percentile(d, 97)), d, 0)
    win = np.zeros_like(d, bool)
    win[max(0, int(y0 * .375) - pad // 2):int(y1 * .375) + pad // 2, max(0, int(x0 * .5) - pad // 2):int(x1 * .5) + pad // 2] = True
    mask = (d > 20) & win
    if mask.sum() < 60:
        return None
    ys, xs = np.where(mask)
    bx0, bx1 = np.percentile(xs, [1, 99]); by0, by1 = np.percentile(ys, [1, 99])
    return [int(bx0 * 2), int(by0 / .375), int(bx1 * 2), int(by1 / .375)]


JUDGE_Q = """Home-safety image QA for {patient}. The image was edited to contain these labelled regions (0-1000 coords, x right, y down):
{rows}
Boxes are approximate (the object may extend beyond or sit slightly outside the box). For each key: is the described thing actually visible and recognisable in or near that region? For HAZARD keys: would a careful home-safety assessor see this hazard? For SAFE keys: does it look safe (not itself a hazard)?
Return ONLY JSON {{"checks": [{{"key": "...", "visible": true|false, "looks_safe": true|false|null, "note": "<short>"}}], "photoreal": true|false}}"""


def judge(b, im, item):
    rows = [f'- {h["id"]}: HAZARD "{b.tax[h["id"]]["name"]}" box={h["box"]}' for h in item["hazards"] if h.get("box")]
    rows += [f'- D{i}: SAFE "{d["label"]}" box={d["box"]}' for i, d in enumerate(item["distractors"])]
    if not rows:
        return {"checks": [], "photoreal": True}
    return first_json(llm([imgblock(im, 1280), {"text": JUDGE_Q.format(patient=b.cfg["patient"], rows="\n".join(rows))}], 1500))


def build(b: Bench, spec):
    iid = spec["id"]
    im = Image.open(base_path(b, spec["base"])).convert("RGB"); im.thumbnail((1280, 1280))
    eds = plan(b, spec, im)
    trace, hazards, distractors = [], [], []
    steps = [("hazard", hid) for hid in spec["hazards"]] + [("distractor", f"D{i}") for i in range(len(spec["distractors"]))]
    for n, (kind, key) in enumerate(steps):
        e = eds.get(key)
        if not e:
            trace.append({"kind": kind, "id": key, "skipped": "no plan"}); continue
        nxt, be = edit(im, e["box"], e["prompt"], f"{b.name}-{iid}-s{n}")
        box = diff_box(im, nxt, e["box"], wide=be["backend"] != "bedrock") or [int(v) for v in e["box"][:4]]
        im = nxt
        im.save(b.out / "steps" / f"{iid}-s{n}.jpg", "JPEG", quality=80)
        if kind == "hazard":
            h = b.tax[key]
            trace.append({"kind": "hazard", "id": key, "label": h["name"], "subtle": key in spec["subtle"], "prompt": e["prompt"], **be, "planner": LLM, "planned_box": e["box"], "box": box, "citation": b.citation(key)})
            hazards.append({"id": key, "name": h["name"], "box": box, "subtle": key in spec["subtle"]})
        else:
            look, label = spec["distractors"][int(key[1:])]
            trace.append({"kind": "distractor", "id": key, "label": label, "looks_like": look, "prompt": e["prompt"], **be, "planner": LLM, "planned_box": e["box"], "box": box})
            distractors.append({"label": label, "looks_like": look, "box": box})
    conds = []
    if spec["condition"]:
        im = CONDITIONS[spec["condition"]](im)
        conds.append(spec["condition"])
        trace.append({"kind": "lighting", "id": spec["condition"], "label": spec["condition"].replace("_", " "), "prompt": "deterministic global PIL grade (box-preserving)", "box": None})
        lh = b.cfg["lighting_hazard"]
        if lh and spec["condition"] != "flat_overcast" and spec["base"]["room"] in lh[1]:
            hazards.append({"id": lh[0], "name": b.tax[lh[0]]["name"], "box": None, "subtle": False, "from_condition": spec["condition"]})
    im.save(b.out / "img" / f"{iid}.jpg", "JPEG", quality=88)
    t = im.copy(); t.thumbnail((360, 360)); t.save(b.out / "thumb" / f"{iid}.jpg", "JPEG", quality=80)
    item = {"id": iid, "level": spec["level"], "image": f"img/{iid}.jpg", "thumb": f"thumb/{iid}.jpg", "base": spec["base"]["id"], "room": spec["base"]["room"],
            "negative": spec["negative"], "hazards": hazards, "distractors": distractors, "conditions": conds, "prompt_trace": trace}
    try:
        v = judge(b, im, item)
    except Exception as e:
        v = {"error": str(e)[:200]}
    checks = {c.get("key"): c for c in v.get("checks", []) if isinstance(c, dict)}
    hz_ok = all(checks.get(h["id"], {}).get("visible") for h in hazards if h.get("box"))
    ds_ok = all(checks.get(f"D{i}", {}).get("visible") and checks.get(f"D{i}", {}).get("looks_safe") is not False for i in range(len(distractors)))
    planned_ok = len(hazards) - sum(1 for h in hazards if not h.get("box")) == len(spec["hazards"]) and len(distractors) == len(spec["distractors"])
    item["verify"] = v
    item["verified"] = bool(hz_ok and ds_ok and planned_ok and "error" not in v)
    return item


def generate(b: Bench, scale=1.0, levels=None):
    rng = random.Random(7 if b.name == "falls" else 11)
    allspecs = specs(b, scale, rng)
    if os.getenv("REDO_FAILED"):
        bad = [it for it in b.m.get("items", []) if not it.get("verified")]
        b.m.setdefault("failed_attempts", []).extend(bad)
        b.m["items"] = [it for it in b.m.get("items", []) if it.get("verified")]
        print("requeued", len(bad), "unverified items", flush=True)
    done = {it["id"] for it in b.m.get("items", [])}
    b.m.setdefault("items", [])
    for L in LEVELS:
        if levels and L["level"] not in levels:
            continue
        todo = [s for s in allspecs if s["level"] == L["level"] and s["id"] not in done]
        t0 = time.time()

        def one(s):
            for attempt in range(2):
                try:
                    it = build(b, s)
                    if not it["verified"] and attempt == 0:
                        with b.lock:
                            b.m.setdefault("failed_attempts", []).append(it)
                        print(b.name, it["id"], "failed verify, rebuilding", flush=True)
                        continue
                    with b.lock:
                        b.m["items"].append(it)
                    print(b.name, it["id"], "VERIFIED" if it["verified"] else "flagged", len(it["hazards"]), "hz", len(it["distractors"]), "ds", flush=True)
                    return
                except Exception as e:
                    print(b.name, s["id"], "ERR", attempt, str(e)[:200], flush=True)
                    if attempt == 1:
                        traceback.print_exc()
        with cf.ThreadPoolExecutor(int(os.getenv("ITEM_CONC", "5"))) as ex:
            futs = [ex.submit(one, s) for s in todo]
            for i, f in enumerate(cf.as_completed(futs)):
                f.result()
                b.save()
        L_items = [it for it in b.m["items"] if it["level"] == L["level"]]
        print(f"== {b.name} L{L['level']} {len(L_items)} items, {sum(it['verified'] for it in L_items)} verified, {time.time() - t0:.0f}s, cost {COST}", flush=True)
        b.save()


REFINE_Q = """This home photo contains these labelled items (planned regions are approximate, 0-1000 coords, x right, y down):
{rows}
For each key, give the TIGHT bounding box of the actual object in the image (0-1000 coords), or null if you cannot find it.
Return ONLY JSON {{"boxes": {{"<key>": [x0, y0, x1, y1] | null}}}}"""


def refine(b: Bench):
    """Whole-image editors (Gemini) drift globally, so pixel-diff boxes are unreliable for them: localize each
    pre-declared label with Sonnet 5 inside the final image. Label identity is unchanged (still label-before-pixels)."""
    def one(it):
        if it.get("box_refined") or not any(t.get("backend") not in (None, "bedrock") for t in it["prompt_trace"]):
            return
        rows = [f'- {h["id"]}: {h["name"]} (planned {t["planned_box"]})' for h in it["hazards"] for t in it["prompt_trace"] if t.get("id") == h["id"] and t.get("planned_box")]
        rows += [f'- D{i}: {d["label"]} (planned {t["planned_box"]})' for i, d in enumerate(it["distractors"]) for t in it["prompt_trace"] if t.get("id") == f"D{i}" and t.get("planned_box")]
        if not rows:
            return
        try:
            r = first_json(llm([imgblock(Image.open(b.out / it["image"]).convert("RGB"), 1280), {"text": REFINE_Q.format(rows="\n".join(rows))}], 1200)).get("boxes", {})
        except Exception as e:
            print("refine ERR", it["id"], str(e)[:100]); return
        for h in it["hazards"]:
            nb = r.get(h["id"])
            if h.get("box") and isinstance(nb, list) and len(nb) == 4:
                h["diff_box"], h["box"], h["box_source"] = h["box"], [int(v) for v in nb], "sonnet-5 localization of pre-declared label (whole-image editor)"
        for i, d in enumerate(it["distractors"]):
            nb = r.get(f"D{i}")
            if isinstance(nb, list) and len(nb) == 4:
                d["diff_box"], d["box"], d["box_source"] = d["box"], [int(v) for v in nb], "sonnet-5 localization of pre-declared label (whole-image editor)"
        for t in it["prompt_trace"]:
            key = t.get("id")
            nb = r.get(key)
            if t.get("backend") not in (None, "bedrock") and isinstance(nb, list) and len(nb) == 4:
                t["diff_box"], t["box"] = t.get("box"), [int(v) for v in nb]
        it["box_refined"] = True
        if not it.get("verified") and all(t.get("skipped") is None for t in it["prompt_trace"]):
            try:  # re-judge against the localized boxes (the diff boxes the first judge saw were off for whole-image edits)
                im = Image.open(b.out / it["image"]).convert("RGB")
                v = judge(b, im, it)
                ch = {c.get("key"): c for c in v.get("checks", []) if isinstance(c, dict)}
                ok = all(ch.get(h["id"], {}).get("visible") for h in it["hazards"] if h.get("box")) and \
                     all(ch.get(f"D{i}", {}).get("visible") and ch.get(f"D{i}", {}).get("looks_safe") is not False for i in range(len(it["distractors"])))
                it["verify_after_refine"] = v
                if ok:
                    it["verified"] = True
                    it["verified_via"] = "re-judge after box localization"
            except Exception as e:
                print("rejudge ERR", it["id"], str(e)[:100])
        print("refined", it["id"], it.get("verified"), flush=True)
    with cf.ThreadPoolExecutor(12) as ex:
        list(ex.map(one, b.m["items"]))
    b.save()


# ---------------------------------------------------------------- difficulty curve
CURVE_MODELS = {"nova-pro": "amazon.nova-pro-v1:0", "nova-2-lite": "us.amazon.nova-2-lite-v1:0", "qwen3-vl": "qwen.qwen3-vl-235b-a22b", "gpt-5.6-sol": "us.openai.gpt-5.6-sol",
                "claude-sonnet-5": "us.anthropic.claude-sonnet-5", "llama-4-maverick": "us.meta.llama4-maverick-17b-instruct-v1:0",
                "mistral-large-3": "mistral.mistral-large-3-675b-instruct", "kimi-k3": "us.moonshotai.kimi-k3"}


def curve(b: Bench, models=None):
    import importlib
    os.environ["BENCH"] = "" if b.name == "falls" else "dementia"
    if b.name == "falls":
        os.environ.pop("BENCH", None)
    sys.path.insert(0, str(ROOT / "src"))
    rm = importlib.import_module("run_models")
    prompt = rm.PROMPT.format(checklist="\n".join(f"- {h['id']}: {h['name']}" for h in b.tax.values()))
    items = [it for it in b.m["items"] if it.get("verified")]
    od = b.out / "outputs"; od.mkdir(exist_ok=True)
    res = b.m.get("difficulty_curve", {})
    import hashlib

    def run_model(name):
        call = rm.bedrock_call(CURVE_MODELS[name])
        items = [it for it in b.m["items"] if it.get("verified")]
        (od / name).mkdir(exist_ok=True)

        def one(it):
            img = (b.out / it["image"]).read_bytes()
            f = od / name / f"{it['id']}-{hashlib.sha1(img).hexdigest()[:8]}.json"  # keyed on pixels: regenerated items get re-scored
            if f.exists():
                return json.loads(f.read_text())
            try:
                text = retry(lambda: call(img, prompt), 4)
                r = {"id": it["id"], "raw": text, "hazards": rm.parse(text)}
                f.write_text(json.dumps(r, indent=1))
                return r
            except Exception as e:
                print(name, it["id"], "ERR", str(e)[:150], flush=True)
                return None
        with cf.ThreadPoolExecutor(6) as ex:
            outs = dict(zip([it["id"] for it in items], ex.map(one, items)))
        per = {}
        for L in LEVELS:
            lv = [it for it in items if it["level"] == L["level"] and outs.get(it["id"])]
            tp = tot = ff = dtot = 0
            for it in lv:
                pred = {h.get("id") for h in outs[it["id"]]["hazards"]}
                truth = {h["id"] for h in it["hazards"]}
                tot += len(truth); tp += len(truth & pred)
                for d in it["distractors"]:
                    if d["looks_like"] in truth:
                        continue
                    dtot += 1; ff += d["looks_like"] in pred
            per[str(L["level"])] = {"n_items": len(lv), "recall": round(tp / tot, 3) if tot else None, "distractor_false_flag": round(ff / dtot, 3) if dtot else None,
                                    "n_hazards": tot, "n_distractors": dtot}
        res[name] = per
        print(name, json.dumps({k: (v["recall"], v["distractor_false_flag"]) for k, v in per.items()}), flush=True)
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(run_model, models or CURVE_MODELS))
    if not os.getenv("NOSAVE"):
        b.m = json.loads(b.mpath.read_text()) if b.mpath.exists() else b.m
        b.m["difficulty_curve"] = res
        b.m["difficulty_curve_meta"] = {"scored_on": "verified items only", "recall": "fraction of labelled hazard ids the model listed (id match, boxes ignored)",
                                        "distractor_false_flag": "fraction of safe look-alike distractors whose look-alike hazard id the model flagged although that id was not a true hazard in the image",
                                        "prompt": "src/run_models.py PROMPT (bench model_prompt for dementia) with this bench's checklist", "models": CURVE_MODELS}
        b.save()


if __name__ == "__main__":
    bench = sys.argv[1]
    b = Bench(bench)
    if len(sys.argv) > 2 and sys.argv[2] == "refine":
        refine(b)
    elif len(sys.argv) > 2 and sys.argv[2] == "curve":
        curve(b, sys.argv[3:] or None)
    else:
        scale = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
        levels = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else None
        if not b.m.get("bases") or os.getenv("REBASE"):
            make_bases(b, int(os.getenv("NBASES", "6")))
        if os.getenv("ULTRA_BASES"):
            make_ultra_bases(b, int(os.getenv("ULTRA_BASES")))
        generate(b, scale, levels)
        print("DONE", bench, COST, flush=True)
