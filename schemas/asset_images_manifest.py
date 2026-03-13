"""Pydantic schema for asset_images_manifest.json."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from schemas.asset_prompts import AssetAspectRatio
from schemas.asset_registry import CharacterId, PropId, SceneId, StrictModel


def _validate_sequential_ids(ids: list[str], prefix: str) -> None:
    expected = [f"{prefix}_{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise ValueError(f"{prefix} IDs must be sequential: expected {expected}, got {ids}")


class CharacterAssetImage(StrictModel):
    id: CharacterId
    name: str
    label_text: str
    aspect_ratio: AssetAspectRatio
    requested_size: str
    render_prompt: str
    negative_prompt: str
    raw_image_path: str
    local_image_path: str
    raw_response_path: str
    remote_url: str


class SceneAssetImage(StrictModel):
    id: SceneId
    name: str
    label_text: str
    aspect_ratio: AssetAspectRatio
    requested_size: str
    render_prompt: str
    negative_prompt: str
    raw_image_path: str
    local_image_path: str
    raw_response_path: str
    remote_url: str


class PropAssetImage(StrictModel):
    id: PropId
    name: str
    label_text: str
    aspect_ratio: AssetAspectRatio
    requested_size: str
    render_prompt: str
    negative_prompt: str
    raw_image_path: str
    local_image_path: str
    raw_response_path: str
    remote_url: str


class AssetImagesManifest(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    title: str
    image_model: str
    characters: list[CharacterAssetImage]
    scenes: list[SceneAssetImage]
    props: list[PropAssetImage]

    @model_validator(mode="after")
    def validate_images(self) -> "AssetImagesManifest":
        _validate_sequential_ids([item.id for item in self.characters], "char")
        _validate_sequential_ids([item.id for item in self.scenes], "scene")
        _validate_sequential_ids([item.id for item in self.props], "prop")
        return self
