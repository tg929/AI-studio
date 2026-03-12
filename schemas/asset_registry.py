"""Pydantic schema for asset_registry.json."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CHAR_ID_PATTERN = r"^char_\d{3}$"
SCENE_ID_PATTERN = r"^scene_\d{3}$"
PROP_ID_PATTERN = r"^prop_\d{3}$"
SEGMENT_ID_PATTERN = r"^seg_\d{3}$"

CharacterId = Annotated[str, Field(pattern=CHAR_ID_PATTERN)]
SceneId = Annotated[str, Field(pattern=SCENE_ID_PATTERN)]
PropId = Annotated[str, Field(pattern=PROP_ID_PATTERN)]
SegmentId = Annotated[str, Field(pattern=SEGMENT_ID_PATTERN)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StoryMeta(StrictModel):
    era: str
    world_setting: str
    tone: str
    core_conflict: str


class RelationshipTarget(StrictModel):
    character_id: CharacterId
    relation: str
    description: str


class CharacterAsset(StrictModel):
    id: CharacterId
    name: str
    aliases: list[str]
    role_type: Literal["main", "supporting", "minor"]
    gender: str
    age: str
    occupation_identity: str
    personality_traits: list[str]
    appearance_summary: str
    costume_summary: str
    identity_markers: list[str]
    must_keep_features: list[str]
    relationship_targets: list[RelationshipTarget]
    signature_prop_ids: list[PropId]
    default_scene_ids: list[SceneId]
    first_appearance_segment_id: SegmentId


class SceneAsset(StrictModel):
    id: SceneId
    name: str
    location: str
    scene_type: Literal["interior", "exterior", "mixed", "unknown"]
    time_of_day: str
    weather: str
    atmosphere: str
    environment_summary: str
    key_visual_elements: list[str]
    must_keep_features: list[str]
    default_character_ids: list[CharacterId]
    default_prop_ids: list[PropId]
    first_appearance_segment_id: SegmentId


class PropAsset(StrictModel):
    id: PropId
    name: str
    aliases: list[str]
    category: Literal[
        "weapon",
        "document",
        "food_drink",
        "vehicle",
        "ornament",
        "device",
        "daily_item",
        "other",
    ]
    owner_character_ids: list[CharacterId]
    default_scene_ids: list[SceneId]
    significance: str
    visual_summary: str
    material_texture: str
    condition_state: str
    must_keep_features: list[str]
    first_appearance_segment_id: SegmentId


class StorySegment(StrictModel):
    id: SegmentId
    order: int = Field(ge=1)
    summary: str
    text: str
    scene_ids: list[SceneId]
    character_ids: list[CharacterId]
    prop_ids: list[PropId]


class Ambiguity(StrictModel):
    type: str
    target_id: str
    note: str


def _validate_sequential_ids(ids: list[str], prefix: str) -> None:
    expected = [f"{prefix}_{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise ValueError(f"{prefix} IDs must be sequential: expected {expected}, got {ids}")


def _ensure_known_references(values: list[str], allowed: set[str], field_name: str) -> None:
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(f"{field_name} contains unknown references: {unknown}")


class AssetRegistry(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    title: str
    genre: str
    logline: str
    story_meta: StoryMeta
    characters: list[CharacterAsset]
    scenes: list[SceneAsset]
    props: list[PropAsset]
    story_segments: list[StorySegment]
    consistency_notes: list[str]
    ambiguities: list[Ambiguity]

    @model_validator(mode="after")
    def validate_registry(self) -> "AssetRegistry":
        character_ids = [item.id for item in self.characters]
        scene_ids = [item.id for item in self.scenes]
        prop_ids = [item.id for item in self.props]
        segment_ids = [item.id for item in self.story_segments]

        _validate_sequential_ids(character_ids, "char")
        _validate_sequential_ids(scene_ids, "scene")
        _validate_sequential_ids(prop_ids, "prop")
        _validate_sequential_ids(segment_ids, "seg")

        character_set = set(character_ids)
        scene_set = set(scene_ids)
        prop_set = set(prop_ids)
        segment_set = set(segment_ids)

        for character in self.characters:
            _ensure_known_references(character.signature_prop_ids, prop_set, "character.signature_prop_ids")
            _ensure_known_references(character.default_scene_ids, scene_set, "character.default_scene_ids")
            if character.first_appearance_segment_id not in segment_set:
                raise ValueError(
                    f"character.first_appearance_segment_id is unknown: {character.first_appearance_segment_id}"
                )
            for relationship in character.relationship_targets:
                if relationship.character_id not in character_set:
                    raise ValueError(
                        f"character.relationship_targets contains unknown character_id: {relationship.character_id}"
                    )

        for scene in self.scenes:
            _ensure_known_references(scene.default_character_ids, character_set, "scene.default_character_ids")
            _ensure_known_references(scene.default_prop_ids, prop_set, "scene.default_prop_ids")
            if scene.first_appearance_segment_id not in segment_set:
                raise ValueError(
                    f"scene.first_appearance_segment_id is unknown: {scene.first_appearance_segment_id}"
                )

        for prop in self.props:
            _ensure_known_references(prop.owner_character_ids, character_set, "prop.owner_character_ids")
            _ensure_known_references(prop.default_scene_ids, scene_set, "prop.default_scene_ids")
            if prop.first_appearance_segment_id not in segment_set:
                raise ValueError(
                    f"prop.first_appearance_segment_id is unknown: {prop.first_appearance_segment_id}"
                )

        orders = [segment.order for segment in self.story_segments]
        expected_orders = list(range(1, len(orders) + 1))
        if orders != expected_orders:
            raise ValueError(
                f"story_segments.order must be sequential: expected {expected_orders}, got {orders}"
            )

        for segment in self.story_segments:
            _ensure_known_references(segment.scene_ids, scene_set, "story_segment.scene_ids")
            _ensure_known_references(segment.character_ids, character_set, "story_segment.character_ids")
            _ensure_known_references(segment.prop_ids, prop_set, "story_segment.prop_ids")

        return self
