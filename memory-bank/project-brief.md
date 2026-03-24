# Project Brief

## Summary

This project builds a script-to-video workflow using Volcano Engine models through a Python pipeline with AgentKit and VeADK integrations.

The system currently supports two upstream intake families:

- a full script
- a short intent input such as keywords or a brief, which can first be expanded into a full script

The upstream path is now route-guided:

- an intake router decides whether to expand, compress, rewrite, direct-extract, or stop for confirmation
- an asset-readiness gate evaluates the script candidate before asset extraction

From a full script, the system produces:

- structured assets
- labeled asset images
- storyboard shot prompts
- stitched per-shot reference boards
- per-shot videos
- one final stitched video

Current baseline:

- `run10` is the first end-to-end completed baseline run from script through final stitched video.
- The current final output is `runs/run10/10_final/final_video.mp4`.
- Final stitching now supports both leading trim and a short leading black-screen cover on every shot so residual first-frame board frames can be hidden deterministically.
- The interactive direction is now shifting from `veadk web`-first operation to a custom Python operator console.
- A shared workflow service plus persisted run-state layer now sits underneath the CLI and VeADK tools as the foundation for that UI.
- The first local operator-console skeleton now exists with FastAPI endpoints, background task execution, and review-oriented run detail panels.
- The first operator approval gates are now active: downstream execution stops at `upstream`, `asset_images`, and `storyboard` until the stored review state is approved.
- Legacy runs that already contain checkpoint artifacts now auto-bootstrap those checkpoint reviews to `approved` during compatibility sync so old `runN` directories can resume without being misclassified as blocked by newly added gates.
- The project now also has a unified local CLI entrypoint `run_workflow.py` for terminal-based end-to-end execution and resume.
- Upstream intake-router normalization now repairs path / operation-order mismatches before schema validation.
- Storyboard prop coverage now treats character signature props and scene default props as valid carry-over assets.
- Current top visual-quality priority is consistency:
  - all characters in one script should share one coherent project-level style
  - scenes should remain the same place without drifting into crowd plates or diagrams
  - props should stay object-only without human scale references or category drift

## Default Input

- Script file: `01-陨落的天才.txt`

## Product Flow

1. Intake routing
2. Optional intent understanding
3. Optional story blueprint generation
4. Optional script transform generation
5. Asset-readiness gating
6. Script preprocessing
7. Asset extraction
8. Art direction generation
9. Asset visual prompt generation
10. Asset image generation
11. Storyboard generation
12. Shot reference board stitching
13. Shot video generation
14. Final video concatenation

## Core Constraints

- Python implementation
- AgentKit / VeADK workflow
- The next user-facing shell is a custom Python operator console built on a shared orchestration service
- `veadk web` remains a secondary operator/debug shell during the transition
- Volcano Engine text, image, and video models
- The current short-intent expansion target is a roughly `60s`, `6-shot` micro-script before it enters the existing downstream flow
- The upstream router should choose the minimum necessary path among `expand|compress|rewrite|direct_extract|confirm`
- `recommended_operations` must be canonicalized so its first item matches the chosen upstream path
- Shot duration fixed at 10 seconds
- Asset images must include labels
- Video model gets one stitched board image plus one shot prompt
- Asset extraction should only run after an explicit readiness check on the current script candidate
- Storyboard shot props may come from covered segments, listed-character signature props, or covered/primary-scene default props
- Final video stitching trims the leading first-frame display window from each shot before concatenation
- Final video stitching can also force a short leading black-screen cover on each processed shot before concatenation
- JSON as the default inter-stage contract

## V1 Success Criteria

- End-to-end run works on one test script.
- Each stage can be executed and validated independently.
- Asset IDs are stable and consistently reused across stages.
- Shot count, shot duration, and output files are traceable.
- The final output is one playable stitched video.

## Not in V1

- Public-facing polished product UI
- Fine-grained human review tooling beyond the first operator approval checkpoints
- Automatic dubbing/music/subtitles
- Multi-project orchestration
