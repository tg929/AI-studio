# Architecture

Last updated: 2026-03-12

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

### `pipeline/runtime.py`

Current role:

- Loads local text-model runtime config from `agentkit.local.yaml`
- Builds the Ark client for workflow nodes
- Loads local image-model runtime config from `agentkit.local.yaml`

### `pipeline/io.py`

Current role:

- Shared JSON and model-response helpers for workflow nodes
- Centralizes `write_json`, `read_json`, response dumping, and text-content extraction

### `pipeline/asset_extraction.py`

Current role:

- Normalizes script text
- Writes input artifacts
- Calls the text model
- Normalizes observed model field aliases
- Validates the result against the asset schema
- Writes `asset_registry.json`

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

### `schemas/asset_registry.py`

Current role:

- Defines the strict Pydantic schema for `asset_registry.json`
- Enforces ID format and cross-reference integrity

### `schemas/style_bible.py`

Current role:

- Defines the strict Pydantic schema for `style_bible.json`
- Validates the global visual-style contract for downstream prompt generation

### `schemas/asset_prompts.py`

Current role:

- Defines the strict Pydantic schema for `asset_prompts.json`
- Validates per-type prompt metadata and ID ordering

### `schemas/asset_images_manifest.py`

Current role:

- Defines the strict Pydantic schema for `asset_images_manifest.json`
- Validates per-type generated image metadata and ID ordering

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
  - later: storyboard, board stitching, video generation, final concat

- `prompts/`
  - `asset_extraction.py`
  - `style_bible.py`
  - `asset_prompts.py`
  - `asset_images.py`
  - later: storyboard prompt, video prompt

- `schemas/`
  - `asset_registry.py`
  - `style_bible.py`
  - `asset_prompts.py`
  - `asset_images_manifest.py`
  - later: storyboard, video job schemas

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

## Model Compatibility Note

The current text model rejected `response_format={"type":"json_object"}`.

The implemented path therefore uses:

- strict prompt instructions
- deterministic field alias normalization for known deviations
- Pydantic validation as the final contract gate

## Contract Philosophy

- Every stage should accept structured input and produce structured output.
- Prefer JSON files between stages.
- Use stable asset IDs instead of free-text matching.
- Keep each stage independently testable.
- A later stage should read the prior stage's validated JSON rather than regenerate hidden in-memory state.
- When the image model produces unstable text rendering, generate clean imagery first and render labels locally.
