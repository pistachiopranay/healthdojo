---
title: "HomeDojo competitive landscape (quick scan)"
tags: [homedojo, competitive, research]
status: active
created: 2026-09-26
---

Scan of ~15 minutes, 2026-09-26. Directional, not exhaustive.

**Bottom line:** no one owns clinical eval for home-health AI. Adjacent pieces exist.

## Closest threats
- **Lightwheel + World Labs:** Marble-generated worlds for robot evaluation. Same loop, different domain. https://www.worldlabs.ai/case-studies/2-lightwheel
- **World Labs robotics:** https://www.worldlabs.ai/case-studies/1-robotics. Reported SceniX acquisition (single secondary source, unverified): https://cryptobriefing.com/world-labs-scenix-acquisition-robot-training/
- **NVIDIA Isaac Sim + Marble:** text to sim-ready worlds. https://developer.nvidia.com/blog/simulate-robotic-environments-faster-with-nvidia-isaac-sim-and-world-labs-marble/

## Academic prior art
- **TSHA** (2026): VLM safety-hazard assessment benchmark, mixes AIGC and real images. General safety, not clinical fall risk. https://arxiv.org/html/2603.29759v3
- **OmniFall:** fall-event detection with a synthetic split. Covers the event, not the environment. https://arxiv.org/html/2505.19889v3
- **Synthetic household generation** (persona-driven, robotics): https://arxiv.org/pdf/2602.07243
- **Review: "Are we missing the environmental factors in AI-based fall risk models?"** Our gap, stated in the literature. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12889826/

## Adjacent (likely customers)
- Fall detection: SafelyYou, KamiCare (https://kamivision.com/en-us/fall-detection), AltumView
- Fall-risk scoring: VirtuSense (https://www.virtusense.ai/products/vstbalance), which covers gait, not environment
- Home-hazard apps: FallCheck (academic checklist app)
- Generic health-AI eval: HealthBench, Centific, Microsoft Healthcare AI Model Evaluator. None covers the home.

## Positioning
1. Don't pitch "we generate homes." Pitch **clinically grounded labels** (OT instruments, post-op mobility limits).
2. We are the environment layer that fall-risk AI is missing (cite the review).
3. Lightwheel shows the model works in robotics. Health has nothing like it.
