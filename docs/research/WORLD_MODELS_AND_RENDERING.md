---
title: "World Models and Rendering Options for HomeDojo Scene Generation"
tags: [homedojo, world-labs, marble, procthor, ai2-thor, infinigen, hssd, image-editing, synthetic-data, hackathon]
status: active
created: 2026-09-26
---

# World Models and Rendering Options for HomeDojo

The question: how do we produce about 40 home scenes with **seeded fall hazards whose labels we can trust**, render them, and score vision models on them, all inside a 5-hour hackathon?

Researched 2026-09-26. Each claim links to its source. **[UNVERIFIED]** marks a claim that comes only from a third-party source, or one we inferred and did not test.

---

## TL;DR recommendation

**Fastest path to trustworthy labels in 5 hours: use image editing to insert hazards into base room images. Each edit is a controlled intervention, and the label is what we asked the model to add, confirmed by a verifier.** Use Marble for a few showcase walkthroughs only. It is not the labeling pipeline.

1. Build the "clean" set: generate or collect about 10–15 base room images (bathroom, bedroom, hallway, stairs, kitchen, living room). Each one gets a **scene-graph JSON written by us** (room type, the hazards we intend). Use one text-to-image model.
2. Inject the hazards: for each base image, run 2–4 edits. Each edit adds exactly one hazard from a fixed taxonomy (loose throw rug, cord across walkway, clutter on stairs, no grab bar, poor lighting, wet floor, low furniture in path, pet bowl in walkway...). Where the API supports it, use a mask for the region. That gives about 40 labeled images, plus clean negatives.
3. Verify the labels: (a) run a pixel diff between base and edited image, which gives a changed-region bbox and checks for spillover; (b) have a **different** VLM confirm the hazard is present; (c) have a human eyeball each one (40 images takes about 10 minutes). Drop any image that fails.
4. Scoring: the ground truth is `{hazard_type, bbox from diff}` per image. Score models on detection, localization (IoU against the diff bbox) and false positives on clean images.

Why this works: the pair (base, edited) is a counterfactual, so the model under test must find the delta, and the diff gives us localization for free. Masks are only guidance for GPT Image (see §3), so step 3 is mandatory.

**If the team has a Linux+GPU box, or is willing to use AI2-THOR on macOS:** ProcTHOR/AI2-THOR is the only route where the scene graph is *literally* the ground truth, with per-object metadata and instance segmentation. The catch is that its asset library is weak on fall-hazard objects (no rugs or cords in the documented type list, see §2.1), and it looks visibly synthetic. It works as a stretch "sim track".

---

## 1. World Labs Marble

### 1.1 Is there a public API? Yes.
- The "World API" was announced on 2026-01-21. It generates navigable 3D worlds from text, images, panoramas, multi-view inputs and video, and runs asynchronously. https://www.worldlabs.ai/blog/announcing-the-world-api
- Docs index: https://docs.worldlabs.ai/llms.txt
- Python client: https://github.com/worldlabsai/worldlabs-api-python. Node and Python examples: https://github.com/worldlabsai/worldlabs-api-examples (listed at https://docs.worldlabs.ai/api/examples.md)

### 1.2 Endpoints and auth
Base URL `https://api.worldlabs.ai`. Auth header: `WLT-Api-Key: <key>`. https://docs.worldlabs.ai/api/reference/worlds/generate.md

| Endpoint | Purpose | Source |
|---|---|---|
| `POST /marble/v1/worlds:generate` | Start a world generation. Returns an Operation | https://docs.worldlabs.ai/api/reference/worlds/generate.md |
| `GET` operation (poll `done`) | Long-running op status | https://docs.worldlabs.ai/api/reference/operations/get.md |
| Get / List / Delete world | World object with assets | https://docs.worldlabs.ai/api/reference/worlds/get.md |
| `POST /marble/v1/worlds/{id}:export` | PLY splats (sync, cached) or HQ GLB mesh (async) | https://docs.worldlabs.ai/api/reference/worlds/export.md |
| `POST /marble/v1/pano:depth_to_rgb` | 360° depth pano (EXR/PNG, 2:1) + text, returning an RGB pano | https://docs.worldlabs.ai/api/reference/pano/depth_to_rgb.md |
| Media assets prepare-upload / get | Upload inputs | https://docs.worldlabs.ai/api/reference/media-assets/prepare-upload.md |
| Get credits | Balance | https://docs.worldlabs.ai/api/reference/credits/get.md |

Request fields: `world_prompt` (required, discriminated by `type`), `model` (`marble-1.0-draft`, `marble-1.0`, `marble-1.1`, `marble-1.1-plus`), `seed` (uint32), `display_name`, `tags`, `permission`. https://docs.worldlabs.ai/api/reference/worlds/generate.md. The default model is currently `marble-1.0` and will change to `marble-1.1` later. https://docs.worldlabs.ai/api/models.md

