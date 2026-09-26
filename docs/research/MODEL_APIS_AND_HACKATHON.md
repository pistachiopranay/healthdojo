---
title: "Model APIs (Bedrock, OpenAI, Gemini, Jev) and Hackathon Facts for HomeDojo"
tags: [homedojo, bedrock, openai, gemini, typesafe-jev, vision, hackathon, research]
status: active
created: 2026-09-26
---

# Model APIs and Hackathon Facts for HomeDojo

Researched 2026-09-26, 11:00-11:30 PT. Legend:
- **[LIVE]**: verified by a real API call from this laptop today (scripts in `.scratch/smoke_*.py`).
- **[DOC]**: taken from the cited official doc page.
- **[UNVERIFIED]**: secondary source or inference. Check before relying on it.

---

## 0. TL;DR for the build

1. **Bedrock works today through AWS profile `pistachio`** (`AWS_PROFILE=pistachio`, region `us-east-1`). The `default` profile's session has expired and `daiser-ops` has an invalid token. [LIVE]
2. **Blocker: Claude on Bedrock.** The first Claude calls succeeded around 11:02. Every Claude call after that failed with `ResourceNotFoundException: Model use case details have not been submitted for this account`, and `aws bedrock get-use-case-for-model-access` reports that the form was never filled out. Fixes: (a) someone with console access submits the Anthropic use-case form (Bedrock console, Model access), or (b) call Claude through the Anthropic API directly. `ANTHROPIC_API_KEY` is already set in `homedojo/.env`. [LIVE]
3. **Bedrock vision models confirmed working now:** Nova Lite, Nova Pro, Nova 2 Lite (all three also accept **video**), Qwen3-VL-235B, Mistral Large 3, Pixtral Large, Llama 4 Maverick and Scout, Gemma 3 27B, Ministral 3 14B, Nemotron Nano 12B v2, and Kimi K3. [LIVE]
4. **Catalog-listed but denied for this account:** Claude Opus 5 / 5.5 / 4.7 / 4.8, Sonnet 5, Fable 5, all `openai.gpt-*` on Bedrock, and Grok 4.6. Opus 4.1 and Sonnet 4 are marked "Legacy", as is Nova Premier (end of life). [LIVE]
5. **Bedrock image editing:** **Stability `us.stability.stable-image-inpaint-v1:0` works** (about 16 s, $0.07/image). **Nova Canvas is denied** ("Legacy, not used in last 30 days"). [LIVE]
6. **OpenAI:** `OPENAI_API_KEY` is **not set** in the shell env, and it is **empty** in `homedojo/.env`. We need the sponsor key. [LIVE]
7. **Jev is text only.** It cannot look at images. Use it as the **grader/normalizer** over the VLM's text output. A 3-question call took 130-300 ms. [LIVE] [DOC]
8. **The hackathon runs today, 10:00-17:00 PT.** The event page lists **no judging criteria and no prior-work rules**. Ask the organizers on site. [DOC]

---

## 1. Local environment check [LIVE]

| Item | Result |
|---|---|
| `aws --version` | aws-cli/2.34.57 Python/3.14.5 Darwin arm64 |
| AWS profiles | `default` (session expired; needs `aws login`), **`pistachio` (OK)**, `daiser-ops` (InvalidClientTokenId) |
| AWS default region | none configured. Always pass `region_name="us-east-1"` / `--region us-east-1` |
| Node | v24.18.0 |
| Python | system `python3` = 3.9.6 (old). **Use `uv`** (0.9.26), e.g. `uv run --with boto3 python ...` |
| boto3 via uv | 1.43.103 (supports `outputConfig`) |
| ffmpeg | `/opt/homebrew/bin/ffmpeg` present (for frame sampling and clip building) |
| `OPENAI_API_KEY` in env | **No**. Also empty in `homedojo/.env` |
| Gemini key in env | **No** |
| TypeSafe key | Present at `~/.config/typesafe/api_key`, and `TYPESAFE_API_KEY` is set in `homedojo/.env` |
| `ANTHROPIC_API_KEY` | Set in `homedojo/.env` |

Note: `homedojo/.gitignore` covers `.env` but **not `.scratch/`**. The smoke scripts contain no secrets, but add `.scratch/` to `.gitignore` if you don't want them committed.

---

