"""Run every model on every scene with the same prompt; cache raw outputs in data/outputs/<model>/<scene>.json."""
import base64, json, os, re, sys, concurrent.futures as cf, pathlib
from dotenv import load_dotenv
from common import ROOT, DATA, SCENES, BENCH, bench_meta, taxonomy

load_dotenv(ROOT / ".env", override=True)
if os.getenv("AWS_ACCESS_KEY_ID"):
    os.environ.pop("AWS_PROFILE", None)  # event workshop account creds win
OUT = DATA / "outputs"
TAX = taxonomy()

PROMPT = """You are assessing a photo of a home for fall hazards before an older adult returns home after hip or knee replacement surgery (they will use a walker).

List every hazard from this checklist that is present in the photo. Only use these ids:
{checklist}

Return ONLY JSON: {{"hazards": [{{"id": "<id>", "severity": "low|medium|high", "evidence": "<what you see>", "box": [x0, y0, x1, y1]}}]}}
box = where the hazard is, in 0-1000 normalized image coordinates (omit for whole-room issues). Return {{"hazards": []}} if the room is safe."""
if BENCH:  # each benchmark states its own patient context
    PROMPT = bench_meta().get("model_prompt", PROMPT)


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
        pat = r"[A-Z]{3,5}-[A-Z]?\d\d" if BENCH else r"[A-Z]{3,5}-0\d"
        return [{"id": i} for i in dict.fromkeys(re.findall(pat, text))]


def anthropic_call(model):
    import anthropic
    client = anthropic.Anthropic()
    def call(img_bytes, prompt):
        r = client.messages.create(model=model, max_tokens=1500, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png" if img_bytes[:4] == b"\x89PNG" else "image/jpeg", "data": base64.b64encode(img_bytes).decode()}},
            {"type": "text", "text": prompt}]}])
        return "".join(b.text for b in r.content if b.type == "text")
    return call


def bedrock_call(model_id):
    import boto3
    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    def call(img_bytes, prompt):
        fmt = "png" if img_bytes[:4] == b"\x89PNG" else "jpeg"
        kw = dict(modelId=model_id, messages=[{"role": "user", "content": [
            {"image": {"format": fmt, "source": {"bytes": img_bytes}}}, {"text": prompt}]}])
        try:
            r = client.converse(**kw, inferenceConfig={"maxTokens": 4000, "temperature": 0})
        except client.exceptions.ValidationException as e:
            if "temperature" not in str(e):
                raise
            r = client.converse(**kw, inferenceConfig={"maxTokens": 4000})
        return "".join(b.get("text", "") for b in r["output"]["message"]["content"])
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


def openrouter_call(model):
    from openai import OpenAI
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
    def call(img_bytes, prompt):
        mime = "image/png" if img_bytes[:4] == b"\x89PNG" else "image/jpeg"
        r = client.chat.completions.create(model=model, max_tokens=4000, temperature=0, messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64," + base64.b64encode(img_bytes).decode()}},
            {"type": "text", "text": prompt}]}])
        if not r.choices or not (r.choices[0].message.content or "").strip():
            raise RuntimeError(f"empty response from {model}")
        return r.choices[0].message.content
    return call


def _or(model):
    return (lambda: openrouter_call(model), "OPENROUTER_API_KEY", "OpenRouter")


