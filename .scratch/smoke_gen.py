import boto3, json, base64, io, time
from PIL import Image
c = boto3.client("bedrock-runtime", region_name="us-east-1")
base = Image.new("RGB",(512,512),(210,200,180)); b=io.BytesIO(); base.save(b,"PNG"); b64=base64.b64encode(b.getvalue()).decode()
t=time.time()
try:
    body={"taskType":"INPAINTING","inPaintingParams":{"image":b64,"text":"a loose throw rug with a curled edge on a wooden floor","maskPrompt":"floor"},
          "imageGenerationConfig":{"numberOfImages":1,"width":512,"height":512,"cfgScale":7.0,"seed":1}}
    r=c.invoke_model(modelId="amazon.nova-canvas-v1:0", body=json.dumps(body)); out=json.loads(r["body"].read())
    open("canvas_out.png","wb").write(base64.b64decode(out["images"][0])); print("OK nova-canvas inpaint", f"{time.time()-t:.1f}s")
except Exception as e: print("ERR nova-canvas", str(e)[:250])
t=time.time()
try:
    mask=Image.new("L",(512,512),0); mask.paste(255,(100,300,400,480)); mb=io.BytesIO(); mask.save(mb,"PNG")
    body={"image":b64,"mask":base64.b64encode(mb.getvalue()).decode(),"prompt":"a loose throw rug with a curled edge","output_format":"png"}
    r=c.invoke_model(modelId="us.stability.stable-image-inpaint-v1:0", body=json.dumps(body)); out=json.loads(r["body"].read())
    open("stab_out.png","wb").write(base64.b64decode(out["images"][0])); print("OK stability inpaint", f"{time.time()-t:.1f}s", {k:v for k,v in out.items() if k!="images"})
except Exception as e: print("ERR stability", str(e)[:250])