## 2. AWS Bedrock

### 2.1 Vision-capable models: catalog vs. actual access (us-east-1)

Catalog source: `aws bedrock list-foundation-models --region us-east-1` filtered to IMAGE/VIDEO input. Access source: live Converse calls, each sending one 512x384 PNG plus forced tool use.

| Model ID to call (inference profile) | Input | Access today | Forced tool (`toolChoice.tool`) | Native `outputConfig` JSON schema | ~Input tok for 512x384 img | Price in/out per 1M (us-east-1) |
|---|---|---|---|---|---|---|
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | text, image | worked once, **now blocked by use-case form** | yes | not tested (blocked) | 990 | $1.10 / $5.50 |
| `us.anthropic.claude-sonnet-4-6` | text, image | same as above | yes | not tested | 991 | $3.30 / $16.50 |
| `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | text, image | same as above | yes | - | 990 | $3.30 / $16.50 |
| `us.anthropic.claude-opus-4-6-v1` | text, image | same as above | yes | - | 991 | $5.50 / $27.50 |
| `us.anthropic.claude-opus-4-5-20251101-v1:0` | text, image | same as above | yes | - | 990 | $5.50 / $27.50 |
| `us.amazon.nova-lite-v1:0` | text, image, **video** | **OK** | yes | **no** (ValidationException) | 2118 | $0.06 / $0.24 |
| `us.amazon.nova-pro-v1:0` | text, image, **video** | **OK** | yes | no | 2118 | $0.80 / $3.20 |
| `us.amazon.nova-2-lite-v1:0` | text, image, **video** | **OK** | yes | no | 1198 | $0.33 / $2.75 |
| `qwen.qwen3-vl-235b-a22b` | text, image | **OK** | yes | **yes** | 409 | $0.53 / $2.66 |
| `mistral.mistral-large-3-675b-instruct` | text, image | **OK** | yes | **yes** | 409 | $0.50 / $1.50 |
| `us.mistral.pixtral-large-2502-v1:0` | text, image | **OK** | only `toolChoice.any` | no | 925 | $2.00 / $6.00 |
| `us.meta.llama4-maverick-17b-instruct-v1:0` | text, image | **OK** | only `auto` (no forced tool) | no | 1698 | $0.24 / $0.97 |
| `us.meta.llama4-scout-17b-instruct-v1:0` | text, image | **OK** | only `auto`; returned the array as a **JSON string** | no | 1698 | $0.17 / $0.66 |
| `google.gemma-3-27b-it` | text, image | **OK** | ignored the tool (no toolUse) | - | 287 | [UNVERIFIED] |
| `mistral.ministral-3-14b-instruct` | text, image | **OK** | ignored the tool | - | 409 | [UNVERIFIED] |
| `nvidia.nemotron-nano-12b-v2` | text, image | **OK** | ignored the tool | - | 3630 | [UNVERIFIED] |
| `us.moonshotai.kimi-k3` | text, image | **OK** (slow, 3 s) | yes, but returned the array as a **JSON string** | - | 522 | [UNVERIFIED] |
| `us.twelvelabs.pegasus-1-2-v1:0` | text, video | Converse **not supported** (use InvokeModel) | - | - | - | [UNVERIFIED] |
| Claude Opus 5 / 5.5 / 4.7 / 4.8, Sonnet 5, Fable 5 / 5.1 | text, image | **AccessDenied** ("not available for this account") | - | - | - | Opus 4.7/4.8 listed at $5.50/$27.50 |
| `openai.gpt-5.4/5.5/5.6-*/6-*` on Bedrock | text, image | **AccessDenied** | - | - | - | - |
| `xai.grok-4.6` | text, image | **AccessDenied** | - | - | - | - |
| `us.amazon.nova-premier-v1:0` | - | **End of life** | - | - | - | - |
| Claude Opus 4.1, Sonnet 4 | - | "Legacy, not used in 30 days", denied | - | - | - | - |

Prices come from the AWS Price List API (`aws pricing get-products --service-code AmazonBedrock` / `AmazonBedrockFoundationModels`, us-east-1). Claude prices are the "Regional" SKUs, which carry about a 10% uplift over Anthropic list prices. The public pricing page (https://aws.amazon.com/bedrock/pricing/) is JS-rendered, so it could not be scraped reliably. Treat these as list prices and confirm them in Cost Explorer.

**Rough cost per benchmark image** (one ~512x384 image plus a short prompt, measured input tokens × price): Nova Lite about $0.00013; Qwen3-VL about $0.0002; Llama 4 Maverick about $0.0004; Nova 2 Lite about $0.0004; Claude Haiku 4.5 about $0.0011; Nova Pro about $0.0017; Pixtral about $0.0019; Sonnet 4.6 about $0.0033; Opus 4.6 about $0.0055. Output tokens add a little more. A 1024x1024 image costs about 1300 visual tokens on Claude (see 2.3), so roughly 1.3x these Claude numbers. **A 200-image × 10-model sweep costs well under $10.**

**Regions.** us-east-1 has 70 vision/image-output models and us-west-2 has 63 (live `list-foundation-models`).
- Only in us-east-1: **Nova Canvas, Nova Reel**, Nova embeddings, Twelve Labs Marengo, and the Nova `:24k/:300k/:256k` provisioned variants.
- Only in us-west-2: **Stability SD3.5 Large, Stable Image Core/Ultra, Luma Ray v2**.
- Claude, Nova, Llama 4, Pixtral, OpenAI-on-Bedrock and Stability editing tools are available in both through `us.` and `global.` cross-region inference profiles.
- **Use us-east-1.**

The `global.anthropic.*` profile returned the same use-case-form error.

### 2.2 Converse request shape: image [DOC] [LIVE]

The ImageBlock takes `format` ∈ `png | jpeg | gif | webp`, and `source` is a union of `bytes` or `s3Location` (https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ImageBlock.html). boto3 base64-encodes raw bytes for you.

```python
# uv run --with boto3 python bedrock_image.py      (AWS_PROFILE=pistachio)
import boto3, json

