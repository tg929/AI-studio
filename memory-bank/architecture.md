# Architecture

Last updated: 2026-03-15

## Current Files

### `simple_agent.py`

Current role:

- Basic AgentKit app entrypoint
- Exposes one simple agent
- Mounts text, image, and video-related tools

Future role:

- Likely becomes the workflow entry shell or delegates to workflow modules

### `extract_assets.py`

Current role:

- CLI entrypoint for the first workflow node
- Runs script preprocessing and asset extraction

### `generate_script_from_intent.py`

Current role:

- CLI entrypoint for the new optional upstream intent-to-script node
- Accepts keywords, a brief, or a full script
- Generates `00_source/*` artifacts and writes a normalized `01_input/script_clean.txt`
- Can optionally continue into asset extraction in the same run directory

### `pipeline/runtime.py`

Current role:

- Loads local text-model runtime config from `agentkit.local.yaml`
- Builds the Ark client for workflow nodes
- Loads local image-model runtime config from `agentkit.local.yaml`
- Loads local video-model runtime config from `agentkit.local.yaml`

### `pipeline/io.py`

Current role:

- Shared JSON and model-response helpers for workflow nodes
- Centralizes `write_json`, `read_json`, response dumping, and text-content extraction

### `pipeline/asset_extraction.py`

Current role:

- Normalizes script text
- Writes input artifacts
- Supports both file-based script input and direct in-memory script text input
- Calls the text model
- Normalizes observed model field aliases
- Validates the result against the asset schema
- Writes `asset_registry.json`

### `pipeline/intent_to_script.py`

Current role:

- Builds the new `00_source/` upstream stage
- Writes `source_input.txt` and `source_context.json`
- Generates `intent_packet.json`
- Generates `story_blueprint.json`
- Generates `generated_script.txt`
- Generates `script_quality_report.json`
- Writes the generated script into `01_input/script_clean.txt` for downstream reuse

### `generate_style_bible.py`

Current role:

- CLI entrypoint for the style-bible node
- Reads a validated `asset_registry.json`
- Generates `style_bible.json` into the same run directory

### `generate_asset_prompts.py`

Current role:

- CLI entrypoint for the asset-prompt node
- Reads a validated `style_bible.json`
- Resolves the matching `asset_registry.json`
- Generates `asset_prompts.json` into the same run directory

### `generate_asset_images.py`

Current role:

- CLI entrypoint for the asset-image node
- Reads a validated `asset_prompts.json`
- Generates raw asset images and final labeled asset cards
- Writes `asset_images_manifest.json`

### `generate_storyboard.py`

Current role:

- CLI entrypoint for the storyboard node
- Reads a validated `style_bible.json`
- Resolves the matching `asset_registry.json` and `script_clean.txt`
- Generates `storyboard.json` into the same run directory

### `generate_shot_reference_boards.py`

Current role:

- CLI entrypoint for the shot-reference-board node
- Reads a validated `storyboard.json`
- Resolves the matching `asset_images_manifest.json`
- Generates one stitched board image per shot plus `shot_reference_manifest.json`

### `generate_video_jobs.py`

Current role:

- CLI entrypoint for the video-job assembly node
- Reads a validated `storyboard.json`
- Resolves the matching `shot_reference_manifest.json`, `asset_registry.json`, and `style_bible.json`
- Generates `video_jobs.json` into the same run directory

### `generate_shot_videos.py`

Current role:

- CLI entrypoint for the shot-video execution node
- Reads a validated `video_jobs.json`
- Supports single-shot execution for sample validation before batch runs
- Generates `shot_videos_manifest.json` plus per-shot request/response/video artifacts

### `generate_final_video.py`

Current role:

- CLI entrypoint for the final-video concatenation node
- Reads a validated `shot_videos_manifest.json`
- Concatenates succeeded shot videos into one final mp4
- Exposes both leading-trim and leading-blackout controls for per-shot preprocessing
- Generates `final_video_manifest.json`

### `publish_shot_reference_boards.py`

Current role:

