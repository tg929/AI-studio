"""Pydantic schema for intent_packet.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.asset_registry import StrictModel


InputMode = Literal["keywords", "brief", "script"]
InformationDensity = Literal["sparse", "medium", "rich"]
ExpansionBudget = Literal["low", "medium", "high"]
DialogueDensity = Literal["low", "medium", "high"]
EndingShape = Literal["closed", "open", "hook_next"]


class TargetSpec(StrictModel):
    target_runtime_sec: int = Field(ge=30, le=180)
    target_shot_count: int = Field(ge=3, le=12)
    target_script_length_chars: int = Field(ge=800, le=6000)
    dialogue_density: DialogueDensity
    ending_shape: EndingShape


class IntentPacket(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    input_mode: InputMode
    raw_input: str
    language: Literal["zh-CN"]
    information_density: InformationDensity
    expansion_budget: ExpansionBudget
    intent_summary: str
    genre: str
    tone: str
    era: str
    world_setting: str
    core_conflict: str
    protagonist_seed: str
    must_have_elements: list[str]
    forbidden_elements: list[str]
    target_spec: TargetSpec
    assumptions: list[str]
    ambiguities: list[str]

    @model_validator(mode="after")
    def validate_intent_packet(self) -> "IntentPacket":
        if not self.source_script_name:
            raise ValueError("source_script_name must not be empty")
        if not self.raw_input:
            raise ValueError("raw_input must not be empty")
        if not self.intent_summary:
            raise ValueError("intent_summary must not be empty")
        if not self.genre:
            raise ValueError("genre must not be empty")
        if not self.tone:
            raise ValueError("tone must not be empty")
        if not self.core_conflict:
            raise ValueError("core_conflict must not be empty")
        if not self.protagonist_seed:
            raise ValueError("protagonist_seed must not be empty")
        return self
