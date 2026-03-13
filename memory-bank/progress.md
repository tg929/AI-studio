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
- Implemented the `asset_prompts.json` generation node.
- Added explicit Pydantic validation for `asset_prompts.json`.
- Ran the first real asset-prompt generation successfully and saved it under the existing run directory.
- Implemented the `asset_images_manifest.json` generation node.
- Added real image-model generation for character, scene, and prop asset images.
- Switched final asset-card labels from model-rendered text to local deterministic overlay rendering.
- Ran the asset-image stage successfully and saved raw images, labeled final images, raw responses, and manifest files.
- Refined asset-image prompts toward reference-sheet layouts inspired by `BigBanana-AI-Director-main-2`.
- Updated character asset images toward `close-up + turnaround views`, scene asset images toward `master shot + support views`, and prop asset images toward `hero view + structural views`.
- Replaced raw image download from `httpx` with `curl` after repeated signed-URL TLS EOF failures during image retrieval.
- Aligned the asset-stage aspect-ratio strategy with `BigBanana-AI-Director-main-2`: one shared project-level image ratio, currently using the reference project's default `16:9`.
- Tightened the asset prompt strategy around explicit three-view boards:
  - characters: close-up + front / side / back full-body views
  - scenes: master view + three same-location auxiliary views
  - props: hero view + front / side / back object views
- Reworked prompt wording to suppress template-page artifacts such as `CREATE ONE`, visible headers, sidebars, color bars, page furniture, and readable letters.
- Ran a fresh end-to-end experiment from script input through asset images under `runs/20260312-214058`.
- Stopped injecting the full negative-term list directly into image prompts and switched image prompts to cleaner natural-language prohibitions.
- Tightened scene prompts around explicit empty-environment requirements and prop prompts around strict object-only view consistency.
- Ran another fresh end-to-end experiment from script input through asset images under `runs/20260312-220137`.
- Switched new run-directory creation from timestamp names to sequential `runs/runN` naming.
- Re-ran the full implemented pipeline after confirming `watermark=False` is applied in the image API call; the latest full run is `runs/run1`.

## Current Phase

Early workflow implementation.

The project now has:

- workflow schema design
- asset extraction prompt design
- one working Python extraction node
- one working Python style-bible node
- one working Python asset-prompts node
- one working Python asset-images node
- project memory-bank setup

## Next Step

- Generate `storyboard.json`
- Then build one stitched reference board per shot

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
- The asset-prompts node uses the same prompt-constrained JSON + local schema validation path.
- The asset-image node uses the image model for clean subject generation and local overlay rendering for stable labels.
- The current asset-image prompt strategy now explicitly targets reference boards instead of ordinary single illustrations.
- The latest fresh run improved upstream asset prompt cleanliness, but raw image results still show template contamination in some cases:
  - character sheets may still contain stray edge text or UI-like marks
  - scene sheets may still hallucinate people and page headers
  - prop sheets may collapse into the wrong subject or pull in character-like silhouettes
- The newest run `20260312-220137` further reduced some prompt-leak artifacts, but key image-generation failures remain:
  - character images can still hallucinate embedded Chinese glyphs and QR-like marks
  - scene images still tend to add people despite explicit empty-scene wording
  - prop images can still drift into the wrong object class or mix object views with humanoid silhouettes