brt = boto3.client("bedrock-runtime", region_name="us-east-1")
img = open("scene.jpg", "rb").read()

HAZARD_TOOL = {"toolSpec": {
    "name": "report_hazards",
    "description": "Report every fall hazard visible in the scene.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {"hazards": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["cord", "rug", "clutter", "lighting",
                             "stairs", "bathroom", "furniture", "pet", "other"]},
                "description": {"type": "string"},
                "confidence": {"type": "number"},
                "bbox_norm": {"type": "array", "items": {"type": "number"},
                              "description": "[x0,y0,x1,y1] in 0..1"}},
            "required": ["category", "description", "confidence"]}}},
        "required": ["hazards"]}}}}

resp = brt.converse(
    modelId="us.amazon.nova-2-lite-v1:0",           # or any row in 2.1
    system=[{"text": "You are an occupational therapist doing a home fall-risk assessment."}],
    messages=[{"role": "user", "content": [
        {"image": {"format": "jpeg", "source": {"bytes": img}}},   # image BEFORE text
        {"text": "Identify all fall hazards. Report via the tool."}]}],
    toolConfig={"tools": [HAZARD_TOOL],
                "toolChoice": {"tool": {"name": "report_hazards"}}},  # Llama: omit; Pixtral: {"any": {}}
    inferenceConfig={"maxTokens": 800, "temperature": 0},
)
hazards = next(b["toolUse"]["input"] for b in resp["output"]["message"]["content"] if "toolUse" in b)
if isinstance(hazards.get("hazards"), str):        # Kimi K3 / Llama Scout quirk
    hazards["hazards"] = json.loads(hazards["hazards"])
print(resp["usage"], hazards)
```

**Structured output with native JSON schema** (`outputConfig.textFormat`). Bedrock added this in Feb 2026 (https://aws.amazon.com/about-aws/whats-new/2026/02/structured-outputs-available-amazon-bedrock, https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html).
- **[LIVE] It worked on Qwen3-VL and Mistral Large 3.**
- It was **rejected** by Nova Lite, Nova Pro, Nova 2 Lite, Llama 4 and Pixtral ("doesn't support the outputConfig field").
- Per the doc it is supported for Claude 4.5+, but we could not test that because of the use-case block.
- Schema restrictions: `additionalProperties` must be `false`; no `minimum`/`maximum`/`minLength`; `minItems` only 0 or 1; no recursion. The first use of a new schema compiles a grammar, which can take minutes; the grammar is then cached for 24 h.
- **Recommendation: use forced tool use as the portable path.** Add `"strict": true` in `toolSpec` where it is supported. Use `outputConfig` only as an optimization.

```python
schema = {"type": "object", "additionalProperties": False, "required": ["hazards"],
          "properties": {"hazards": {"type": "array", "items": {"type": "object", "additionalProperties": False,
              "required": ["category", "confidence"],
              "properties": {"category": {"type": "string", "enum": ["cord", "rug", "clutter", "other"]},
                             "confidence": {"type": "number"}}}}}}
