import boto3, json, time, io, os
from PIL import Image, ImageDraw
img = Image.new("RGB", (512, 384), "white"); d = ImageDraw.Draw(img)
d.rectangle([0,300,512,384], fill=(180,140,100))  # floor
d.rectangle([150,280,360,300], fill=(200,30,30))  # rug edge
d.line([(50,310),(460,340)], fill="black", width=4)  # cord
buf = io.BytesIO(); img.save(buf, "PNG"); png = buf.getvalue()
tool = {"toolSpec": {"name": "report_hazards", "description": "Report fall hazards seen",
  "inputSchema": {"json": {"type": "object", "properties": {"hazards": {"type": "array", "items": {"type": "object",
     "properties": {"type": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["type","confidence"]}}},
     "required": ["hazards"]}}}}
c = boto3.client("bedrock-runtime", region_name="us-east-1")
models = os.environ.get("MODELS","").split(",")
for m in models:
    t=time.time()
    try:
        r = c.converse(modelId=m, messages=[{"role":"user","content":[
            {"image":{"format":"png","source":{"bytes":png}}},
            {"text":"This is a schematic of a room floor. List any trip/fall hazards via the tool."}]}],
            toolConfig={"tools":[tool], "toolChoice":({"any":{}} if os.environ.get("ANY") else {"tool":{"name":"report_hazards"}})},
            inferenceConfig={"maxTokens":400})
        blocks = r["output"]["message"]["content"]
        tu = [b["toolUse"]["input"] for b in blocks if "toolUse" in b]
        print(f"OK  {m} {time.time()-t:.1f}s usage={r['usage']} tool={json.dumps(tu)[:160]}")
    except Exception as e:
        print(f"ERR {m} {time.time()-t:.1f}s {type(e).__name__}: {str(e)[:200]}")