- CLI entrypoint for the shot-board publishing node
- Reads a validated `shot_reference_manifest.json`
- Copies stitched board PNGs into a configured static-root directory
- Writes `board_public_url` values back into the manifest

### `publish_shot_reference_boards_to_jsdelivr.py`

Current role:

- Convenience CLI for the free GitHub-plus-jsDelivr publishing path
- Infers `owner/repo` and branch from a target public GitHub repo checkout
- Reuses the generic board publisher to generate jsDelivr-backed `board_public_url` values

### `pipeline/style_bible.py`

Current role:

- Loads and validates `asset_registry.json`
- Builds the style-bible request payload
- Calls the text model
- Normalizes observed field aliases and list-vs-string differences
- Validates the result against the style-bible schema
- Writes `style_bible.json`

### `pipeline/asset_prompts.py`

Current role:

- Loads and validates `style_bible.json`
- Resolves and validates the matching `asset_registry.json`
- Builds the asset-prompt request payload
- Calls the text model
- Normalizes observed prompt field aliases
- Deterministically fills non-model metadata such as labels, aspect ratios, and negative prompts
- Uses one shared asset-stage aspect ratio instead of per-asset-type fixed ratios, aligned with the reference project's asset-stage behavior
- Validates the final result against the asset-prompts schema
- Writes `asset_prompts.json`

### `pipeline/asset_images.py`

Current role:

- Loads and validates `asset_prompts.json`
- Builds image-generation jobs per asset
- Calls the image model for each character / scene / prop asset
- Downloads raw images from signed URLs using `curl`
- Adds stable local Chinese labels onto the final asset cards
- Writes `asset_images_manifest.json`

### `pipeline/storyboard.py`

Current role:

- Loads and validates `style_bible.json`
- Resolves and validates the matching `asset_registry.json`
- Loads `script_clean.txt`
- Builds a storyboard input digest for the text model
- Calls the text model
- Normalizes observed shot-field aliases and enum drifts
- Deterministically fills fixed top-level storyboard metadata
- Validates the final result against the storyboard schema
- Enforces extra cross-file checks such as contiguous segment coverage and valid shot asset references
- Writes `storyboard.json`

### `pipeline/shot_reference_boards.py`

Current role:

- Loads and validates `storyboard.json`
- Resolves and validates the matching `asset_images_manifest.json`
- Selects the shot's scene asset plus visible character/prop assets in deterministic order
- Chooses a fixed grid template from asset count
- Trims uniform outer borders from raw asset reference images before placement
- Uses an adaptive two-asset layout for `grid_2x1` boards so differing aspect ratios are shown completely before any attempt to maximize fill
- Uses edge-to-edge grid cells plus cover-fit composition so each occupied slot fills its assigned area
- Reserves a dedicated bottom label area per occupied slot so labels do not occlude the rendered reference imagery
- Renders a consistent local black label bar from clean text instead of reusing the padded labeled-card bitmap directly
- Renders one PNG stitched board per shot using local image composition only
- Writes `shot_reference_manifest.json`

### `pipeline/video_jobs.py`

Current role:

- Loads and validates `storyboard.json`
- Resolves and validates the matching `shot_reference_manifest.json`, `asset_registry.json`, and `style_bible.json`
- Assembles fixed 5-block video prompts from storyboard fields plus asset/style anchors
- Enforces prompt-length limits and first-frame URL readiness status
- Writes `video_jobs.json`

### `pipeline/shot_reference_publish.py`

Current role:

- Loads and validates `shot_reference_manifest.json`
- Publishes stitched board PNGs into a configured static directory
- Writes `board_public_url` values using a configured public base URL
- Records publish results for later video-job generation

### `pipeline/shot_videos.py`

Current role:

- Loads and validates `video_jobs.json`
- Builds the video-task payload using one shot prompt plus one `first_frame` image URL
- Submits content-generation tasks to the video model
- Polls task status and downloads succeeded video files
- Persists `shot_videos_manifest.json` incrementally as results accumulate so partial progress survives long-running interruptions

