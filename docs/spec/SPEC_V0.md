---
title: "HomeDojo v0 spec (hackathon, 4 hours)"
tags: [homedojo, spec]
status: active
created: 2026-09-26
---

# HomeDojo v0: 4-hour hackathon spec

**One line:** HomeBench is the first clinically grounded benchmark for whether AI models can see what makes a home unsafe for a patient going home after surgery.

## Demo story (3 min)
1. **Problem:** about 1 in 3 joint-replacement patients fall within a year, most of them at home. Home-health AI is shipping vision models into homes, and nobody can test them because real ground truth doesn't exist.
2. **Dojo:** we generate homes with *known* hazards. The label comes first, then we render the scene, so every image has exact ground truth.
3. **Leaderboard:** Claude, Nova, Llama (Bedrock) and GPT, scored on 40 scenes.
4. **Money slide:** the failure finding, e.g. every model misses *absent* hazards (no grab bar) and *measurement* hazards (walker won't fit through the doorway).
5. **Dojo loop:** the failures get exported as a hard-example training pack. "Bring your model" means a submission form for a model URL.
6. **Origin and ask:** "We built this because HomeReady needed it."

## Scope (IN)
- **Scene generation.** 40 scenes: 6 rooms × hazard mixes, plus 6 clean negatives. Method: generate a clean base room image, then *edit* it to insert 1 to 3 hazards from the taxonomy. Absent-type hazards (no grab bar) come from generation prompts instead. Each scene is `scene.json` = {room, hazards:[{id, severity}], prompt, image}.
- **Label verification.** One VLM pass checks that each seeded hazard is visible. Scenes that fail get dropped or fixed. We report how many were dropped: that's an honest number to show.
- **Runner.** The same prompt goes to every model: the image plus the list of 35 taxonomy ids and names, and the model returns JSON `[{id, severity, evidence}]`. Models:
  - Bedrock Converse: Claude, Nova Pro, Llama vision
  - OpenAI: GPT
- **Grader.** Match on id → TP/FP/FN. Metrics: recall, precision, F1 overall, by room, and by hazard *type* (visible object / absent feature / measurement). Severity-weighted recall uses post-op escalation. Jev is optional, used only to map free-text answers from models that don't return clean ids.
- **UI.** A single static page: leaderboard, a heatmap of hazard type × model, and a scene browser (image, ground truth, each model's answer with hits and misses marked).
- **Hosting.** S3 static site (AWS points).

## Scope (OUT today)
Marble 3D worlds and video walkthroughs (roadmap slide only), real training, auth, a real submission API.

## Stack
- Python 3 scripts in `src/`: `gen_scenes.py`, `verify.py`, `run_models.py`, `grade.py`, `build_site.py`
- Images: treg image models (GPT Image / Gemini image / Seedream, editing), or Bedrock Nova Canvas as the fallback
- Eval: boto3 `bedrock-runtime` Converse, plus the OpenAI Responses API with json_schema
- UI: one self-contained HTML file, rendered from `results.json` with vanilla JS. No build step.

## Timeline (T0 = 18:15 UTC; demo about 22:10)
| Slot | Work |
|---|---|
| 0:00–0:20 | Lock spec, keys in, smoke-test every model on 1 image |
| 0:20–1:20 | Generate + verify 40 scenes (runs in background) |
| 0:40–1:40 | Runner + grader over first scenes |
| 1:40–2:40 | Full run, leaderboard/scene browser UI, host on S3 |
| 2:40–3:15 | Failure analysis → money slide, training-pack export |
| 3:15–4:00 | Pitch deck (6 slides) + rehearse; buffer |

## Risks
- The image editor won't insert the hazard reliably → verification pass. Fall back to generating the whole scene from the prompt.
- AWS event credentials expire → refresh them from Workshop Studio.
- Absent and measurement hazards are hard to *render* faithfully → keep a small, hand-checked set (8 to 10 scenes).
