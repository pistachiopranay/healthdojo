"""Build the Guideline Library: site/guidelines.html + site/guideline-<bench>.html from curriculum manifests.

Re-run any time a manifest grows:   .venv/bin/python src/build_library.py
Optional:  --mock   use .scratch/mock_manifest.json for any bench whose manifest is missing (dev only)

Input : data/curriculum/<bench>/manifest.json   (bench = falls, dementia; partial / missing fields are fine)
Output: site/guidelines.html, site/guideline-<bench>.html, site/curriculum/<bench>/{img,thumb,worlds}/*.jpg
Missing manifest -> skeleton from the bench's hazard taxonomy, shown as "Generating".
"""
import json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, SITE, SRC = ROOT / "data", ROOT / "site", ROOT / "src"
MOCK = "--mock" in sys.argv

BENCHES = {
    "falls": {
        "title": "Post-op fall prevention",
        "taxonomy": DATA / "hazard_taxonomy.json",
        "report": "index.html",
        "publisher": "CDC STEADI",
        "guideline": {
            "name": "Check for Safety: A Home Fall Prevention Checklist for Older Adults",
            "publisher": "CDC STEADI",
            "url": "https://www.cdc.gov/steadi/pdf/STEADI-Brochure-CheckForSafety-508.pdf",
            "license": "US federal work: text is public domain (the brochure photo is not). Cross-walked to HOME FAST and the World Falls Guidelines 2022.",
            "excerpt": [
                "Are there papers, books, towels, shoes, magazines, boxes, blankets, or other objects on the floor? Pick things up and keep objects off the floor.",
                "Do you have to walk around furniture when you walk through a room? Ask someone to move the furniture so your path is clear.",
                "Do you have throw rugs on the floor? Remove the rugs or use double-sided tape or a non-slip backing so the rugs won't slip.",
                "Do you have to walk over or around wires or cords? Coil or tape cords and wires next to the wall so you can't trip over them.",
                "Are there papers, shoes, books, or other objects on the stairs? Pick up things on the stairs. Always keep objects off stairs.",
                "Are some steps broken or uneven? Fix loose or uneven steps.",
                "Are there light switches only at one end of the stairs? Put in an overhead light and switch at the top and bottom of the stairs.",
                "Are the handrails loose or broken? Is there a handrail on only one side of the stairs? Make sure handrails are on both sides of the stairs.",
                "Is the tub or shower floor slippery? Put a non-slip rubber mat or self-stick strips on the floor of the tub or shower.",
                "Do you need some support when you get in and out of the tub, or up from the toilet? Have grab bars put in next to and inside the tub, and next to the toilet.",
                "Is the light near the bed hard to reach? Place a lamp close to the bed where it's easy to reach.",
                "Is the path from your bed to the bathroom dark? Put in a night-light so you can see where you're walking.",
            ],
        },
    },
    "dementia": {
        "title": "Dementia home safety",
        "taxonomy": DATA / "benchmarks" / "dementia" / "hazard_taxonomy.json",
        "report": "dementia.html",
        "publisher": "Alzheimer's Association / NIA",
        "guideline": {
            "name": "Home Safety Checklist for Alzheimer's Disease and Dementia",
            "publisher": "Alzheimer's Association / NIA",
            "url": "https://www.alz.org/help-support/caregiving/safety/home-safety",
            "license": "Guideline lines are paraphrased with attribution; cross-walked to NIA home-safety tips.",
            "excerpt": [],
        },
    },
}

COMING = [
    ("Pressure injury prevention", "NPIAP / EPUAP"),
    ("Medication safety at home", "AHRQ / ISMP"),
    ("Pediatric home injury", "AAP TIPP"),
    ("Smoke & CO alarm placement", "NFPA 72"),
]