### `pipeline/final_video.py`

Current role:

- Loads and validates `shot_videos_manifest.json`
- Trims a configurable leading duration from each succeeded shot video before concat
- Optionally covers a short leading duration of each processed shot with pure black after trimming
- Builds an ffmpeg concat input list from the trimmed shot videos
- Re-encodes and concatenates all shot videos into `final_video.mp4`
- Writes `final_video_manifest.json`

### `schemas/asset_registry.py`

Current role:

- Defines the strict Pydantic schema for `asset_registry.json`
- Enforces ID format and cross-reference integrity

### `schemas/style_bible.py`

Current role:

- Defines the strict Pydantic schema for `style_bible.json`
- Validates the global visual-style contract for downstream prompt generation

### `schemas/intent_packet.py`

Current role:

- Defines the strict Pydantic schema for `intent_packet.json`
- Locks input mode, story intent, target spec, assumptions, and ambiguities

### `schemas/story_blueprint.py`

Current role:

- Defines the strict Pydantic schema for `story_blueprint.json`
- Enforces controlled character / scene / prop counts plus beat-sheet integrity

### `schemas/script_quality.py`

Current role:

- Defines the strict Pydantic schema for `script_quality_report.json`
- Validates hard-check aggregation and repair metadata before downstream handoff

### `schemas/asset_prompts.py`

Current role:

- Defines the strict Pydantic schema for `asset_prompts.json`
- Validates per-type prompt metadata and ID ordering

### `schemas/asset_images_manifest.py`

Current role:

- Defines the strict Pydantic schema for `asset_images_manifest.json`
- Validates per-type generated image metadata and ID ordering

### `schemas/storyboard.py`

Current role:

- Defines the strict Pydantic schema for `storyboard.json`
- Validates shot ID/order sequencing, fixed global video defaults, field enums, and per-shot list limits

### `schemas/shot_reference_manifest.py`

Current role:

- Defines the strict Pydantic schema for `shot_reference_manifest.json`
- Validates per-shot board metadata, template/cell counts, and slot coverage

### `schemas/video_jobs.py`

Current role:

- Defines the strict Pydantic schema for `video_jobs.json`
- Validates job ordering, fixed defaults, prompt-block structure, and ready-vs-blocked URL state

### `schemas/shot_videos_manifest.py`

Current role:

- Defines the strict Pydantic schema for `shot_videos_manifest.json`
- Validates per-shot execution results, status values, and sequential ordering

### `schemas/final_video_manifest.py`

Current role:

- Defines the strict Pydantic schema for `final_video_manifest.json`
- Records both `trim_leading_seconds` and `blackout_leading_seconds` inside the concat spec
- Validates concat trim settings, per-shot source/trimmed inputs, final output path metadata, and sequential shot ordering

### `prompts/asset_extraction.py`

Current role:

- Stores the production prompt template for asset extraction

### `prompts/style_bible.py`

Current role:

- Stores the production prompt template for style-bible generation

### `prompts/asset_prompts.py`

Current role:

- Stores the production prompt template for text-model generation of asset image prompts
- Targets reference-board style outputs rather than ordinary single illustrations

### `prompts/asset_images.py`

Current role:

- Builds deterministic image-generation prompts for reference-board layouts
- Leaves final text labels to local rendering instead of model-rendered text

### `prompts/storyboard.py`

Current role:

- Stores the production prompt template for storyboard generation
- Frames `storyboard.json` as a structured shot-planning contract for later board stitching and video-prompt assembly

### `agentkit.yaml`

Current role:

- Shared AgentKit project config

### `agentkit.local.yaml`

Current role:

- Local runtime envs
- Local model IDs and API keys

Notes:

- Local-only
- Must never be committed

### `smoke_test_models.py`

Current role:

- Direct model connectivity smoke tests
- Separate from the production AgentKit workflow

### `01-陨落的天才.txt`

Current role:

- Default script input for design and initial testing

### `BigBanana-AI-Director-main-2/`

Current role:

