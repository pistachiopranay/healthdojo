"""Verify each edit scene: (1) a judge model confirms the seeded hazard is visible and nothing else changed,
(2) pixel diff against the base gives the ground-truth box. Writes verified/box back into scene json."""
import base64, json, concurrent.futures as cf
import numpy as np
from PIL import Image, ImageFilter
from dotenv import load_dotenv
from common import ROOT, DATA, SCENES, taxonomy

load_dotenv(ROOT / ".env")
TAX = taxonomy()
JUDGE = "claude-opus-5-5"

Q = """Image 1 is the original room. Image 2 was edited to add exactly one fall hazard: "{name}" ({desc}).
Answer ONLY JSON: {{"hazard_visible": true|false, "other_major_changes": true|false, "note": "<short>"}}
hazard_visible = a careful home-safety assessor looking only at image 2 would clearly see this hazard."""


def diff_box(base, edit):
    a = Image.open(base).convert("L").resize((500, 375)); b = Image.open(edit).convert("L").resize((500, 375))
    d = np.abs(np.asarray(a, float) - np.asarray(b, float))
    d = np.asarray(Image.fromarray(d.astype("uint8")).filter(ImageFilter.GaussianBlur(4)))
    mask = d > max(25, np.percentile(d, 97))
    if mask.mean() < 0.002:
        return None, float(mask.mean())
    ys, xs = np.where(mask)
    x0, x1 = np.percentile(xs, [2, 98]); y0, y1 = np.percentile(ys, [2, 98])
    return [int(x0 * 2), int(y0 * 1000 / 375), int(x1 * 2), int(y1 * 1000 / 375)], float(mask.mean())


def judge(base, edit, h):
    import anthropic
    img = lambda p: {"type": "image", "source": {"type": "base64", "media_type": "image/png" if p.read_bytes()[:4] == b"\x89PNG" else "image/jpeg", "data": base64.b64encode(p.read_bytes()).decode()}}
    r = anthropic.Anthropic().messages.create(model=JUDGE, max_tokens=1500, messages=[{"role": "user", "content": [
        img(base), img(edit), {"type": "text", "text": Q.format(name=h["name"], desc=h["visual_description"])}]}])
    t = "".join(b.text for b in r.content if b.type == "text")
    return json.loads(t[t.find("{"):t.rfind("}") + 1])


def one(p):
    s = json.loads(p.read_text())
    if s["kind"] != "edit" or "verified" in s:
        return
    base, edit = DATA / f"renders/{s['base']}.jpg", DATA / s["image"]
    h = TAX[s["hazards"][0]["id"]]
    box, changed = diff_box(base, edit)
    try:
        v = judge(base, edit, h)
    except Exception as e:
        v = {"hazard_visible": False, "note": f"judge error {e}"}
    s["verify"] = v | {"changed_frac": round(changed, 4)}
    s["verified"] = bool(v.get("hazard_visible"))
    if box and s["hazards"][0]["type"] in ("object", "absence"):
        s["hazards"][0]["box"] = box
    p.write_text(json.dumps(s, indent=1))
    print(s["id"], "VERIFIED" if s["verified"] else "REJECT", v.get("note", ""), flush=True)


if __name__ == "__main__":
    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(one, sorted(SCENES.glob("*.json"))))
