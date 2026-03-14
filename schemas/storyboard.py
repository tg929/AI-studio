"""Pydantic schema for storyboard.json."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from schemas.asset_registry import CharacterId, PropId, SceneId, SegmentId, StrictModel


SHOT_ID_PATTERN = r"^shot_\d{3}$"
ShotId = Annotated[str, Field(pattern=SHOT_ID_PATTERN)]

ShotType = Literal["establishing", "reaction", "dialogue", "action", "insert", "transition"]
BoardLayoutHint = Literal[
    "scene_dominant",
    "single_character",
    "multi_character",
    "prop_insert",
    "balanced",
]
ShotSize = Literal["wide", "full", "medium_full", "medium", "medium_close", "close", "extreme_close"]
CameraAngle = Literal[
    "eye_level",
    "low_angle",
    "high_angle",
    "over_shoulder",
    "profile",
    "top_down",
    "dutch",
]
CameraMovement = Literal[
    "static",
    "slow_push_in",
    "slow_pull_out",
    "pan_left",
    "pan_right",
    "track_left",
    "track_right",
    "follow",
    "arc",
    "tilt_up",
    "tilt_down",
]
FirstFrameMode = Literal["stitched_asset_board"]
FirstFrameTransition = Literal["fast_transform_into_cinematic_scene"]
PromptLanguage = Literal["zh-CN"]

_MULTI_SHOT_MARKERS = (
    "镜头一",
    "镜头二",
    "镜头三",
    "镜头1",
    "镜头2",
    "镜头3",
    "切到",
    "再切",
    "cut to",
    "shot 1",
    "shot 2",
    "shot1",
    "shot2",
)


def _validate_sequential_ids(ids: list[str], prefix: str) -> None:
    expected = [f"{prefix}_{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise ValueError(f"{prefix} IDs must be sequential: expected {expected}, got {ids}")


def _ensure_unique(values: list[str], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates: {values}")


class GlobalVideoSpec(StrictModel):
    shot_duration_sec: Literal[10]
    aspect_ratio: Literal["16:9"]
    first_frame_mode: FirstFrameMode
    first_frame_transition: FirstFrameTransition
    prompt_language: PromptLanguage


class StoryboardShot(StrictModel):
    id: ShotId
    order: int = Field(ge=1)
    segment_ids: list[SegmentId] = Field(min_length=1)
    duration_sec: Literal[10]

    primary_scene_id: SceneId

    character_ids: list[CharacterId]
    visible_character_ids: list[CharacterId]

    prop_ids: list[PropId]
    visible_prop_ids: list[PropId]

    primary_subject_ids: list[str] = Field(min_length=1)

    shot_type: ShotType
    board_layout_hint: BoardLayoutHint

    shot_size: ShotSize
    camera_angle: CameraAngle
    camera_movement: CameraMovement

    shot_purpose: str
    subject_action: str
    background_action: str
    emotion_tone: str
    continuity_notes: list[str]
    prompt_core: str

    @model_validator(mode="after")
    def validate_shot(self) -> "StoryboardShot":
        _ensure_unique(self.segment_ids, "segment_ids")
        _ensure_unique(self.character_ids, "character_ids")
        _ensure_unique(self.visible_character_ids, "visible_character_ids")
        _ensure_unique(self.prop_ids, "prop_ids")
        _ensure_unique(self.visible_prop_ids, "visible_prop_ids")
        _ensure_unique(self.primary_subject_ids, "primary_subject_ids")

        if len(self.visible_character_ids) > 4:
            raise ValueError("visible_character_ids must contain at most 4 items")
        if len(self.visible_prop_ids) > 1:
            raise ValueError("visible_prop_ids must contain at most 1 item")
        if len(self.continuity_notes) > 5:
            raise ValueError("continuity_notes must contain at most 5 items")

        if not self.shot_purpose:
            raise ValueError("shot_purpose must not be empty")
        if not self.subject_action:
            raise ValueError("subject_action must not be empty")
        if not self.emotion_tone:
            raise ValueError("emotion_tone must not be empty")
        if not self.prompt_core:
            raise ValueError("prompt_core must not be empty")

        lowered_prompt_core = self.prompt_core.lower()
        if any(marker in lowered_prompt_core for marker in _MULTI_SHOT_MARKERS):
            raise ValueError("prompt_core must describe a single shot without cut markers")

        for subject_id in self.primary_subject_ids:
            if not subject_id.startswith(("scene_", "char_", "prop_")):
                raise ValueError(f"primary_subject_ids contains invalid asset prefix: {subject_id}")

        return self


class Storyboard(StrictModel):
    schema_version: Literal["1.0"]
    source_run: str
    source_script_name: str
    title: str
    global_video_spec: GlobalVideoSpec
    shots: list[StoryboardShot] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_storyboard(self) -> "Storyboard":
        shot_ids = [item.id for item in self.shots]
        shot_orders = [item.order for item in self.shots]

        _validate_sequential_ids(shot_ids, "shot")

        expected_orders = list(range(1, len(shot_orders) + 1))
        if shot_orders != expected_orders:
            raise ValueError(f"shots.order must be sequential: expected {expected_orders}, got {shot_orders}")

        return self