resp = brt.converse(modelId="qwen.qwen3-vl-235b-a22b", messages=[...],
    outputConfig={"textFormat": {"type": "json_schema",
        "structure": {"jsonSchema": {"schema": json.dumps(schema), "name": "hazards"}}}})
data = json.loads(resp["output"]["message"]["content"][0]["text"])
```

### 2.3 Image limits

- **Claude (any platform)** [DOC] (https://platform.claude.com/docs/en/build-with-claude/vision):
  - Formats: JPEG, PNG, GIF, WebP. Maximum 8000x8000 px.
  - **On Bedrock: 5 MB per image, base64 only.**
  - Up to 100 images per request for 200k-context models, 600 for others.
  - If a request has more than 20 images, each image must be at most 2000 px per side.
  - Tokens = ⌈w/28⌉ × ⌈h/28⌉. Standard models are capped at a 1568 px long edge and 1568 tokens. Claude 4.7+ models are capped at 2576 px and 4784 tokens.
  - **Pre-resize to about 1024-1568 px on the long edge.**
- **Nova** [DOC] (https://docs.aws.amazon.com/nova/latest/userguide/modalities-video.html): the total base64 payload must be at most **25 MB**. Measured cost: a 512x384 image took about 2.1k tokens on Nova v1 and about 1.2k on Nova 2 Lite.
- Converse also accepts `s3Location` for images and video, which avoids payload limits.

### 2.4 Video input (Nova only among the accessible models) [DOC] [LIVE]

**[LIVE]** A 3 s MP4 sent as Converse `bytes` worked on Nova Lite, Nova Pro and Nova 2 Lite, taking about 1 s each. Token counts: 2333 on v1 and 1095 on Nova 2 Lite.

Nova video facts [DOC]:
- **One video per request.**
- Formats: MP4, MOV, MKV, WebM, FLV, MPEG, MPG, WMV, 3GP (use `"three_gp"` as the format name for 3GP).
- Size: 25 MB inline; via S3 up to 1 GB per file.
- Frames are resized to 672x672. Sampling is **1 fps** for clips up to 16 min.
- **About 288 tokens per sampled frame on Nova v1** (10 s ≈ 2,880 tokens).
- Nova 2 doc: https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-multimodal-models.html

```python
video = open("walkthrough.mp4", "rb").read()
brt.converse(modelId="us.amazon.nova-2-lite-v1:0", messages=[{"role": "user", "content": [
    {"video": {"format": "mp4", "source": {"bytes": video}}},     # or {"s3Location": {"uri": "s3://..."}}
    {"text": "List fall hazards and the second they appear."}]}],
    toolConfig={...}, inferenceConfig={"maxTokens": 800})
