"""Pydantic schema for shot_reference_manifest.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.asset_registry import CharacterId, PropId, SceneId, StrictModel
from schemas.storyboard import BoardLayoutHint, ShotId


BoardLayoutTemplate = Literal["grid_1x1", "grid_2x1", "grid_2x2", "grid_3x2"]
AssetSlotType = Literal["scene", "character", "prop"]

_TEMPLATE_CELL_COUNTS = {
    "grid_1x1": 1,
    "grid_2x1": 2,
    "grid_2x2": 4,
    "grid_3x2": 6,
}


def _validate_sequential_ids(ids: list[str], prefix: str) -> None:
    expected = [f"{prefix}_{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise ValueError(f"{prefix} IDs must be sequential: expected {expected}, got {ids}")


class BoardDefaults(StrictModel):
    canvas_size: Literal["1920x1080"]
    aspect_ratio: Literal["16:9"]
    background_color: str
    outer_padding_px: int = Field(ge=0)
    gutter_px: int = Field(ge=0)
    fit_mode: Literal["contain"]
    preserve_asset_labels: Literal[True]
    add_overlay_text: Literal[False]
    blank_cell_fill: str


class TargetBox(StrictModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class BoardSlot(StrictModel):
    slot_index: int = Field(ge=1)
    row: int = Field(ge=1)
    col: int = Field(ge=1)
    asset_type: AssetSlotType
    asset_id: str
    source_image_path: str
    target_box: TargetBox

    @model_validator(mode="after")
    def validate_slot(self) -> "BoardSlot":
        prefix_map = {
            "scene": "scene_",
            "character": "char_",
            "prop": "prop_",
        }
        expected_prefix = prefix_map[self.asset_type]
        if not self.asset_id.startswith(expected_prefix):
            raise ValueError(
                f"asset_id prefix does not match asset_type {self.asset_type}: {self.asset_id}"
            )
        return self


class ShotReferenceBoard(StrictModel):
    shot_id: ShotId
    order: int = Field(ge=1)
    layout_template: BoardLayoutTemplate
    board_layout_hint: BoardLayoutHint

    primary_scene_id: SceneId
    character_ids: list[CharacterId]
    prop_ids: list[PropId]

    asset_count: int = Field(ge=1, le=6)
    blank_cell_count: int = Field(ge=0)

    board_local_path: str
    board_public_url: str

    slots: list[BoardSlot] = Field(min_length=1)
    blank_slots: list[int]

    @model_validator(mode="after")
    def validate_board(self) -> "ShotReferenceBoard":
        expected_cells = _TEMPLATE_CELL_COUNTS[self.layout_template]
        slot_indexes = [item.slot_index for item in self.slots]
        if len(slot_indexes) != len(set(slot_indexes)):
            raise ValueError(f"slots must not contain duplicate slot_index values: {slot_indexes}")
        if len(self.blank_slots) != len(set(self.blank_slots)):
            raise ValueError(f"blank_slots must not contain duplicates: {self.blank_slots}")
        if self.asset_count != len(self.slots):
            raise ValueError(f"asset_count must equal len(slots): {self.asset_count} vs {len(self.slots)}")
        if self.blank_cell_count != len(self.blank_slots):
            raise ValueError(
                f"blank_cell_count must equal len(blank_slots): {self.blank_cell_count} vs {len(self.blank_slots)}"
            )
        if self.asset_count + self.blank_cell_count != expected_cells:
            raise ValueError(
                f"layout_template {self.layout_template} expects {expected_cells} cells, got "
                f"{self.asset_count + self.blank_cell_count}"
            )
        expected_slot_range = list(range(1, expected_cells + 1))
        actual_slot_range = sorted(slot_indexes + self.blank_slots)
        if actual_slot_range != expected_slot_range:
            raise ValueError(
                f"slots + blank_slots must exactly fill template cells: expected {expected_slot_range}, "
                f"got {actual_slot_range}"
            )
        return self


class ShotReferenceManifest(StrictModel):
    schema_version: Literal["1.0"]
    source_run: str
    source_script_name: str
    title: str
    board_defaults: BoardDefaults
    boards: list[ShotReferenceBoard] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> "ShotReferenceManifest":
        shot_ids = [item.shot_id for item in self.boards]
        orders = [item.order for item in self.boards]

        _validate_sequential_ids(shot_ids, "shot")

        expected_orders = list(range(1, len(orders) + 1))
        if orders != expected_orders:
            raise ValueError(f"boards.order must be sequential: expected {expected_orders}, got {orders}")

        return self
