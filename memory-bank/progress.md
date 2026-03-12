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
- Implemented the first Python workflow node for script preprocessing and asset extraction.
- Added explicit Pydantic validation for `asset_registry.json`.
- Ran the first real extraction against `01-陨落的天才.txt` successfully.
- Implemented the `style_bible.json` generation node.
- Added explicit Pydantic validation for `style_bible.json`.
- Ran the first real style-bible generation successfully and saved it under the existing run directory.

## Current Phase

Early workflow implementation.

The project now has:

- workflow schema design
- asset extraction prompt design
- one working Python extraction node
- one working Python style-bible node
- project memory-bank setup

## Next Step

- Implement asset image prompt generation
- Then generate labeled asset images

## Known Constraints

- Python only for implementation
- AgentKit / VeADK is the target runtime
- Asset images are labeled
- One stitched board image per shot is sent to the video model
- Each shot is 10 seconds

## Notes

- `agentkit.local.yaml` contains local model settings and must remain uncommitted.
- `BigBanana-AI-Director-main-2/` is gitignored here and used only as a local reference copy.
- The current text model does not support `response_format={"type":"json_object"}`.
- The asset extraction node currently uses prompt-constrained JSON output plus local schema validation.
- The style-bible node uses the same prompt-constrained JSON + local schema validation path.
