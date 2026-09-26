"""Score model outputs against scene ground truth -> data/results.json."""
import json, collections
from common import DATA, SCENES, taxonomy, hazard_type

TAX = taxonomy()


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / u if u > 0 else 0


def main():
    scenes = {s["id"]: s for s in (json.loads(p.read_text()) for p in SCENES.glob("*.json")) if s.get("verified", True)}
    known_absent = collections.defaultdict(set)
    for s in scenes.values():
        if s["kind"] == "edit":
            known_absent[s["base"]] |= {h["id"] for h in s["hazards"]}
    models = sorted(p.name for p in (DATA / "outputs").iterdir() if p.is_dir())
    board, per_scene = [], {}
    for m in models:
        c = collections.Counter(); by_type = collections.defaultdict(collections.Counter); by_room = collections.defaultdict(collections.Counter)
        by_haz = collections.defaultdict(collections.Counter); fa = collections.Counter(); loc = []
        for sid, s in scenes.items():
            f = DATA / "outputs" / m / f"{sid}.json"
            if not f.exists():
                continue
            out = json.loads(f.read_text())
            pred = {h.get("id"): h for h in out["hazards"] if h.get("id") in TAX}
            gt = {h["id"]: h for h in s["hazards"]}
            # known negatives: hazards seeded into sibling edits of the same base are verified absent here
            for neg in known_absent.get(s.get("base", sid), set()) - set(gt):
                fa["fp" if neg in pred else "tn"] += 1
            for hid, g in gt.items():
                hit = hid in pred
                c["tp" if hit else "fn"] += 1
                by_type[g["type"]]["tp" if hit else "fn"] += 1
                by_room[s["room"]]["tp" if hit else "fn"] += 1
                by_haz[hid]["tp" if hit else "fn"] += 1
                if hit and g.get("box") and pred[hid].get("box") and len(pred[hid]["box"]) == 4:
                    loc.append(iou(g["box"], pred[hid]["box"]))
            # only count predictions in edit scenes as FP when they are the room's seeded-hazard family
            # (a base room may contain real incidental hazards; FP on clean rooms is reported separately)
            per_scene.setdefault(sid, {})[m] = {"pred": list(pred), "raw": out["hazards"]}
        rec = lambda k: round(k["tp"] / max(1, k["tp"] + k["fn"]), 3)
        board.append({"model": m, "recall": rec(c), "tp": c["tp"], "fn": c["fn"],
                      "false_alarm": round(fa["fp"] / max(1, fa["fp"] + fa["tn"]), 3),
                      "by_type": {t: rec(k) for t, k in by_type.items()},
                      "by_room": {r: rec(k) for r, k in by_room.items()},
                      "by_hazard": {h: rec(k) for h, k in by_haz.items()},
                      "loc_iou": round(sum(loc) / len(loc), 3) if loc else None})
    board.sort(key=lambda r: -r["recall"])
    res = {"leaderboard": board, "scenes": list(scenes.values()), "predictions": per_scene,
           "taxonomy": {k: {"name": v["name"], "room": v["room"], "type": hazard_type(k)} for k, v in TAX.items()}}
    (DATA / "results.json").write_text(json.dumps(res, indent=1))
    for r in board:
        print(f"{r['model']:20} recall={r['recall']}  types={r['by_type']}  false_alarm={r['false_alarm']}")


if __name__ == "__main__":
    main()