# ---------------------------------------------------------------- helpers
def jload(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def words(s):
    return {w for w in re.findall(r"[a-z]{3,}", str(s or "").lower())} - {"the", "and", "you", "are", "your", "put", "for", "with", "that", "have", "there", "can", "use", "other"}


def match_line(cite, lines):
    """Index of the excerpt line a rubric citation quotes (exact substring first, then word overlap)."""
    c = str(cite or "").strip().strip('"“”').lower()
    if not c or not lines:
        return None
    for i, l in enumerate(lines):
        if c in l.lower() or l.lower() in c:
            return i
    cw = words(c)
    best = max(range(len(lines)), key=lambda i: len(cw & words(lines[i])) / (len(cw | words(lines[i])) or 1))
    return best if len(cw & words(lines[best])) >= 3 else None


def cite_text(c):
    if isinstance(c, dict):
        return c.get("guideline_line") or c.get("line") or c.get("quote") or c.get("text") or ""
    return c or ""


def taxonomy_rubric(bench, tax):
    rows = []
    for h in (tax or {}).get("hazards", []):
        mod = h.get("dementia_modifier") or (h.get("post_op") or {}).get("walker")
        sev = h.get("severity")
        if isinstance(sev, dict):
            sev = "high" if (h.get("post_op") or {}).get("escalate") else "medium"
        rows.append({"id": h["id"], "name": h.get("name"), "room": h.get("room"), "type": h.get("type"),
                     "severity": sev, "modifier": None if mod in (None, "-") else mod,
                     "citation": cite_text(h.get("citation")) or None})
    return rows


def resize(src, dest, w):
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        im.thumbnail((w, w))
        im.save(dest, "JPEG", quality=82)
    except Exception:
        shutil.copy(src, dest)


def site_img(bench, src_rel, base_dir, kind, stem, w):
    """Copy data/curriculum/<bench>/<src_rel> into site/curriculum/<bench>/<kind>/<stem>.jpg; return site-relative path."""
    if not src_rel:
        return None
    src = (base_dir / src_rel) if not Path(src_rel).is_absolute() else Path(src_rel)
    if not src.exists():
        return None
    dest = SITE / "curriculum" / bench / kind / (re.sub(r"[^\w.-]", "_", stem) + ".jpg")
    resize(src, dest, w)
    return dest.relative_to(SITE).as_posix()


# ---------------------------------------------------------------- per bench
def load_bench(bench, cfg):
    mdir = DATA / "curriculum" / bench
    man = jload(mdir / "manifest.json")
    source = "manifest"
    if MOCK and bench == "falls":  # dev: force the mock so the chart / distractor UI can be eyeballed
        man, source = jload(ROOT / ".scratch" / "mock_manifest.json"), "mock"
        mdir = DATA / "curriculum" / bench  # mock paths are written relative to this dir too
    if man is None:
        man, source = {}, "taxonomy"
    tax = jload(cfg["taxonomy"]) or {}

    g = {**cfg["guideline"], **{k: v for k, v in (man.get("guideline") or {}).items() if v}}
    rubric = [r for r in (man.get("rubric") or []) if isinstance(r, dict) and r.get("id")] or taxonomy_rubric(bench, tax)
    taxmap = {h["id"]: h for h in tax.get("hazards", [])}
    for r in rubric:  # fill gaps from the taxonomy
        t = taxmap.get(r["id"], {})
        r.setdefault("name", t.get("name")); r.setdefault("room", t.get("room"))
        r["name"] = r.get("name") or t.get("name") or r["id"]; r["room"] = r.get("room") or t.get("room")
        r["type"] = r.get("type") or t.get("type")
        r["citation"] = cite_text(r.get("citation")) or cite_text(t.get("citation")) or None
    if not g.get("excerpt"):  # dementia fallback: the unique guideline lines its rubric cites
        g["excerpt"] = list(dict.fromkeys(r["citation"] for r in rubric if r.get("citation")))
    ex = g.get("excerpt") or []
    for r in rubric:
        r["line"] = match_line(r.get("citation"), ex)
    icd = ((jload(DATA / "icd10_fall_codes.json") or {}).get("map") or {}) if bench == "falls" else {}
    for r in rubric:  # approximate ICD-10-CM external-cause code for the fall mechanism (falls only)
        c = icd.get(r["id"])
        if isinstance(c, dict) and c.get("code"):
            r["icd"] = {"code": c["code"], "title": c.get("title")}

    bases = {b.get("id"): b.get("path") for b in man.get("bases") or [] if isinstance(b, dict) and b.get("accepted", True) is not False}

    def base_src(base):
        """(dir, relpath) of an item's clean base room: manifest bases list, a direct path, or data/renders/<base>.jpg."""
        if not isinstance(base, str) or not base:
            return None, None
        if base in bases and bases[base]:
            return mdir, bases[base]
        if re.search(r"\.(jpe?g|png|webp)$", base, re.I):
            return mdir, base
        for d in (DATA / "renders", DATA / "benchmarks" / bench / "renders"):
            if (d / f"{base}.jpg").exists():
                return d, f"{base}.jpg"
        return None, None

    items = []
    for it in man.get("items") or []:
        if not isinstance(it, dict) or not it.get("id"):
            continue
        img = site_img(bench, it.get("image"), mdir, "img", it["id"], 1600)
        if not img:
            continue  # image not written yet
        th = site_img(bench, it.get("thumb"), mdir, "thumb", it["id"], 560) or site_img(bench, it.get("image"), mdir, "thumb", it["id"], 560)
        base = it.get("base")
        bd, brel = base_src(base)
        base_img = site_img(bench, brel, bd, "base", str(base), 1200) if bd else None
        hz = [h for h in it.get("hazards") or [] if isinstance(h, dict)]
        room = it.get("room") or next((taxmap.get(h.get("id"), {}).get("room") or next((r["room"] for r in rubric if r["id"] == h.get("id")), None) for h in hz), None)
        if not room and isinstance(base, str):
            room = base.split("-")[0].split("/")[-1]
        checks = {c.get("key"): c for c in ((it.get("verify") or {}).get("checks") or []) if isinstance(c, dict)}
        trace = []
        for k, t in enumerate(it.get("prompt_trace") or []):
            if not isinstance(t, dict):
                continue
            t = dict(t)
            t["citation"] = cite_text(t.get("citation")) or None
            t["line"] = match_line(t["citation"], ex) if t["citation"] else None
            t["step_img"] = site_img(bench, f"steps/{it['id']}-s{k}.jpg", mdir, "steps", f"{it['id']}-s{k}", 720)
            ck = checks.get(t.get("id")) or checks.get(t.get("label"))
            if ck:
                t["check"] = {"visible": ck.get("visible"), "looks_safe": ck.get("looks_safe"), "note": ck.get("note")}
            trace.append(t)
        items.append({"id": it["id"], "level": it.get("level"), "img": img, "thumb": th or img, "base": base, "base_img": base_img,
                      "room": room, "negative": bool(it.get("negative")), "hazards": hz,
                      "distractors": [d for d in it.get("distractors") or [] if isinstance(d, dict)],
                      "conditions": it.get("conditions") or [], "trace": trace, "verified": it.get("verified"),
                      "photoreal": (it.get("verify") or {}).get("photoreal")})

    levels = [l for l in man.get("levels") or [] if isinstance(l, dict)]
    for l in levels:
        l["have"] = sum(1 for i in items if str(i["level"]) == str(l.get("level")))

    # 3D worlds: data/worlds/worlds.json filtered by bench (missing bench = falls), plus any manifest.worlds not already there.
    # Card buttons: world.html?id=<id> (walkable viewer) / Marble viewer URL / walk.html?w=<id> (model walkthrough).
    worlds, seen = [], set()
    walks = (jload(DATA / "walks" / "index.json") or {}).get("worlds", {})

    def add_world(wid, w, base_dir):
        if not wid or wid in seen or (w.get("status") not in (None, "done")):
            return
        seen.add(wid)
        th = site_img(bench, w.get("thumb") or w.get("thumbnail") or f"{wid}.thumb.jpg", base_dir, "worlds", str(wid), 800)
        worlds.append({"id": wid, "title": w.get("title") or wid, "hazard": w.get("hazard"), "viewer_url": w.get("viewer_url") or w.get("url"),
                       "thumb": th, "walk": f"walk.html?w={wid}" if wid in walks else "walk.html"})

    for wid, w in (jload(DATA / "worlds" / "worlds.json") or {}).items():
        if isinstance(w, dict) and (w.get("bench") or "falls") == bench:
            add_world(wid, w, ROOT if str(w.get("thumbnail", "")).startswith("data/") else DATA / "worlds")
    for w in man.get("worlds") or []:
        if isinstance(w, dict):
            add_world(w.get("id") or w.get("scene_id") or w.get("world_id"), w, mdir)

    curve = {}
    for m, by in (man.get("difficulty_curve") or {}).items():
        if isinstance(by, dict):
            pts = {}
            for k, v in by.items():
                n = re.sub(r"\D", "", str(k))
                if n and isinstance(v, dict):
                    pts[int(n)] = {"recall": v.get("recall"), "ff": v.get("distractor_false_flag")}
            if pts:
                curve[m] = pts

    live = bool(items)
    return {"bench": bench, "title": cfg["title"], "subtitle": man.get("title"), "method": man.get("method"), "publisher": cfg["publisher"],
            "guideline": g, "rubric": rubric, "levels": levels, "items": items, "worlds": worlds, "curve": curve,
            "report": cfg["report"], "status": "live" if live else "generating", "source": source}


# ---------------------------------------------------------------- render
def page(body_tpl, title, data, active):
    base = (SRC / "library_template_base.html").read_text()
    body = (SRC / body_tpl).read_text()
    html = base.replace("{{TITLE}}", title).replace("{{BODY}}", body).replace("/*DATA*/null", json.dumps(data, separators=(",", ":")))
    return html.replace(f'data-nav="{active}"', f'data-nav="{active}" class="on"')


def main():
    benches = [load_bench(b, c) for b, c in BENCHES.items()]
    cards = [{"bench": b["bench"], "title": b["title"], "publisher": b["publisher"], "guideline": b["guideline"].get("name"),
              "rubric": len(b["rubric"]), "images": len(b["items"]), "levels": len(b["levels"]), "worlds": len(b["worlds"]),
              "status": b["status"], "cover": (b["items"][-1]["thumb"] if b["items"] else (b["worlds"][0]["thumb"] if b["worlds"] else None))}
             for b in benches]
    (SITE / "guidelines.html").write_text(page("library_template_index.html", "HealthDojo · Guideline library",
                                               {"cards": cards, "coming": COMING}, "guidelines"))
    print("wrote site/guidelines.html")
    for b in benches:
        out = SITE / f"guideline-{b['bench']}.html"
        out.write_text(page("library_template_guideline.html", f"HealthDojo · {b['title']}", b, "guidelines"))
        print(f"wrote {out.relative_to(ROOT)}  [{b['source']}] rubric={len(b['rubric'])} levels={len(b['levels'])} "
              f"items={len(b['items'])} worlds={len(b['worlds'])} curve={len(b['curve'])} status={b['status']}")


if __name__ == "__main__":
    main()
