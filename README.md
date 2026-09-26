# HealthDojo — the flight simulator for home-health AI

Home-health AI is moving into patients' homes, and the only way to test it today is on real patients. HealthDojo turns real clinical guidelines into synthetic homes with exact, verified labels, so AI companies can pressure-test their models before a single patient trial.

Built in one day at the Healthcare AI Hackathon (2026-09-26). All data is synthetic; no real patients or patient data.

**Live demo:** http://healthdojo-demo-pear.s3-website-us-east-1.amazonaws.com

## How it works

1. **Guideline → rubric.** A model turns a clinical guideline (e.g. adapted from CDC STEADI "Check for Safety") into hazard rubric rows. Each row quotes its source line, carries severity + a post-op/dementia modifier, cross-walks to validated tools (HOME FAST), and needs clinician approval.
2. **Rubric → synthetic homes, label before pixels.** Generate a clean room, edit in exactly one hazard (or stack several, plus safe look-alike distractors); a pixel diff gives the ground-truth box and a vision judge verifies the edit. Scenes are also turned into walkable 3D worlds (World Labs Marble).
3. **Pressure test.** Photo benchmark (14 vision models, 13 on AWS Bedrock) and **walkthrough mode**: an agent environment where a model is dropped into a 360° home facing away from the hazard and must look/turn/zoom/flag to find it.
4. **Report card.** Recall, false alarms on verified-absent hazards, localization, failure heatmaps by hazard type and room.

Benchmarks: **HomeBench** (post-op fall prevention, CDC STEADI) and **DementiaBench** (Alzheimer's Association / NIA home-safety guidance).

## Layout
- `src/` — generator (`gen_scenes.py`), verifier (`verify.py`), model runner (`run_models.py`), grader (`grade.py`), site builder, live brief flow (`brief_server.py`), walkthrough (`walk.py`, `walk_live_server.py`), Marble worlds (`marble.py`), curriculum engine
- `data/` — hazard taxonomies, scene graphs, model outputs, results, worlds, walk traces
- `docs/research/` — clinical taxonomy research, landscape, sources
- `site/` — static report-card site

## Run
Python 3.12 venv; credentials in `.env` (AWS Bedrock, Anthropic, World Labs). `BENCH=dementia` switches benchmark.
```
cd src && python run_models.py && python grade.py && python build_site.py
```

## Caveats
Rubrics are drafted from published guidelines and pending OT/PT review; ICD-10 mapping is approximate. Sample sizes are small (directional results). Sim-to-real transfer is not yet validated.