```

Claude, Qwen, Llama and Pixtral have no video input on Bedrock. For those, **sample frames with ffmpeg** (for example `ffmpeg -i clip.mp4 -vf fps=1,scale=1024:-2 f_%02d.jpg`) and send them as multiple image blocks. That also puts every model on an equal footing for the video track. (The Claude "video" attempt failed only because of the use-case block. Claude does not take video natively anyway.)

Other video options:
- **Twelve Labs Pegasus 1.2** is in the catalog but rejects Converse. It needs InvokeModel. [LIVE] [UNVERIFIED body shape]
- **Nova 2 Omni** appears in the price list (image/video/audio input, image output: $0.30/1M input, $44/1M output image tokens). It is **not** in our `list-foundation-models` output, so it is probably not GA or not enabled here. [UNVERIFIED]

### 2.5 Image generation and editing on Bedrock (for building scenes and adding hazards)

| Model | Access | Use | Price |
|---|---|---|---|
| `us.stability.stable-image-inpaint-v1:0` | **OK** [LIVE] (512² edit in 15.9 s) | image + mask + prompt → add a hazard to a base image | $0.07/gen |
| `us.stability.stable-image-search-replace-v1:0` | listed (not tested) | `search_prompt` ("floor near the bed") + `prompt` ("a loose throw rug with curled edge"). No mask needed. **Best fit for "add a hazard"** | $0.07/gen |
| `us.stability.stable-image-erase-object-v1:0` | listed | remove a hazard to create a clean negative pair | $0.07/gen |
| `us.stability.stable-outpaint-v1:0`, `-control-structure`, `-control-sketch`, `-style-transfer`, `-search-recolor` | listed | variations or relighting ("dim lighting" hazard via recolor or structure) | ~$0.07 [UNVERIFIED] |
| `amazon.nova-canvas-v1:0` (us-east-1 only) | **Denied**: "Legacy, not used in last 30 days" [LIVE] | would offer INPAINTING with `maskPrompt` | $0.04 (1024 std) / $0.06 (premium) |
| `stability.sd3-5-large-v1:0`, `stable-image-core/ultra` (us-west-2 only) | listed | text-to-image base rooms | $0.08 / $0.04 / $0.14 |
| `amazon.nova-reel-v1:1` (us-east-1) | listed (not tested) | text/image → 6 s video (async, output to S3) | [UNVERIFIED] |

Stability inpaint body used in the live test (InvokeModel; the response is `{"images":[b64], "seeds":[...], "finish_reasons":[...]}`):

```python
body = {"image": b64_png, "mask": b64_mask_png,   # mask: white = repaint
        "prompt": "a loose throw rug with a curled edge", "output_format": "png"}
r = brt.invoke_model(modelId="us.stability.stable-image-inpaint-v1:0", body=json.dumps(body))
png = base64.b64decode(json.loads(r["body"].read())["images"][0])
```

---

## 3. OpenAI (sponsor)

**Key status:** not available locally yet. Nothing in this section was tested live. All of it is [DOC].

### 3.1 Vision via the Responses API

Source: https://developers.openai.com/api/docs/guides/images-vision
- Image parts are `{"type":"input_image","image_url":"data:image/jpeg;base64,..."}`, or `"file_id"`, or a public URL.
- `detail` ∈ `low` (512²) | `high` (≤2,500 patches) | `original` | `auto`.
- Formats: PNG, JPEG, WEBP, non-animated GIF. Up to 1,500 images and 512 MB per request.
- Current vision models listed: `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-sol/terra/luna`, `gpt-5.5`, `gpt-5.4`.

### 3.2 Structured outputs

Source: https://developers.openai.com/api/docs/guides/structured-outputs
- Use `text={"format":{"type":"json_schema","name":...,"schema":...,"strict":True}}`, or `client.responses.parse(text_format=PydanticModel)`.
- Strict mode requires `additionalProperties: false` and **every property listed in `required`**. Use a nullable type for optional fields.

```python
# uv run --with openai python oai_vision.py     (needs OPENAI_API_KEY)
import base64, json
from openai import OpenAI
client = OpenAI()
b64 = base64.b64encode(open("scene.jpg", "rb").read()).decode()

schema = {"type": "object", "additionalProperties": False, "required": ["hazards"],
  "properties": {"hazards": {"type": "array", "items": {"type": "object", "additionalProperties": False,
    "required": ["category", "description", "confidence", "bbox_norm"],
    "properties": {
      "category": {"type": "string", "enum": ["cord", "rug", "clutter", "lighting", "stairs",
                                              "bathroom", "furniture", "pet", "other"]},
      "description": {"type": "string"},
      "confidence": {"type": "number"},
      "bbox_norm": {"type": ["array", "null"], "items": {"type": "number"}}}}}}}

