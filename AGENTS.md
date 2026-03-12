# Project Instructions for Codex

Read these files before doing substantial work in this repository:

1. `memory-bank/project-brief.md`
2. `memory-bank/progress.md`
3. `memory-bank/implementation-plan.md`
4. `memory-bank/architecture.md`

If the task is about prompts, workflow design, or model orchestration, also read:

5. `memory-bank/prompt-strategy.md`
6. `memory-bank/open-questions.md`

Project rules:

- This project is implemented in Python, not TypeScript.
- Use AgentKit and VeADK as the main runtime/orchestration layer.
- Use Volcano Engine models for text, image, and video generation.
- Treat `BigBanana-AI-Director-main-2/` as a reference library for prompt design and workflow ideas only.
- Do not copy its TS/React implementation structure as the production implementation for this repo.
- Keep secrets out of git. `agentkit.local.yaml` is local-only and must not be committed.
- The default script input for current development is `01-陨落的天才.txt`.
- Each storyboard shot is fixed at 10 seconds in the current project version.
- Asset images in this project are labeled reference assets.
- For video generation, each shot uses one stitched reference board image plus one shot prompt.
- Keep inter-stage artifacts structured as JSON whenever possible.
- Work step by step. Do not start the next implementation step before the current step is verified.

Documentation rules:

- Update `memory-bank/progress.md` after each meaningful milestone.
- Update `memory-bank/architecture.md` after structural code changes.
- Update `memory-bank/project-brief.md` when high-level project state or locked decisions change.
- Keep docs concise and factual. Remove stale assumptions instead of layering contradictory notes.
