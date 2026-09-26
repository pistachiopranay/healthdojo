import boto3, json, io, time
from PIL import Image, ImageDraw
img = Image.new("RGB",(512,384),"white"); d=ImageDraw.Draw(img); d.line([(50,310),(460,340)],fill="black",width=4)
b=io.BytesIO(); img.save(b,"JPEG"); jpg=b.getvalue()
schema={"type":"object","properties":{"hazards":{"type":"array","items":{"type":"object","properties":{
  "category":{"type":"string","enum":["cord","rug","clutter","lighting","stairs","bathroom","other"]},
  "confidence":{"type":"number"}},"required":["category","confidence"],"additionalProperties":False}}},
  "required":["hazards"],"additionalProperties":False}
c=boto3.client("bedrock-runtime",region_name="us-east-1")
for m in ["us.anthropic.claude-haiku-4-5-20251001-v1:0","us.anthropic.claude-sonnet-4-6","us.amazon.nova-2-lite-v1:0","us.amazon.nova-pro-v1:0","qwen.qwen3-vl-235b-a22b","mistral.mistral-large-3-675b-instruct","us.meta.llama4-maverick-17b-instruct-v1:0","us.mistral.pixtral-large-2502-v1:0"]:
    t=time.time()
    try:
        r=c.converse(modelId=m,messages=[{"role":"user","content":[{"image":{"format":"jpeg","source":{"bytes":jpg}}},{"text":"List fall hazards."}]}],
          inferenceConfig={"maxTokens":300},
          outputConfig={"textFormat":{"type":"json_schema","structure":{"jsonSchema":{"schema":json.dumps(schema),"name":"hazards"}}}})
        txt=r["output"]["message"]["content"][0]["text"]; json.loads(txt); print("OK ",m,f"{time.time()-t:.1f}s",txt[:120])
    except Exception as e: print("ERR",m,f"{time.time()-t:.1f}s",type(e).__name__,str(e)[:180])
