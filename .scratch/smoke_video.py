import boto3, time
c = boto3.client("bedrock-runtime", region_name="us-east-1")
v = open("test.mp4","rb").read()
for m in ["us.amazon.nova-lite-v1:0","us.amazon.nova-pro-v1:0","us.amazon.nova-2-lite-v1:0","us.anthropic.claude-haiku-4-5-20251001-v1:0"]:
    t=time.time()
    try:
        r = c.converse(modelId=m, messages=[{"role":"user","content":[
          {"video":{"format":"mp4","source":{"bytes":v}}},{"text":"Describe this video in one sentence."}]}], inferenceConfig={"maxTokens":80})
        print("OK ", m, f"{time.time()-t:.1f}s", r["usage"], r["output"]["message"]["content"][0]["text"][:120])
    except Exception as e: print("ERR", m, str(e)[:200])
