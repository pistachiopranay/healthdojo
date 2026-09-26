# HomeDojo

Eval and training environment for home-health multimodal AI. We generate synthetic homes with seeded, clinically grounded fall hazards (the scene graph is the ground truth), render them, and score vision models on finding the hazards. Output: **HomeBench**, a leaderboard, failure analysis, and hard-example training packs.

Origin: built for HomeReady (post-op home readiness). HomeReady is customer zero.

## Layout
- `docs/research/`: landscape, world models/rendering, clinical taxonomy, model APIs + hackathon
- `docs/spec/`: product spec + stack (source of truth before build)
- `data/`: hazard taxonomy, scene graphs, rendered scenes, model outputs
- `src/`: generator, runner, grader, leaderboard UI

Built at the Pear hackathon, 2026-09-26.