# name -> (factory, required env, provider). Bedrock = AWS event workshop account.
MODELS = {
    "claude-opus-5.5": (lambda: anthropic_call("claude-opus-5-5"), "ANTHROPIC_API_KEY", "Anthropic API"),
    "gpt-6-luna": (lambda: bedrock_call("us.openai.gpt-6-luna"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "gpt-6-astra": (lambda: bedrock_call("us.openai.gpt-6-astra"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "gpt-5.6-sol": (lambda: bedrock_call("us.openai.gpt-5.6-sol"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "gpt-5.6-terra": (lambda: bedrock_call("us.openai.gpt-5.6-terra"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "grok-4.6": (lambda: bedrock_call("us.xai.grok-4.6"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "kimi-k3": (lambda: bedrock_call("us.moonshotai.kimi-k3"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "claude-sonnet-5": (lambda: bedrock_call("us.anthropic.claude-sonnet-5"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "claude-haiku-4.5": (lambda: bedrock_call("us.anthropic.claude-haiku-4-5-20251001-v1:0"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "nova-pro": (lambda: bedrock_call("amazon.nova-pro-v1:0"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "nova-2-lite": (lambda: bedrock_call("us.amazon.nova-2-lite-v1:0"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "llama-4-maverick": (lambda: bedrock_call("us.meta.llama4-maverick-17b-instruct-v1:0"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "qwen3-vl": (lambda: bedrock_call("qwen.qwen3-vl-235b-a22b"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "mistral-large-3": (lambda: bedrock_call("mistral.mistral-large-3-675b-instruct"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "gemma-3-27b": (lambda: bedrock_call("google.gemma-3-27b-it"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    "nemotron-nano-vl": (lambda: bedrock_call("nvidia.nemotron-nano-12b-v2"), "AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    # added post-hackathon via OpenRouter (models not on the event's Bedrock account)
    "claude-fable-5.1": (lambda: anthropic_call("claude-fable-5-1"), "ANTHROPIC_API_KEY", "Anthropic API"),
    "claude-opus-5": (lambda: anthropic_call("claude-opus-5"), "ANTHROPIC_API_KEY", "Anthropic API"),
    "gpt-6-sol": _or("openai/gpt-6-sol"),
    "gpt-6-astra": _or("openai/gpt-6-astra"),
    "gemini-3.1-pro": _or("google/gemini-3.1-pro-preview"),
    "gemini-3.8-flash": _or("google/gemini-3.8-flash"),
    "grok-4.7": _or("x-ai/grok-4.7"),
    "qwen3.8-max": _or("qwen/qwen3.8-max-0902"),
    "muse-spark-1.3": _or("meta/muse-spark-1.3"),
    "glm-5v-turbo": _or("z-ai/glm-5v-turbo"),
    "seed-2.1-turbo": _or("bytedance-seed/seed-2-1-turbo"),
    "mistral-medium-3.5": _or("mistralai/mistral-medium-3-5"),
    "deepseek-v4-flash-vision": _or("deepseek/deepseek-v4-flash-vision-exp"),
}

# Same model weights served via OpenRouter, used only to fill scenes the Bedrock run missed.
OPENROUTER_FALLBACK = {
    "claude-sonnet-5": "anthropic/claude-sonnet-5", "claude-haiku-4.5": "anthropic/claude-haiku-4.5",
    "gpt-5.6-sol": "openai/gpt-5.6-sol", "gpt-5.6-terra": "openai/gpt-5.6-terra",
    "grok-4.6": "x-ai/grok-4.6", "kimi-k3": "moonshotai/kimi-k3",
    "llama-4-maverick": "meta-llama/llama-4-maverick", "qwen3-vl": "qwen/qwen3-vl-235b-a22b-instruct",
    "gemma-3-27b": "google/gemma-3-27b-it", "nova-pro": "amazon/nova-pro-v1", "nova-2-lite": "amazon/nova-2-lite-v1",
}
if os.getenv("VIA_OPENROUTER"):
    for _n, _m in OPENROUTER_FALLBACK.items():
        MODELS[_n] = _or(_m)


def small_jpeg(img_bytes, side=1280):
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def run(model_name, scenes):
    factory, env, _ = MODELS[model_name]
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
            img = (DATA / s["image"]).read_bytes()
            try:
                text = call(img, prompt)
            except Exception:
                text = call(small_jpeg(img), prompt)  # some Bedrock models reject large/PNG payloads
            if not (text or "").strip():
                raise RuntimeError("empty response")  # a failed call, not "no hazards"; leave uncached so a rerun retries it
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
