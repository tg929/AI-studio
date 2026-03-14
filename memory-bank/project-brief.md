# Project Brief

## Summary

This project builds a script-to-video workflow using Volcano Engine models through a Python AgentKit application.

The system takes a script as input and produces:

- structured assets
- labeled asset images
- storyboard shot prompts
- stitched per-shot reference boards
- per-shot videos
- one final stitched video

Current baseline:

- `run10` is the first end-to-end completed baseline run from script through final stitched video.
- The current final output is `runs/run10/10_final/final_video.mp4`.

## Default Input

- Script file: `01-陨落的天才.txt`

## Product Flow

1. Script preprocessing
2. Asset extraction
3. Art direction generation
4. Asset visual prompt generation
5. Asset image generation
6. Storyboard generation
7. Shot reference board stitching
8. Shot video generation
9. Final video concatenation

## Core Constraints

- Python implementation
- AgentKit / VeADK workflow
- Volcano Engine text, image, and video models
- Shot duration fixed at 10 seconds
- Asset images must include labels
- Video model gets one stitched board image plus one shot prompt
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
