# Tech Stack

## Runtime

- Python 3.12
- AgentKit
- VeADK
- Shared workflow orchestration under `app/workflow_service.py`
- Persisted run-state under `app/run_state.py`
- Persisted operator review state under `app/review_state.py`
- Current operator console stack: FastAPI + uvicorn + custom HTML shell
- Planned next-step UI layer: NiceGUI

## Model Provider

- Volcano Engine / Ark
- Text model: configured locally in `agentkit.local.yaml`
- Image model: configured locally in `agentkit.local.yaml`
- Video model: configured locally in `agentkit.local.yaml`

## Current Project Files

- `simple_agent.py`: current AgentKit entrypoint
- `agentkit.yaml`: shared AgentKit config
- `agentkit.local.yaml`: local runtime envs and model settings
- `smoke_test_models.py`: standalone smoke test script

## Planned Supporting Libraries

- Standard library: `json`, `pathlib`, `dataclasses` or `pydantic`, `logging`, `subprocess`
- Operator console: `fastapi`, `uvicorn`, `nicegui`
- Image processing: likely `Pillow`
- Video stitching: likely `ffmpeg`
- Schema validation: likely `pydantic`

## Configuration Rules

- Keep secrets only in `agentkit.local.yaml` or local envs.
- Never commit local API keys.
- Keep stage outputs under a predictable run directory.

## Reference Sources

- Volcano Engine docs for AgentKit and VeADK
- `BigBanana-AI-Director-main-2` for prompt architecture ideas
- `vibe-coding` for memory-bank workflow
