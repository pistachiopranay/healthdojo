"""Run every model on every scene with the same prompt; cache raw outputs in data/outputs/<model>/<scene>.json."""
import base64, json, os, re, sys, concurrent.futures as cf, pathlib
from dotenv import load_dotenv
from common import ROOT, DATA, SCENES, taxonomy

load_dotenv(ROOT / ".env")
OUT = DATA / "outputs"
TAX = taxonomy()

PROMPT = """You are assessing a photo of a home for fall hazards before an older adult returns home after hip or knee replacement surgery (they will use a walker).

List every hazard from this checklist that is present in the photo. Only use these ids:
{checklist}

Return ONLY JSON: {{"hazards": [{{"id": "<id>", "severity": "low|medium|high", "evidence": "<what you see>", "box": [x0, y0, x1, y1]}}]}}
box = where the hazard is, in 0-1000 normalized image coordinates (omit for whole-room issues). Return {{"hazards": []}} if the room is safe."""


def checklist():
    return "\n".join(f"- {h['id']}: {h['name']}" for h in TAX.values())


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        h = json.loads(m.group(0))["hazards"] if m else []
        if isinstance(h, str):
            h = json.loads(h)
        return [x for x in h if isinstance(x, dict)]
    except Exception:
        return [{"id": i} for i in dict.fromkeys(re.findall(r"[A-Z]{3,5}-0\d", text))]


def anthropic_call(model):
    import anthropic
    client = anthropic.Anthropic()
    def call(img_bytes, prompt):
        r = client.messages.create(model=model, max_tokens=1500, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode()}},
            {"type": "text", "text": prompt}]}])
        return "".join(b.text for b in r.content if b.type == "text")
    return call


def bedrock_call(model_id):
    import boto3
    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    def call(img_bytes, prompt):
        r = client.converse(modelId=model_id, messages=[{"role": "user", "content": [
            {"image": {"format": "jpeg", "source": {"bytes": img_bytes}}}, {"text": prompt}]}],
            inferenceConfig={"maxTokens": 1500, "temperature": 0})
        return r["output"]["message"]["content"][0]["text"]
    return call


def openai_call(model):
    from openai import OpenAI
    client = OpenAI()
    def call(img_bytes, prompt):
        r = client.responses.create(model=model, input=[{"role": "user", "content": [
            {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode()},
            {"type": "input_text", "text": prompt}]}])
        return r.output_text
    return call


# name -> factory. Only models whose credentials are present are run.
MODELS = {
    "claude-opus-5.5": (lambda: anthropic_call("claude-opus-5-5"), "ANTHROPIC_API_KEY"),
    "claude-sonnet-5": (lambda: anthropic_call("claude-sonnet-5"), "ANTHROPIC_API_KEY"),
    "claude-haiku-4.5": (lambda: anthropic_call("claude-haiku-4-5-20251001"), "ANTHROPIC_API_KEY"),
    "nova-pro": (lambda: bedrock_call("us.amazon.nova-pro-v1:0"), "AWS_PROFILE"),
    "nova-2-lite": (lambda: bedrock_call("us.amazon.nova-2-lite-v1:0"), "AWS_PROFILE"),
    "llama-4-maverick": (lambda: bedrock_call("us.meta.llama4-maverick-17b-instruct-v1:0"), "AWS_PROFILE"),
    "pixtral-large": (lambda: bedrock_call("us.mistral.pixtral-large-2502-v1:0"), "AWS_PROFILE"),
    "qwen3-vl": (lambda: bedrock_call("qwen.qwen3-vl-235b-a22b"), "AWS_PROFILE"),
    "mistral-large-3": (lambda: bedrock_call("mistral.mistral-large-3-675b-instruct"), "AWS_PROFILE"),
    "gemma-3-27b": (lambda: bedrock_call("google.gemma-3-27b-it"), "AWS_PROFILE"),
    "gpt": (lambda: openai_call(os.getenv("OPENAI_MODEL", "gpt-5")), "OPENAI_API_KEY"),
}


def run(model_name, scenes):
    factory, env = MODELS[model_name]
    if not os.getenv(env):
        print(f"skip {model_name}: no {env}")
        return
    call = factory()
    d = OUT / model_name
    d.mkdir(parents=True, exist_ok=True)
    prompt = PROMPT.format(checklist=checklist())
    def one(s):
        f = d / f"{s['id']}.json"
        if f.exists():
            return
        try:
            text = call((DATA / s["image"]).read_bytes(), prompt)
            f.write_text(json.dumps({"scene": s["id"], "raw": text, "hazards": parse(text)}, indent=1))
            print(model_name, s["id"], "ok", flush=True)
        except Exception as e:
            print(model_name, s["id"], "ERR", str(e)[:200], flush=True)
    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(one, scenes))


if __name__ == "__main__":
    scenes = [json.loads(p.read_text()) for p in sorted(SCENES.glob("*.json"))]
    scenes = [s for s in scenes if s.get("verified", True)]
    names = sys.argv[1:] or list(MODELS)
    for n in names:
        run(n, scenes)
