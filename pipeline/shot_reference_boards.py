"""Shot reference board generation node."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from pipeline.io import read_json, write_json
from schemas.asset_images_manifest import AssetImagesManifest
from schemas.shot_reference_manifest import ShotReferenceManifest
from schemas.storyboard import Storyboard


CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
OUTER_PADDING_PX = 24
GUTTER_PX = 24
BACKGROUND_COLOR = "#FFFFFF"
BLANK_CELL_FILL = "#FFFFFF"
FIT_MODE = "contain"

LAYOUT_DIMENSIONS = {
    "grid_1x1": (1, 1),
    "grid_2x1": (2, 1),
    "grid_2x2": (2, 2),
    "grid_3x2": (3, 2),
}


@dataclass(frozen=True, slots=True)
class ShotReferenceBoardArtifacts:
    run_dir: Path
    board_dir: Path
    boards_dir: Path


def resolve_run_dir(storyboard_path: Path) -> Path:
    if storyboard_path.name != "storyboard.json":
        raise ValueError(f"Expected a storyboard.json file: {storyboard_path}")
    if storyboard_path.parent.name != "06_storyboard":
        raise ValueError(f"Expected storyboard.json under a 06_storyboard directory: {storyboard_path}")
    return storyboard_path.parent.parent


def resolve_asset_images_manifest_path(run_dir: Path) -> Path:
    manifest_path = run_dir / "05_asset_images" / "asset_images_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Asset images manifest not found for run directory: {manifest_path}")
    return manifest_path


def build_board_artifacts(run_dir: Path) -> ShotReferenceBoardArtifacts:
    board_dir = run_dir / "07_shot_reference_boards"
    boards_dir = board_dir / "boards"
    board_dir.mkdir(parents=True, exist_ok=True)
    boards_dir.mkdir(parents=True, exist_ok=True)
    return ShotReferenceBoardArtifacts(run_dir=run_dir, board_dir=board_dir, boards_dir=boards_dir)


def build_asset_image_map(asset_images_manifest: AssetImagesManifest) -> dict[str, dict[str, str]]:
    return {
        "scene": {item.id: item.local_image_path for item in asset_images_manifest.scenes},
        "character": {item.id: item.local_image_path for item in asset_images_manifest.characters},
        "prop": {item.id: item.local_image_path for item in asset_images_manifest.props},
    }


def resolve_layout_template(asset_count: int) -> str:
    if asset_count == 1:
        return "grid_1x1"
    if asset_count == 2:
        return "grid_2x1"
    if asset_count in {3, 4}:
        return "grid_2x2"
    if asset_count in {5, 6}:
        return "grid_3x2"
    raise ValueError(f"Unsupported asset_count for shot board layout: {asset_count}")


def build_target_boxes(layout_template: str) -> list[dict[str, int]]:
    cols, rows = LAYOUT_DIMENSIONS[layout_template]
    cell_width = (CANVAS_WIDTH - 2 * OUTER_PADDING_PX - (cols - 1) * GUTTER_PX) // cols
    cell_height = (CANVAS_HEIGHT - 2 * OUTER_PADDING_PX - (rows - 1) * GUTTER_PX) // rows

    boxes: list[dict[str, int]] = []
    slot_index = 1
    for row in range(rows):
        for col in range(cols):
            boxes.append(
                {
                    "slot_index": slot_index,
                    "row": row + 1,
                    "col": col + 1,
                    "x": OUTER_PADDING_PX + col * (cell_width + GUTTER_PX),
                    "y": OUTER_PADDING_PX + row * (cell_height + GUTTER_PX),
                    "width": cell_width,
                    "height": cell_height,
                }
            )
            slot_index += 1
    return boxes


def build_ordered_assets(shot, asset_image_map: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []

    scene_path = asset_image_map["scene"].get(shot.primary_scene_id)
    if not scene_path:
        raise FileNotFoundError(f"Scene asset image not found for {shot.primary_scene_id}")
    assets.append(
        {
            "asset_type": "scene",
            "asset_id": shot.primary_scene_id,
            "source_image_path": scene_path,
        }
    )

    primary_character_ids = [
        asset_id
        for asset_id in shot.primary_subject_ids
        if asset_id.startswith("char_") and asset_id in shot.visible_character_ids
    ]
    remaining_character_ids = [
        asset_id for asset_id in shot.visible_character_ids if asset_id not in primary_character_ids
    ]
    primary_prop_ids = [
        asset_id
        for asset_id in shot.primary_subject_ids
        if asset_id.startswith("prop_") and asset_id in shot.visible_prop_ids
    ]
    remaining_prop_ids = [asset_id for asset_id in shot.visible_prop_ids if asset_id not in primary_prop_ids]

    for character_id in primary_character_ids + remaining_character_ids:
        image_path = asset_image_map["character"].get(character_id)
        if not image_path:
            raise FileNotFoundError(f"Character asset image not found for {character_id}")
        assets.append(
            {
                "asset_type": "character",
                "asset_id": character_id,
                "source_image_path": image_path,
            }
        )

    for prop_id in primary_prop_ids + remaining_prop_ids:
        image_path = asset_image_map["prop"].get(prop_id)
        if not image_path:
            raise FileNotFoundError(f"Prop asset image not found for {prop_id}")
        assets.append(
            {
                "asset_type": "prop",
                "asset_id": prop_id,
                "source_image_path": image_path,
            }
        )

    return assets


def render_board_image(slots: list[dict[str, object]], output_path: Path) -> None:
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), color=BACKGROUND_COLOR)

    for slot in slots:
        source_image_path = Path(str(slot["source_image_path"]))
        image = Image.open(source_image_path).convert("RGB")
        box = slot["target_box"]
        box_width = int(box["width"])
        box_height = int(box["height"])

        scale = min(box_width / image.width, box_height / image.height)
        resized_width = max(1, int(image.width * scale))
        resized_height = max(1, int(image.height * scale))
        resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)

        paste_x = int(box["x"]) + (box_width - resized_width) // 2
        paste_y = int(box["y"]) + (box_height - resized_height) // 2
        canvas.paste(resized, (paste_x, paste_y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")


def generate_shot_reference_boards(*, storyboard_path: Path) -> ShotReferenceBoardArtifacts:
    storyboard = Storyboard.model_validate(read_json(storyboard_path))
    run_dir = resolve_run_dir(storyboard_path)
    asset_images_manifest = AssetImagesManifest.model_validate(read_json(resolve_asset_images_manifest_path(run_dir)))
    artifacts = build_board_artifacts(run_dir)
    asset_image_map = build_asset_image_map(asset_images_manifest)

    boards_payload: list[dict[str, object]] = []

    for shot in storyboard.shots:
        ordered_assets = build_ordered_assets(shot, asset_image_map)
        asset_count = len(ordered_assets)
        layout_template = resolve_layout_template(asset_count)
        target_boxes = build_target_boxes(layout_template)
        board_path = (artifacts.boards_dir / f"{shot.id}.png").resolve()

        slots_payload: list[dict[str, object]] = []
        blank_slots: list[int] = []
        for box, asset in zip(target_boxes, ordered_assets, strict=False):
            slots_payload.append(
                {
                    "slot_index": box["slot_index"],
                    "row": box["row"],
                    "col": box["col"],
                    "asset_type": asset["asset_type"],
                    "asset_id": asset["asset_id"],
                    "source_image_path": asset["source_image_path"],
                    "target_box": {
                        "x": box["x"],
                        "y": box["y"],
                        "width": box["width"],
                        "height": box["height"],
                    },
                }
            )
        blank_slots.extend(box["slot_index"] for box in target_boxes[len(ordered_assets) :])

        render_board_image(slots_payload, board_path)

        boards_payload.append(
            {
                "shot_id": shot.id,
                "order": shot.order,
                "layout_template": layout_template,
                "board_layout_hint": shot.board_layout_hint,
                "primary_scene_id": shot.primary_scene_id,
                "character_ids": shot.visible_character_ids,
                "prop_ids": shot.visible_prop_ids,
                "asset_count": asset_count,
                "blank_cell_count": len(blank_slots),
                "board_local_path": str(board_path),
                "board_public_url": "",
                "slots": slots_payload,
                "blank_slots": blank_slots,
            }
        )

    manifest_payload = {
        "schema_version": "1.0",
        "source_run": run_dir.name,
        "source_script_name": storyboard.source_script_name,
        "title": storyboard.title,
        "board_defaults": {
            "canvas_size": "1920x1080",
            "aspect_ratio": "16:9",
            "background_color": BACKGROUND_COLOR,
            "outer_padding_px": OUTER_PADDING_PX,
            "gutter_px": GUTTER_PX,
            "fit_mode": FIT_MODE,
            "preserve_asset_labels": True,
            "add_overlay_text": False,
            "blank_cell_fill": BLANK_CELL_FILL,
        },
        "boards": boards_payload,
    }
    manifest = ShotReferenceManifest.model_validate(manifest_payload)
    manifest_path = artifacts.board_dir / "shot_reference_manifest.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))

    return artifacts