### 1.3 Inputs
From https://docs.worldlabs.ai/api/reference/worlds/generate.md:
- **Text**: `{type:"text", text_prompt, disable_recaption}`
- **Single image**: `{type:"image", image_prompt, text_prompt, is_pano: auto|true|false}`. A panorama input skips the pano stage.
- **Multi-image**: `{type:"multi-image", multi_image_prompt:[{azimuth, content}], reconstruct_images}`. Maximum 4 images, or 8 with reconstruction.
- **Video**: `{type:"video", video_prompt}`. The size limit is 100 MB (raised 2026-01-29, https://docs.worldlabs.ai/marble/release-notes.md).
- Content sources for these inputs: `uri`, `media_asset`, or `data_base64`.
- **3D layout / Chisel**: available **in the web app only**. You block out walls, place a pano camera, and upload GLB/FBX reference geometry. https://docs.worldlabs.ai/marble/create/chisel-tools/chisel-basics.md. **The generate schema has no Chisel or layout input.** The closest API equivalent is `pano:depth_to_rgb`: render a depth pano from our own layout and texture it with a prompt. This is our inference and is **[UNVERIFIED for this use]**.
- **Editing** (pano edit with text plus reference images, "Create & edit", expand, variations) is documented for the app only. The API reference lists no edit endpoint. https://docs.worldlabs.ai/marble/edit/index.md, https://docs.worldlabs.ai/marble/create/prompt-guides/create-and-edit.md

### 1.4 Outputs
World object `assets` (https://docs.worldlabs.ai/api/reference/worlds/get.md):
- `splats.spz_urls`: Gaussian splats in SPZ format, about 2M splats, plus a low-res variant of about 500k (https://docs.worldlabs.ai/marble/export/specs.md)
- `splats.semantics_metadata`: `metric_scale_factor` and `ground_plane_offset`, which convert the world to metric scale
- `mesh.collider_mesh_url`: GLB with 100–200k triangles. `full_res_mesh_url` is vertex-colored. `hq_mesh_url` is textured (600k-tri textured or 1M-tri vertex-colored). HQ mesh generation takes up to 1 hour and is limited to 4 requests per hour per user (https://docs.worldlabs.ai/marble/export/specs.md)
- `imagery.pano_url`: equirectangular PNG at 2560×1280
- `thumbnail_url`, `caption`
- PLY export via `:export` at full_res, 500k, 150k or 100k (https://docs.worldlabs.ai/api/reference/worlds/export.md)
- **Depth**: no depth map asset is documented. You can derive depth by rendering the mesh or splats yourself (our inference).
- **Video**: the "Record" camera-path MP4 is an app feature, with no documented API. https://docs.worldlabs.ai/marble/create/studio-tools/record.md
- Coordinates: OpenCV by default (+x left, +y down, +z forward). For OpenGL, negate Y and Z. https://docs.worldlabs.ai/marble/export/specs.md. Apply the metric scale when rendering outside Marble. https://docs.worldlabs.ai/api/rendering-spz.md

### 1.5 Can we render camera views programmatically? Yes, but we have to render them ourselves.
- `worldlabs-api-python` loads SPZ and renders videos with **gsplat**. `examples/render_video.py <world_id>` renders a turntable. It **needs a CUDA GPU**. https://github.com/worldlabsai/worldlabs-api-python
- **SparkJS** is a THREE.js Gaussian splat renderer (SPZ/PLY/etc.) for browser rendering. You could screenshot it headlessly with Playwright (our inference, **[UNVERIFIED]** on speed and quality). https://sparkjs.dev/ (linked from https://docs.worldlabs.ai/api/examples.md)
- The collider mesh (GLB) can be rendered in any engine, e.g. Blender/pyrender, for depth maps (inference).

### 1.6 How controllable is object placement? Poorly, for our purposes.
- Through the API, placement comes only from the prompt and the input images. There are no object IDs, no per-object semantics, and no instance segmentation in the outputs. The only semantics are scale and ground plane (https://docs.worldlabs.ai/api/reference/worlds/get.md).
- The generated world may **hallucinate or omit** a hazard that the prompt asked for. **That means the prompt is not a trustworthy label.** Each world would need human verification, and a splat gives no per-object ground truth to check against.
- A partial workaround is image-conditioned generation: produce a hazard-edited image (§3) and pass it as `type:"image"`. The hazard is then likely to appear in the front view, but fidelity outside that view is not guaranteed (**[UNVERIFIED]**).

### 1.7 Pricing, limits and timing
- API: $1 = 1,250 credits, $5 minimum, and credits never expire. Costs: Marble 1.0/1.1 world = 1,500 credits; draft = 150; 1.1 Plus = 1,500 + 0–1,500 variable (observed mean $1.714). Pano surcharges: text or non-pano image +80, multi-image or video +100, pano image 0. HQ mesh export = 3,500 credits ($2.80). PLY export is free. https://docs.worldlabs.ai/api/pricing.md
  - A text world therefore costs 1,580 credits, about **$1.26**. A draft costs about **$0.18**. 40 worlds cost about $50 (standard) or about $7 (draft).
- Rate limits: the default is **about 3 starts/min and 60/hour**. Approved accounts get about 30/min on standard models and about 90/min on draft. The limits apply to starts, not to concurrency. https://docs.worldlabs.ai/api/rate-limits.md
- **Generation time: "usually takes about 5 minutes"** per world. https://docs.worldlabs.ai/api/rate-limits.md. At 3/min you can start 40 in about 14 minutes, so all 40 finish in roughly 20 minutes if they run in parallel. Parallel execution is not explicitly guaranteed.
- API credits are separate from Marble app subscriptions. https://docs.worldlabs.ai/api/pricing.md
- App tiers: Free (4 generations), Standard (12), Pro (25, commercial rights, textured mesh export), Max (75), plus Enterprise. https://docs.worldlabs.ai/marble/support/account-billing.md. Prices of $20/$35/$95 per month come from third-party sources **[UNVERIFIED]**: https://www.therundown.ai/tools/marble and https://radiancefields.com/world-labs-formally-launches-marble-a-generative-world-model (the official https://marble.worldlabs.ai/pricing did not render for us).
- Models: 1.1 and 1.1 Plus were released 2026-04-02 (https://docs.worldlabs.ai/marble/release-notes.md). Draft is the fastest option. 1.1 Plus makes the biggest worlds. https://docs.worldlabs.ai/marble/models.md

**Verdict for HomeDojo:** Marble makes an excellent demo ("walk through a hazardous home"), but it is a poor ground-truth source. It has no per-object labels, placement is stochastic, Chisel is app-only, rendering needs a GPU (gsplat) or a browser, and it takes about 5 minutes per world. Use it for 2–3 showcase scenes, seeded from already-verified edited images.

---

## 2. Alternatives with exact ground truth

### 2.1 ProcTHOR / AI2-THOR
- `pip install ai2thor`. Supports macOS 10.9+ and Ubuntu, with Docker/Colab options. Unity backend. https://github.com/allenai/ai2thor
- ProcTHOR: `pip install procthor`. Generates interactive houses procedurally. NeurIPS 2022 Outstanding Paper. Apache-2.0. https://github.com/allenai/procthor. There is a 10k-house dataset: https://github.com/allenai/procthor-10k
- Observations: RGB, depth, and instance segmentation (`renderInstanceSegmentation`), plus per-object metadata (position, state, visibility). https://github.com/allenai/ai2thor/blob/main/ai2thor/controller.py, https://www.emergentmind.com/topics/ai2-thor-platform
- Placement: `SetObjectPoses` puts objects at exact positions and rotations. https://ai2thor.allenai.org/ithor/documentation/objects/set-object-states/
- **The gap:** the documented object types include Chair, Stool, DogBed, FloorLamp and Box, but **no rugs, cords, mats, stairs or grab bars**. https://ai2thor.allenai.org/ithor/documentation/objects/object-types/. Many clinical hazards (loose rug, cord, wet floor, missing grab bar, dim lighting on stairs) cannot be represented without custom assets. The renders also look clearly synthetic, which is a domain gap for evaluating VLMs.
- Setup risk: the Unity binary download, and Linux needs an X server with GLX (https://github.com/allenai/ai2thor). **[UNVERIFIED]**: stability on Apple Silicon.

### 2.2 Infinigen Indoors
- A procedural, photorealistic indoor generator built on Blender. It has a constraint DSL plus a solver for arranging objects. BSD license. CVPR 2024. https://arxiv.org/abs/2406.11824
- Ships ground-truth annotation tooling (see `docs/GroundTruthAnnotations.md` in https://github.com/princeton-vl/infinigen).
- It is heavy. One downstream dataset reported about a week on 8 RTX6000 GPUs for its scene set (IDEAL-Bench, https://arxiv.org/pdf/2607.03614). **[UNVERIFIED]**: the per-scene time. Our expectation is tens of minutes or more per room. **Not viable in 5 hours.**

### 2.3 Habitat / HSSD-200
- 211 human-authored houses, 18,656 objects, 466 semantic categories (WordNet). Realistic layouts recreated from real homes. https://arxiv.org/abs/2306.11290, https://3dlg-hcvc.github.io/hssd/. Hugging Face: https://huggingface.co/datasets/hssd/hssd-hab
- Semantic ground truth is exact, and the scenes are high quality. But inserting hazards means scripting object placement in habitat-sim, and habitat-sim setup (conda, Linux-oriented) is a hackathon risk (**[UNVERIFIED]** on macOS). It suits a v2 "sim track" better than day one.

---

## 3. The image generation and editing route

| Model | Notes | Price | Source |
|---|---|---|---|
| OpenAI `gpt-image-2.5-sunburst` / `gpt-image-2.5-flare` | Both support edits with masks. Sunburst is the "editing precision" model. **"Masking with GPT Image is entirely prompt-based. The model uses the mask as guidance, but may not follow its exact shape with complete precision."** | Token-based. About $0.05 (medium) to $0.21 (high) per 1024² **[UNVERIFIED, third-party]** | https://developers.openai.com/api/docs/guides/image-generation ; https://www.eesel.ai/blog/chatgpt-images-2-5-pricing |
| Google `gemini-3.1-flash-image` (Nano Banana 2) | Text-plus-image editing | $0.067/1K image, $0.034 batch | https://ai.google.dev/gemini-api/docs/pricing |
| Google `gemini-3-pro-image` (Nano Banana Pro) | Higher quality | $0.134/1K–2K image | https://ai.google.dev/gemini-api/docs/pricing |
| Google `gemini-3.1-flash-lite-image` | Cheapest | $0.0336/1K | https://ai.google.dev/gemini-api/docs/pricing |
| ByteDance Seedream 4.5 | Editing, up to 10 reference images, 4K | About $0.04/image on BytePlus **[UNVERIFIED, third-party]** | https://evolink.ai/blog/seedream-pricing-guide-2026 ; https://www.therundown.ai/tools/seedream-4-5 |

Also, the `treg` MCP in this workspace exposes Gemini Image, GPT Image and Seedream, so we may not need to provision separate keys (workspace MCP instructions; check the balance first).

**Why editing gives controllable labels:**
- The label is the intervention: "add a loose throw rug with a curled corner at the bathroom doorway." We know the intended class before we see any pixels.
- The base/edited pair allows a **pixel diff**. It yields a bbox or mask of what changed, which becomes the localization ground truth and also detects edits that spilled outside the mask. (This matters because GPT Image masks are only guidance, per the quote above.)
- Clean base images act as matched negatives, which lets us measure the false-positive rate.
- Failure modes: the edit is too subtle or missing, a second hazard gets introduced, or global changes appear (lighting or color shift across the whole image). All three show up in the diff area plus a VLM or human check. **[UNVERIFIED]**: what reject rate to expect. Budget 1.5–2× generations, i.e. 60–80 edits for 40 accepted.

Cost for about 80 edits plus 15 base images at about $0.07: **about $7.** Latency is seconds per image **[UNVERIFIED]**, so this fits easily in 5 hours.

---

## 4. Comparison for a 5-hour build

| Route | Label trust | Realism | Hazard coverage | Setup risk | Time for 40 scenes | Cost |
|---|---|---|---|---|---|---|
| **Image edit (base + inserted hazard + diff + verify)** | High, after verification | High | Any hazard we can describe | Low (HTTP APIs) | about 1–1.5 h | about $5–15 |
| Pure text-to-image with hazards in the prompt | Low (model may omit or add hazards) | High | Any | Low | under 1 h | about $3 |
| Marble world (text or image to splat) | Low (no per-object GT) | Medium–High, 3D | Any (stochastic) | Medium (GPU for gsplat, or browser) | about 20–30 min gen + render work | about $7 (draft) to $50 |
| ProcTHOR / AI2-THOR | Exact | Low (synthetic) | Limited (no rugs or cords) | Medium | about 2–3 h | $0 |
| HSSD / Habitat | Exact | Medium | Needs custom asset insertion | High | Too long | $0 |
| Infinigen Indoors | Exact | High | Via constraints | High, compute-heavy | Not feasible | GPU hours |

**Recommended plan:** use image editing with diff verification as the core benchmark (40 scenes). Add 2–3 Marble worlds, seeded from verified edited images, as the demo walkthrough. Mention ProcTHOR/HSSD in the pitch as the "v2 exact-GT 3D track".

## Open questions / unverified
- Official Marble app dollar prices (the pricing page did not render).
- Whether Marble's API will ever expose Chisel or edit endpoints. Neither is present in the reference as of 2026-09-26: https://docs.worldlabs.ai/llms.txt
- Real reject rate of hazard-insertion edits for each model. Needs a 10-image pilot in the first 30 minutes.
- Per-scene runtime for Infinigen Indoors, and AI2-THOR on Apple Silicon.
