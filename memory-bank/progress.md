# Progress

Last updated: 2026-03-14

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
- Converted the current prompt stack to English-first wording for:
  - asset extraction
  - style bible
  - asset prompt generation
  - asset image rendering
- Added small explicit output normalizations in `pipeline/asset_extraction.py` for recurring model drift:
  - `identity_markers` string -> list
  - numeric `age` -> string
  - `schema_version: "1.0.0"` -> `"1.0"`
- Confirmed the Volcano image SDK does not expose a dedicated `negative_prompt` parameter in the current client wrapper; the stored `negative_prompt` field is metadata only.
- Disabled image-side `optimize_prompt` in the Volcano image call so the service stops rewriting the handcrafted render prompt.
- Ran multiple fresh prompt experiments under:
  - `runs/run3`
  - `runs/run5`
  - `runs/run8`
  - `runs/run9`
- Added a safety-oriented rule for underage characters: do not emit exact numeric ages in image prompts; use broad descriptors like `young teen` instead.
- Implemented the `storyboard.json` generation node.
- Added explicit Pydantic validation for `storyboard.json`.
- Added cross-file storyboard validation for segment coverage, contiguous shot-to-segment mapping, and asset-reference integrity.
- Ran the storyboard stage successfully for `run10` and saved the artifacts under `runs/run10/06_storyboard`.
- Implemented the stitched shot reference board generation node.
- Added explicit Pydantic validation for `shot_reference_manifest.json`.
- Ran the shot-board stage successfully for `run10` and saved the artifacts under `runs/run10/07_shot_reference_boards`.
- Implemented the `video_jobs.json` assembly node.
- Added explicit Pydantic validation for `video_jobs.json`.
- Ran the video-job assembly stage successfully for `run10` and saved the artifacts under `runs/run10/08_video_jobs`.
- Implemented the stitched shot-board publishing node.
- Verified locally that non-public board URLs remain blocked from video submission and public-looking board URLs turn all jobs `ready`.
- Latest observation from `runs/run9`:
  - character sheets improved noticeably compared with earlier runs
  - character QR/color-strip contamination was reduced but not fully eliminated
  - prop sheets still drift toward mannequin / torso-display interpretations
  - scene sheets still drift toward presentation-board framing and may still include human figures
  - prompt-only tuning is helping most on characters and much less on scenes / props

## Current Phase

Early workflow implementation.

The project now has:

- workflow schema design
- asset extraction prompt design
- one working Python extraction node
- one working Python style-bible node
- one working Python asset-prompts node
- one working Python asset-images node
- one working Python storyboard node
- one working Python shot-reference-board node
- one working Python video-job assembly node
- one working Python shot-board publishing node
- project memory-bank setup

## Next Step

- Publish `run10` stitched shot boards to a real stable public URL base for `first_frame`
- Then start shot-video generation with the generated `video_jobs.json`

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
- Latest state after the English-prompt experiments (`runs/run9`):
  - character images are the closest to target so far
  - scene and prop images remain the weakest part of the current prompt-only approach
- After reviewing `runs/run9`, the preferred target style for character sheets was reset to the earlier `runs/20260312-220137/05_asset_images/characters` look:
  - left side = one large close-up / half-body portrait
  - right side = three clearly readable large full-body views
  - keep the cleaner canvas behavior achieved in later runs
- `run10` is now the active continuation run. It already contains `01_input` through `04_asset_prompts`, and only `05_asset_images` is being iterated in place.
- Latest `run10` image-stage tuning moved `prompts/asset_images.py` back toward the older Chinese composition language and reduced the prompt from a long rule-heavy board description to a shorter “设定组合图” style request:
  - character: return to the older large-portrait + large right-side three-view layout
  - scene: force three fully rendered alternate angles in a right-side vertical column
  - prop: force one inert object only, with three large right-side alternate views and no mannequin / ring / clothing drift
- Current working rule for expensive calls:
  - do local prompt analysis first
  - only rerun the image stage when the expected improvement is concrete
  - keep all stage outputs for the same experiment under one `runs/runN` directory
- Upstream character extraction has now been hardened with new structured fields:
  - `visual_profile`
  - `costume_profile`
  - `visual_identity_lock`
- `extract_assets.py` now supports `--run-dir` so an existing run can be continued in place instead of forcing a new `runN`.
- `run10/02_assets/asset_registry.json` has been regenerated in place using the upgraded extraction prompt and schema.
- Result of the new `run10/02_assets` extraction:
  - female characters are still present and explicitly marked
  - the new character records contain stronger visual anchors for gender, age stage, hair, clothing, and anti-drift rules
  - some underspecified details are still over-inferred by the text model, especially for `char_002` costume colors / hairstyle
- Important run-state note:
  - `run10/03_style`, `run10/04_asset_prompts`, and `run10/05_asset_images` are now derived from the old `run10/02_assets`
  - they should be treated as stale until we decide to rerun downstream stages
- `run10` has now been brought back into sync:
  - regenerated `03_style` from the updated `02_assets`
  - regenerated `04_asset_prompts` from the updated `03_style`
  - regenerated `05_asset_images` from the updated `04_asset_prompts`
- `run10` is again the current baseline run for further prompt tuning and visual inspection.
- `run10` now also includes a validated `06_storyboard/storyboard.json`:
  - 6 shots total
  - complete coverage of `seg_001` through `seg_012`
  - every shot locked to 10 seconds
  - every shot references only existing `scene_*`, `char_*`, and `prop_*` IDs
- `run10` now also includes a validated `07_shot_reference_boards/shot_reference_manifest.json`:
  - 6 stitched boards total
  - one board per shot
  - current layouts used `grid_2x1` and `grid_2x2`
  - `shot_006` is the current example of a 3-asset `grid_2x2` board with one blank cell
- `run10` now also includes a validated `08_video_jobs/video_jobs.json`:
  - 6 video jobs total
  - every prompt is assembled locally from fixed blocks plus asset/style anchors
  - all current jobs are blocked only because `board_public_url` is still empty
- The new board-publishing node is verified locally:
  - `localhost` and other non-public URLs stay blocked in `video_jobs`
  - public-looking `https://...` URLs produce `ready` jobs
  - the remaining gap is a real externally reachable host/path for `run10` board files
- The storyboard stage currently uses the same text-model pattern as earlier JSON stages:
  - prompt-constrained JSON output
  - local field-alias normalization
  - Pydantic schema validation
  - extra cross-file validation against `asset_registry.json`
- The shot-board stage is now local and deterministic:
  - reads `storyboard.json` + `asset_images_manifest.json`
  - always includes the shot's `primary_scene_id`
  - then places visible characters and visible props into a fixed grid template
  - preserves the original labeled asset images without cropping or overlaying new text
- Current locked storyboard/video-prep decisions:
  - the later shot board is the video model `first_frame`
  - `storyboard.json` is a structured shot-planning contract, not the final video prompt
  - later video prompts should be assembled programmatically from storyboard fields plus asset/style anchors
  - `video_jobs.json` is now assembled locally from `storyboard.json + shot_reference_manifest.json + asset_registry.json + style_bible.json`
  - `shot_reference_manifest.json` currently leaves `board_public_url` empty; a publishing/URL step is still required before video submission