resp = client.responses.create(
    model="gpt-6-luna",                      # cheap tier; gpt-6-sol / gpt-6-astra for the top end
    input=[{"role": "user", "content": [
        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}", "detail": "high"},
        {"type": "input_text", "text": "Identify all fall hazards in this room."}]}],
    text={"format": {"type": "json_schema", "name": "hazards", "schema": schema, "strict": True}},
)
data = json.loads(resp.output_text)
```

### 3.3 Pricing

Source: https://developers.openai.com/api/docs/pricing. Figures are per 1M tokens, input/output, short context.

| Model | Price |
|---|---|
| gpt-6-astra | $10 / $50 |
| gpt-6-sol | $2 / $10 |
| gpt-6-luna | $0.10 / $0.50 |
| gpt-5.6-sol | $4 / $20 |
| gpt-5.6-terra | $2 / $12 |
| gpt-5.6-luna | $0.20 / $1.20 |
| gpt-5.5 | $5 / $30 |
| gpt-5.4 | $2.50 / $15 |
| gpt-5-mini | $0.25 / $2 |
| gpt-5-nano | $0.05 / $0.40 |

Image tokens use patches with a per-model multiplier, reported as "typically 1.2x" [UNVERIFIED exact per-model multiplier].

### 3.4 Video input

**No official native video input in the Responses API** that we could confirm.
- There is an open feature request, [openai-node#1778](https://github.com/openai/openai-node/issues/1778) (March 2026).
- An `{"type":"input_video","video_url":"data:video/mp4;base64,..."}` shape shows up in third-party proxies and OpenRouter (https://github.com/router-for-me/CLIProxyAPI/issues/6037), not in OpenAI docs. [UNVERIFIED]
- **Plan: send sampled frames as multiple `input_image` parts.**
- The `/v1/videos` endpoint (https://developers.openai.com/api/reference/resources/videos/methods/create) is for **generating** video (Sora), not understanding it.

### 3.5 gpt-image editing / inpainting (adding a hazard to a base image)

Source: https://developers.openai.com/api/docs/guides/image-generation
- Current models: `gpt-image-2.5-sunburst` and `gpt-image-2.5-flare`.
- Uses `client.images.edit(model, image, mask, prompt)`.
- **The mask must be a PNG with an alpha channel, the same size and format as the image.** Transparent pixels are the regions to edit. Both files must be under 50 MB.
- Sizes: `1024x1024`, `1536x1024`, `1024x1536`, or custom (multiples of 16, aspect ratio 1:3 to 3:1).
- Quality: `low | medium | high | xhigh | max | auto`.
- Pricing: listed as "$8 per image input / $30 per image output". This is almost certainly **per 1M image tokens**, not per image. [UNVERIFIED unit]

```python
from openai import OpenAI
import base64
client = OpenAI()
r = client.images.edit(
    model="gpt-image-2.5-sunburst",
    image=open("bedroom_clean.png", "rb"),
    mask=open("mask_floor_by_bed.png", "rb"),   # RGBA; transparent = region to repaint
    prompt="Same bedroom, photorealistic. Add a small loose throw rug with a curled corner on the "
           "floor beside the bed. Change nothing else.",
    size="1536x1024", quality="medium")
open("bedroom_rug.png", "wb").write(base64.b64decode(r.data[0].b64_json))
```

**Tip for the benchmark:** the (clean, edited) pair plus the mask gives a free ground-truth bounding box for the added hazard (the mask's bbox). Stability erase-object gives the reverse pair.

---

## 4. Gemini (optional; no key available)

- **Bounding boxes:** Gemini returns `box_2d` as `[ymin, xmin, ymax, xmax]` normalized to 0-1000, plus optional segmentation masks. Examples use `gemini-3.8-flash`. Inline requests are limited to 20 MB; the File API allows up to 3,600 images. [DOC] https://ai.google.dev/gemini-api/docs/image-understanding
- **Video:** native video understanding through the File API or inline (about 1 fps default sampling, per earlier docs). [UNVERIFIED for current models] https://ai.google.dev/gemini-api/docs/video-understanding
- **Relevance:** it has the strongest native grounding, so it would be a useful localization baseline. Skip it unless someone has a key. Claude also returns pixel coordinates (https://platform.claude.com/docs/en/build-with-claude/vision-coordinates). For the others, ask for `bbox_norm` in the schema and score it with IoU or a point-in-mask check.

---

## 5. TypeSafe Jev

### 5.1 Facts

Sources: https://docs.typesafe.ai/api.md, https://docs.typesafe.ai/models.md, https://docs.typesafe.ai/concepts/state.md, https://docs.typesafe.ai/model-jaggedness/jev-1.13.md

- **Endpoint:** `POST https://api.typesafe.ai/v1/systemone` with header `Authorization: Bearer <key>`. `GET /v1/models` lists the available models.
- **Model:** `jev-latest`, which currently resolves to `jev-1.13.0`. `jev-preview` points to the same build. **Pin `jev-1.13.0`** for reproducible benchmark numbers.
- **Input is text only**: "No image, audio, or video input." `state` can be a string, a JSON object, or an array.
- **Context:** 64k tokens per request, and 32k for the state plus the longest question.
- **Price and limits:** $0.042 per 1M input tokens; output is free. Limits are 250k tok/s and 1,200 req/min, and TypeSafe says these are "adjusting dynamically".
- **Question types** (all take `instructions`, which can be a string, object or array):
  - **`noul`**: optional `criteria: {"true": ..., "false": ...}`. Returns `{type, noul: 0..1}`.
  - **`choice`**: `criteria: {option: description | null}`, up to 255 options. Returns `{type, choice, probabilities{}, confidence}`.
  - **`score`**: `criteria: [ordered level descriptions]`, 2-10 levels. Returns `{type, score (expected level), legend, probabilities, confidence}`.
  - The **`score` type is newer than our reference client**, which only uses choice and noul.
