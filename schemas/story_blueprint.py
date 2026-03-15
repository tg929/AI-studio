"""Pydantic schema for story_blueprint.json."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from schemas.asset_registry import StrictModel


BEAT_ID_PATTERN = r"^beat_\d{3}$"
BeatId = Annotated[str, Field(pattern=BEAT_ID_PATTERN)]
CharacterRole = Literal["protagonist", "support", "antagonistic_force", "minor"]
BeatPurpose = Literal["setup", "pressure", "turn", "climax", "release"]


def _validate_sequential_ids(ids: list[str], prefix: str) -> None:
    expected = [f"{prefix}_{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise ValueError(f"{prefix} IDs must be sequential: expected {expected}, got {ids}")


def _ensure_unique(values: list[str], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates: {values}")


class CharacterPlan(StrictModel):
    name: str
    role: CharacterRole
    dramatic_function: str
    visual_seed: str


class ScenePlan(StrictModel):
    name: str
    dramatic_use: str
    visual_anchors: list[str] = Field(min_length=3, max_length=5)


class PropPlan(StrictModel):
    name: str
    significance: str
    visual_seed: str


class StoryBeat(StrictModel):
    beat_id: BeatId
    order: int = Field(ge=1)
    purpose: BeatPurpose
    summary: str
    scene_name: str
    character_focus: list[str]
    prop_focus: list[str]
    visual_anchors: list[str] = Field(min_length=1)
    emotion: str

    @model_validator(mode="after")
    def validate_story_beat(self) -> "StoryBeat":
        _ensure_unique(self.character_focus, "character_focus")
        _ensure_unique(self.prop_focus, "prop_focus")
        _ensure_unique(self.visual_anchors, "visual_anchors")
        if not self.summary:
            raise ValueError("summary must not be empty")
        if not self.scene_name:
            raise ValueError("scene_name must not be empty")
        if not self.emotion:
            raise ValueError("emotion must not be empty")
        return self


class StoryBlueprint(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    title: str
    logline: str
    theme: str
    narrative_arc: str
    character_plan: list[CharacterPlan] = Field(min_length=1, max_length=4)
    scene_plan: list[ScenePlan] = Field(min_length=1, max_length=3)
    prop_plan: list[PropPlan] = Field(max_length=3)
    beat_sheet: list[StoryBeat] = Field(min_length=3, max_length=8)
    ending_note: str
    consistency_notes: list[str]

    @model_validator(mode="after")
    def validate_story_blueprint(self) -> "StoryBlueprint":
        if not self.source_script_name:
            raise ValueError("source_script_name must not be empty")
        if not self.title:
            raise ValueError("title must not be empty")
        if not self.logline:
            raise ValueError("logline must not be empty")
        if not self.theme:
            raise ValueError("theme must not be empty")
        if not self.narrative_arc:
            raise ValueError("narrative_arc must not be empty")
        if not self.ending_note:
            raise ValueError("ending_note must not be empty")

        character_names = [item.name for item in self.character_plan]
        scene_names = [item.name for item in self.scene_plan]
        prop_names = [item.name for item in self.prop_plan]
        beat_ids = [item.beat_id for item in self.beat_sheet]
        beat_orders = [item.order for item in self.beat_sheet]

        _ensure_unique(character_names, "character_plan.name")
        _ensure_unique(scene_names, "scene_plan.name")
        _ensure_unique(prop_names, "prop_plan.name")
        _validate_sequential_ids(beat_ids, "beat")

        expected_orders = list(range(1, len(beat_orders) + 1))
        if beat_orders != expected_orders:
            raise ValueError(f"beat_sheet.order must be sequential: expected {expected_orders}, got {beat_orders}")

        known_characters = set(character_names)
        known_scenes = set(scene_names)
        known_props = set(prop_names)
        for beat in self.beat_sheet:
            if beat.scene_name not in known_scenes:
                raise ValueError(f"beat_sheet.scene_name is unknown: {beat.scene_name}")
            unknown_characters = sorted(set(beat.character_focus) - known_characters)
            if unknown_characters:
                raise ValueError(f"beat_sheet.character_focus contains unknown names: {unknown_characters}")
            unknown_props = sorted(set(beat.prop_focus) - known_props)
            if unknown_props:
                raise ValueError(f"beat_sheet.prop_focus contains unknown names: {unknown_props}")

        return self
