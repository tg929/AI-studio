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

The exact module layout is not implemented yet, but the current target shape is:

- `workflow/` or `pipeline/`
  - script preprocessing
  - asset extraction
  - art direction
  - asset prompt generation
  - asset image generation
  - storyboard generation
  - shot board stitching
  - shot video generation
  - final video concatenation

- `prompts/`
  - asset extraction prompt
  - asset image prompt
  - storyboard prompt
  - video prompt

- `schemas/`
  - JSON schema or Pydantic models for stage contracts

- `runs/`
  - generated outputs per execution

## Contract Philosophy

- Every stage should accept structured input and produce structured output.
- Prefer JSON files between stages.
- Use stable asset IDs instead of free-text matching.
- Keep each stage independently testable.
