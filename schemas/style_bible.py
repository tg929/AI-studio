"""Pydantic schema for style_bible.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.asset_registry import StrictModel


class ColorPalette(StrictModel):
    primary: str
    secondary: str
    accent: str
    skin_tones: str
    saturation: str
    temperature: str


class CharacterDesignRules(StrictModel):
    proportions: str
    face_rendering: str
    hair_rendering: str
    costume_rendering: str
    detail_level: str


class SceneDesignRules(StrictModel):
    environment_density: str
    architectural_language: str
    prop_integration: str
    spatial_composition: str


class AssetCardRules(StrictModel):
    label_language: Literal["zh-CN"]
    label_position: str
    label_style: str
    layout_style: str
    prohibited_elements: list[str]


class StyleBible(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    title: str
    genre: str
    story_tone: str
    visual_style: str
    era: str
    world_setting: str
    color_palette: ColorPalette
    character_design_rules: CharacterDesignRules
    scene_design_rules: SceneDesignRules
    lighting_style: str
    texture_style: str
    composition_rules: list[str] = Field(min_length=3)
    asset_card_rules: AssetCardRules
    mood_keywords: list[str] = Field(min_length=3)
    negative_keywords: list[str] = Field(min_length=3)
    consistency_anchors: str

    @model_validator(mode="after")
    def validate_style_bible(self) -> "StyleBible":
        if not self.consistency_anchors:
            raise ValueError("consistency_anchors must not be empty")
        if not self.visual_style:
            raise ValueError("visual_style must not be empty")
        if not self.asset_card_rules.prohibited_elements:
            raise ValueError("asset_card_rules.prohibited_elements must not be empty")
        return self
