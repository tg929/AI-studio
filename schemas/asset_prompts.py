"""Pydantic schema for asset_prompts.json."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from schemas.asset_registry import CharacterId, PropId, SceneId, StrictModel


def _validate_sequential_ids(ids: list[str], prefix: str) -> None:
    expected = [f"{prefix}_{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise ValueError(f"{prefix} IDs must be sequential: expected {expected}, got {ids}")


class CharacterAssetPrompt(StrictModel):
    id: CharacterId
    name: str
    label_text: str
    prompt: str
    negative_prompt: str
    aspect_ratio: Literal["3:4"]
    framing: str
    background_treatment: str
    generation_intent: str
    card_layout_notes: str


class SceneAssetPrompt(StrictModel):
    id: SceneId
    name: str
    label_text: str
    prompt: str
    negative_prompt: str
    aspect_ratio: Literal["16:9"]
    framing: str
    figure_policy: Literal["no_identifiable_characters"]
    generation_intent: str
    card_layout_notes: str


class PropAssetPrompt(StrictModel):
    id: PropId
    name: str
    label_text: str
    prompt: str
    negative_prompt: str
    aspect_ratio: Literal["1:1"]
    framing: str
    isolation_rules: str
    generation_intent: str
    card_layout_notes: str


class AssetPrompts(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    title: str
    visual_style: str
    consistency_anchors: str
    characters: list[CharacterAssetPrompt]
    scenes: list[SceneAssetPrompt]
    props: list[PropAssetPrompt]

    @model_validator(mode="after")
    def validate_prompt_sets(self) -> "AssetPrompts":
        _validate_sequential_ids([item.id for item in self.characters], "char")
        _validate_sequential_ids([item.id for item in self.scenes], "scene")
        _validate_sequential_ids([item.id for item in self.props], "prop")
        return self