- **Response envelope:** `{model, answers: {key: Answer}, usage: {input_tokens, output_tokens}}`.
- **Errors:** 401, 429 and 529. Retry with backoff; the SDK does this for you.
- **SDK:** `uv add typesafe-sdk`, then `from typesafe_sdk import TypeSafeClient, Noul, Choice, Score`. Answers are read via `response.nouls[k].noul`, `.choices[k].choice` and `.scores[k].score`. Source: https://github.com/typesafe-ai/typesafe-sdk-python
- **Known weak spots in jev-1.13:**
  - It reads instructions literally.
  - Counting, math, and date comparison are unreliable, so do those in code.
  - Multi-hop indirection hurts accuracy.
  - Large irrelevant state hurts accuracy.
  - **Design pattern: many atomic questions in one call, combined in code.**

### 5.2 Reference client

`~/jev-synergy-screening/src/jev_client.py`, config in `src/config.py`, questions in `src/synergy_screening.py`.

- **Key loading:** `TYPESAFE_API_KEY` env var, then `~/.config/typesafe/api_key`. Otherwise it raises.
- **`_post(text, questions, api_key, timeout)`:** posts `{"state": text, "model": "jev-latest", "questions": questions}` with `requests`, measures latency in ms, and raises on HTTP ≥ 400.
- **Pattern:** one `choice` (label) plus several atomic `noul` gates, combined in code. `synergy_combine` returns include only when choice == include AND each gating noul ≥ 0.5 (or < 0.5 for a negative gate). NaN nouls are coerced to None or a default.
- **Returned fields:** `choice`, `confidence`, `probabilities`, each noul value, `latency_ms`, `model`, `usage`.

### 5.3 Live check [LIVE]

One request with 3 questions (noul + choice + score) and a 507-token input returned **HTTP 200 in 299 / 198 / 132 ms**, with `model: "jev-1.13.0"`. The answers were sensible (`category=cord` at confidence 1.0; `severity` score 1.86 on a 0-2 scale).

### 5.4 How HomeDojo should use Jev

Jev cannot see pixels. Use it as a **fast, calibrated, deterministic-ish grader** over VLM text:
1. **Match each ground-truth hazard against the model's free-text list** with one noul per GT hazard in a single call: "Does `model_output` identify the hazard described in `gt[i]`?" This gives recall and precision without an LLM judge, at about 200 ms and about $0.00002 per scene.
2. **Normalize free-text hazards to the clinical taxonomy** with a `choice` (up to 255 options, which fits `data/hazard_taxonomy.json` categories).
3. **Severity or clinical-priority agreement** with a `score` over the taxonomy's levels.
4. **Gate uncertain grades** (confidence < 0.6) to human review. This matches the "confidence-gated routing" pattern in the Jev docs.

### 5.5 Minimal Jev call

