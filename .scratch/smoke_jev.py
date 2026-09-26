import json, time, pathlib, requests
key = pathlib.Path.home().joinpath(".config/typesafe/api_key").read_text().strip()
state = {"model_output": "There is an extension cord running across the hallway floor and a throw rug with a curled corner near the bathroom door.",
         "ground_truth_hazard": "loose rug / curled rug edge"}
q = {"mentions_gt": {"type":"noul","instructions":"Does `model_output` identify the hazard described in `ground_truth_hazard`?"},
     "category": {"type":"choice","instructions":"Which fall-hazard category best matches the first hazard in `model_output`?",
                  "criteria":{"cord":"Electrical or phone cord across walkway","rug":"Loose, curled or unsecured rug/mat","clutter":"Objects on floor","lighting":"Poor lighting","stairs":"Stair defects / no rails","none":None}},
     "severity": {"type":"score","instructions":"How severe is the fall risk described in `model_output` for a frail older adult?","criteria":["minimal","moderate","high"]}}
for i in range(3):
    t=time.perf_counter()
    r=requests.post("https://api.typesafe.ai/v1/systemone",headers={"Authorization":f"Bearer {key}"},json={"state":state,"model":"jev-latest","questions":q},timeout=60)
    print(r.status_code, f"{(time.perf_counter()-t)*1000:.0f}ms", json.dumps(r.json())[:600] if r.ok else r.text[:200])
