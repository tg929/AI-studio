# Project Brief

## Summary

This project builds a script-to-video workflow using Volcano Engine models through a Python AgentKit application.

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
- Volcano Engine text, image, and video models
- The current short-intent expansion target is a roughly `60s`, `6-shot` micro-script before it enters the existing downstream flow
- The upstream router should choose the minimum necessary path among `expand|compress|rewrite|direct_extract|confirm`
- Shot duration fixed at 10 seconds
- Asset images must include labels
- Video model gets one stitched board image plus one shot prompt
- Asset extraction should only run after an explicit readiness check on the current script candidate
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

- Advanced UI
- Fine-grained human review tooling
- Automatic dubbing/music/subtitles
- Multi-project orchestration
