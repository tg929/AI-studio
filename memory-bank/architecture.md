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

### `pipeline/style_bible.py`

Current role:

- Loads and validates `asset_registry.json`
- Builds the style-bible request payload
- Calls the text model
- Normalizes observed field aliases and list-vs-string differences
- Validates the result against the style-bible schema
- Writes `style_bible.json`

### `schemas/asset_registry.py`

Current role:

- Defines the strict Pydantic schema for `asset_registry.json`
- Enforces ID format and cross-reference integrity

### `schemas/style_bible.py`

Current role:

- Defines the strict Pydantic schema for `style_bible.json`
- Validates the global visual-style contract for downstream prompt generation

### `prompts/asset_extraction.py`

Current role:

- Stores the production prompt template for asset extraction

### `prompts/style_bible.py`

Current role:

- Stores the production prompt template for style-bible generation

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
  - later: asset prompts, image generation, storyboard, board stitching, video generation, final concat

- `prompts/`
  - `asset_extraction.py`
  - `style_bible.py`
  - later: asset image prompt, storyboard prompt, video prompt

- `schemas/`
  - `asset_registry.py`
  - `style_bible.py`
  - later: storyboard, video job schemas

- `runs/`
  - generated outputs per execution

## Current Run Artifacts

The implemented nodes now write:

- `runs/<timestamp>/01_input/script_clean.txt`
- `runs/<timestamp>/01_input/script_clean.json`
- `runs/<timestamp>/02_assets/asset_extraction_request.json`
- `runs/<timestamp>/02_assets/asset_extraction_response.json`
- `runs/<timestamp>/02_assets/asset_registry.json`
- `runs/<timestamp>/03_style/style_bible_request.json`
- `runs/<timestamp>/03_style/style_bible_response.json`
- `runs/<timestamp>/03_style/style_bible.json`

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