```python
# uv run --with requests python jev_grade.py
import os, pathlib, requests
key = os.environ.get("TYPESAFE_API_KEY") or (pathlib.Path.home() / ".config/typesafe/api_key").read_text().strip()

gt = ["loose rug with curled edge by bed", "extension cord across hallway"]
state = {"model_output": "I see a power cord crossing the hall floor and a cluttered nightstand.",
         "gt": gt}
questions = {f"found_{i}": {"type": "noul",
                            "instructions": f"Does `model_output` identify the hazard `gt[{i}]`?"}
             for i in range(len(gt))}
questions["top_category"] = {"type": "choice",
    "instructions": "Which category is the first hazard named in `model_output`?",
    "criteria": {"cord": "Cord or cable across a walkway", "rug": "Loose or curled rug or mat",
                 "clutter": "Objects on floor or surfaces", "none": None}}

r = requests.post("https://api.typesafe.ai/v1/systemone",
                  headers={"Authorization": f"Bearer {key}"},
                  json={"state": state, "model": "jev-1.13.0", "questions": questions}, timeout=30)
r.raise_for_status()
a = r.json()["answers"]
recall = sum(a[f"found_{i}"]["noul"] >= 0.5 for i in range(len(gt))) / len(gt)
print(recall, a["top_category"]["choice"], a["top_category"]["confidence"])
```

---

## 6. Hackathon: "Healthcare AI Hackathon" (https://luma.com/e9z9vuxz)

Source: the Luma page, fetched raw on 2026-09-26 (event JSON and description text).

- **When:** **Sat 2026-09-26, 10:00-17:00 PT** (event JSON gives `start_at 2026-09-26T17:00Z`, `end_at 2026-09-27T00:00Z`, America/Los_Angeles). One-day event.
- **Where:** AWS Builder Loft, 525 Market St, Floor 2, San Francisco.
- **Registration:** both the Luma registration **and** the AWS Builder Loft registration are required (https://events.builder.aws.com/rE8DY0). Attendees must be 18+ with a **physical** government photo ID. The event is full, with a waitlist.
- **Presented by:** Pear VC, NEA, Cathay Innovation.
- **Powered by (sponsors):** **OpenAI, AWS, J.P. Morgan, Troutman Pepper**.
- **Hosts:** Andrew A Parambath, Elijah Yi, Hui Cheng, Shruti Merchant, Laura Wright, Stephen T, Seong Kim, Manasa Gummalla, Arcangeli Victoria.
- **Tracks** (described as "examples, not constraints"):
  1. **Care Delivery & Clinical Innovation**: "Build AI that makes care more accessible, personalized, and effective, from diagnostics and specialty care to **home-based care**, clinical trials, robotics, and entirely new models of care delivery." HomeDojo fits here.
  2. **Healthcare Infrastructure & Financing**: financing, administration, coordination across providers, payers, employers, marketplaces, supply chains.
  3. **AI × Life Sciences**: predicting real biological outcomes (toxicity, delivery, efficacy, trial endpoints).
- **Prizes:** "up to $5,000 in first/second/third place cash prizes", plus advisory meetings with healthcare AI operators and sponsors, and **1:1 pitch opportunities with PearX, NEA, and Cathay**.
- **Stated build guidance** (the closest thing to criteria on the page): "Build something that meaningfully improves health. We're **less interested in incremental AI wrappers** and more interested in products that **unlock new capabilities, create new business models, or solve long-standing problems**." Projects are demoed "to an audience of industry leaders".
- **Not published on the page:** formal judging criteria or weights, team-size limits, submission format or deadline, and **rules on prior work / pre-existing code**. Ask the organizers at kickoff. Meanwhile, keep the repo history honest: the `homedojo` repo was created today (2026-09-26 10:56 PT). HomeReady is prior work and should be disclosed as "customer zero", not as part of the build.
- **Pitch angle:** the sponsors are OpenAI and AWS, so show both GPT and Bedrock models on the leaderboard, and use Bedrock Stability / gpt-image for the scene edits.

---

## 7. Open actions

1. **Unblock Claude on Bedrock:** submit the Anthropic use-case form in the Bedrock console for the `pistachio` account. The CLI equivalent is `aws bedrock put-use-case-for-model-access`, but a human should fill in the business details. Or route Claude through `ANTHROPIC_API_KEY` directly.
2. **Get the OpenAI sponsor key** into `homedojo/.env` (`OPENAI_API_KEY`). Deliver it through a file, not chat.
3. Refresh the `default` AWS profile (`aws login`) only if needed. `pistachio` works.
4. Ask the organizers for the judging criteria, the prior-work rule, and the submission deadline.
