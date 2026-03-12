# Progress

Last updated: 2026-03-12

## Completed

- Initialized the local Python AgentKit project.
- Prepared `.venv` and installed required Python packages.
- Added a simple AgentKit app entry in `simple_agent.py`.
- Added standalone smoke tests for text, image, and video model calls.
- Verified smoke tests successfully for all three model types.
- Initialized git and connected the GitHub remote repository.
- Reviewed Volcano Engine AgentKit quickstart and VeADK docs.
- Analyzed `BigBanana-AI-Director-main-2` for prompt/workflow references.
- Added local project memory files inspired by `vibe-coding`.
- Finalized the V1 `asset_registry.json` schema draft.
- Drafted the project-specific asset extraction system prompt.

## Current Phase

Design and planning.

The project is not yet in production workflow implementation. The current focus is:

- workflow schema design
- system prompt design
- memory-bank setup

## Next Step

- Validate the asset schema against `01-陨落的天才.txt`
- Refine the asset extraction prompt after the first extraction run
- Then implement the first Python workflow node

## Known Constraints

- Python only for implementation
- AgentKit / VeADK is the target runtime
- Asset images are labeled
- One stitched board image per shot is sent to the video model
- Each shot is 10 seconds

## Notes

- `agentkit.local.yaml` contains local model settings and must remain uncommitted.
- `BigBanana-AI-Director-main-2/` is gitignored here and used only as a local reference copy.