- Local reference project
- Used for prompt strategy and workflow design ideas only

### `memory-bank/`

Current role:

- Long-lived project memory
- Planning, architecture, prompt, and progress tracking

## Planned Runtime Structure

The module layout is now partially implemented:

- `pipeline/`
  - `runtime.py`
  - `io.py`
  - `asset_extraction.py`
  - `style_bible.py`
  - `asset_prompts.py`
  - `asset_images.py`
  - `storyboard.py`
  - `shot_reference_boards.py`
  - `shot_reference_publish.py`
  - `video_jobs.py`
  - `shot_videos.py`
  - `final_video.py`

- `prompts/`
  - `asset_extraction.py`
  - `style_bible.py`
  - `asset_prompts.py`
  - `asset_images.py`
  - `storyboard.py`
  - later: standalone video prompt helpers if needed

- `schemas/`
  - `asset_registry.py`
  - `style_bible.py`
  - `asset_prompts.py`
  - `asset_images_manifest.py`
  - `storyboard.py`
  - `shot_reference_manifest.py`
  - `video_jobs.py`
  - `shot_videos_manifest.py`
  - `final_video_manifest.py`

- `runs/`
  - generated outputs per execution

## Current Run Artifacts

The implemented nodes now write:

- `runs/runN/01_input/script_clean.txt`
- `runs/runN/01_input/script_clean.json`
- `runs/runN/02_assets/asset_extraction_request.json`
- `runs/runN/02_assets/asset_extraction_response.json`
- `runs/runN/02_assets/asset_registry.json`
- `runs/runN/03_style/style_bible_request.json`
- `runs/runN/03_style/style_bible_response.json`
- `runs/runN/03_style/style_bible.json`
- `runs/runN/04_asset_prompts/asset_prompts_request.json`
- `runs/runN/04_asset_prompts/asset_prompts_response.json`
- `runs/runN/04_asset_prompts/asset_prompts.json`
- `runs/runN/05_asset_images/asset_image_jobs.json`
- `runs/runN/05_asset_images/raw/...`
- `runs/runN/05_asset_images/characters/...`
- `runs/runN/05_asset_images/scenes/...`
- `runs/runN/05_asset_images/props/...`
- `runs/runN/05_asset_images/responses/...`
- `runs/runN/05_asset_images/asset_images_manifest.json`
- `runs/runN/06_storyboard/storyboard_input_digest.json`
- `runs/runN/06_storyboard/storyboard_request.json`
- `runs/runN/06_storyboard/storyboard_response.json`
- `runs/runN/06_storyboard/storyboard.json`
- `runs/runN/07_shot_reference_boards/boards/...`
- `runs/runN/07_shot_reference_boards/board_publish_result.json`
- `runs/runN/07_shot_reference_boards/shot_reference_manifest.json`
- `runs/runN/08_video_jobs/video_jobs.json`
- `runs/runN/09_shot_videos/requests/...`
- `runs/runN/09_shot_videos/responses/...`
- `runs/runN/09_shot_videos/videos/...`
- `runs/runN/09_shot_videos/shot_videos_manifest.json`
- `runs/runN/10_final/concat_inputs.txt`
- `runs/runN/10_final/final_video_manifest.json`
- `runs/runN/10_final/final_video.mp4`
- `runs/runN/10_final/trimmed/...`

## Model Compatibility Note

The current text model rejected `response_format={"type":"json_object"}`.

The implemented path therefore uses:

- strict prompt instructions
- deterministic field alias normalization for known deviations
- Pydantic validation as the final contract gate

The storyboard node follows the same pattern, with one extra layer:

- cross-file validation against `asset_registry.json` for segment coverage and shot asset references

## Contract Philosophy

- Every stage should accept structured input and produce structured output.
- Prefer JSON files between stages.
- Use stable asset IDs instead of free-text matching.
- Keep each stage independently testable.
- A later stage should read the prior stage's validated JSON rather than regenerate hidden in-memory state.
- When the image model produces unstable text rendering, generate clean imagery first and render labels locally.
