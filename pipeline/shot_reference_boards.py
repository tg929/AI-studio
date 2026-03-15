"""Shot reference board generation node."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

from pipeline.io import read_json, write_json
from schemas.asset_images_manifest import AssetImagesManifest
from schemas.shot_reference_manifest import ShotReferenceManifest
from schemas.storyboard import Storyboard


CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
OUTER_PADDING_PX = 0
GUTTER_PX = 0
BACKGROUND_COLOR = "#FFFFFF"
BLANK_CELL_FILL = "#FFFFFF"
FIT_MODE = "adaptive"
LABEL_BAR_FILL = "#000000"
LABEL_TEXT_FILL = "#FFFFFF"
LABEL_BAR_HEIGHT_RATIO = 0.14
LABEL_BAR_MIN_HEIGHT_PX = 72
LABEL_BAR_MAX_HEIGHT_PX = 104
LABEL_SIDE_PADDING_PX = 24
LABEL_FONT_MIN_SIZE = 18
LABEL_FONT_DIVISOR = 3
DUAL_ASSET_GAP_PX = 24
BORDER_ACTIVITY_STD_THRESHOLD = 14.0
TRIM_BACKOFF_PX = 2
MAX_VERTICAL_TRIM_RATIO = 0.12
MAX_HORIZONTAL_TRIM_RATIO = 0.08

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


def build_asset_image_map(asset_images_manifest: AssetImagesManifest) -> dict[str, dict[str, dict[str, str]]]:
    return {
        "scene": {
            item.id: {
                "source_image_path": item.raw_image_path or item.local_image_path,
                "label_text": item.label_text,
            }
            for item in asset_images_manifest.scenes
        },
        "character": {
            item.id: {
                "source_image_path": item.raw_image_path or item.local_image_path,
                "label_text": item.label_text,
            }
            for item in asset_images_manifest.characters
        },
        "prop": {
            item.id: {
                "source_image_path": item.raw_image_path or item.local_image_path,
                "label_text": item.label_text,
            }
            for item in asset_images_manifest.props
        },
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


def build_dual_asset_boxes(ordered_assets: list[dict[str, str]]) -> list[dict[str, int]]:
    if len(ordered_assets) != 2:
        raise ValueError(f"Dual-asset layout expects exactly 2 assets, got {len(ordered_assets)}")

    label_height = resolve_label_height(CANVAS_HEIGHT)
    max_image_height = max(1, CANVAS_HEIGHT - label_height)
    aspects: list[float] = []
    for asset in ordered_assets:
        trimmed_width, trimmed_height = load_trimmed_image(asset["source_image_path"]).size
        aspects.append(trimmed_width / trimmed_height)

    available_width = CANVAS_WIDTH - 2 * OUTER_PADDING_PX - DUAL_ASSET_GAP_PX
    common_image_height = min(
        max_image_height,
        max(1, int(available_width / sum(aspects))),
    )
    widths = [max(1, int(round(aspect * common_image_height))) for aspect in aspects]
    row_width = sum(widths) + DUAL_ASSET_GAP_PX
    if row_width > CANVAS_WIDTH:
        overflow = row_width - CANVAS_WIDTH
        widths[-1] = max(1, widths[-1] - overflow)
        row_width = sum(widths) + DUAL_ASSET_GAP_PX

    box_height = common_image_height + label_height
    start_x = max(0, (CANVAS_WIDTH - row_width) // 2)
    start_y = max(0, (CANVAS_HEIGHT - box_height) // 2)

    boxes: list[dict[str, int]] = []
    current_x = start_x
    for index, width in enumerate(widths, start=1):
        boxes.append(
            {
                "slot_index": index,
                "row": 1,
                "col": index,
                "x": current_x,
                "y": start_y,
                "width": width,
                "height": box_height,
            }
        )
        current_x += width + DUAL_ASSET_GAP_PX
    return boxes


def build_ordered_assets(shot, asset_image_map: dict[str, dict[str, dict[str, str]]]) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []

    scene_asset = asset_image_map["scene"].get(shot.primary_scene_id)
    if not scene_asset:
        raise FileNotFoundError(f"Scene asset image not found for {shot.primary_scene_id}")
    assets.append(
        {
            "asset_type": "scene",
            "asset_id": shot.primary_scene_id,
            "source_image_path": scene_asset["source_image_path"],
            "label_text": scene_asset["label_text"],
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
        asset_entry = asset_image_map["character"].get(character_id)
        if not asset_entry:
            raise FileNotFoundError(f"Character asset image not found for {character_id}")
        assets.append(
            {
                "asset_type": "character",
                "asset_id": character_id,
                "source_image_path": asset_entry["source_image_path"],
                "label_text": asset_entry["label_text"],
            }
        )

    for prop_id in primary_prop_ids + remaining_prop_ids:
        asset_entry = asset_image_map["prop"].get(prop_id)
        if not asset_entry:
            raise FileNotFoundError(f"Prop asset image not found for {prop_id}")
        assets.append(
            {
                "asset_type": "prop",
                "asset_id": prop_id,
                "source_image_path": asset_entry["source_image_path"],
                "label_text": asset_entry["label_text"],
            }
        )

    return assets


def resolve_label_font_path() -> Path:
    candidates = [
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("No usable Chinese font file found for shot board label rendering")


def fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: Path, max_width: int, font_size: int) -> ImageFont.FreeTypeFont:
    while font_size >= LABEL_FONT_MIN_SIZE:
        font = ImageFont.truetype(str(font_path), font_size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= max_width:
            return font
        font_size -= 2
    return ImageFont.truetype(str(font_path), LABEL_FONT_MIN_SIZE)


def _row_activity_score(image: Image.Image, row_index: int) -> float:
    stat = ImageStat.Stat(image.crop((0, row_index, image.width, row_index + 1)))
    return float(sum(stat.stddev) / len(stat.stddev))


def _column_activity_score(image: Image.Image, column_index: int) -> float:
    stat = ImageStat.Stat(image.crop((column_index, 0, column_index + 1, image.height)))
    return float(sum(stat.stddev) / len(stat.stddev))


def _detect_trim_start(image: Image.Image) -> int:
    max_trim = max(0, int(image.height * MAX_VERTICAL_TRIM_RATIO))
    for offset in range(max_trim):
        if _row_activity_score(image, offset) >= BORDER_ACTIVITY_STD_THRESHOLD:
            return max(0, offset - TRIM_BACKOFF_PX)
    return 0


def _detect_trim_end(image: Image.Image) -> int:
    max_trim = max(0, int(image.height * MAX_VERTICAL_TRIM_RATIO))
    for offset in range(max_trim):
        row_index = image.height - 1 - offset
        if _row_activity_score(image, row_index) >= BORDER_ACTIVITY_STD_THRESHOLD:
            return max(0, offset - TRIM_BACKOFF_PX)
    return 0


def _detect_trim_left(image: Image.Image) -> int:
    max_trim = max(0, int(image.width * MAX_HORIZONTAL_TRIM_RATIO))
    for offset in range(max_trim):
        if _column_activity_score(image, offset) >= BORDER_ACTIVITY_STD_THRESHOLD:
            return max(0, offset - TRIM_BACKOFF_PX)
    return 0


def _detect_trim_right(image: Image.Image) -> int:
    max_trim = max(0, int(image.width * MAX_HORIZONTAL_TRIM_RATIO))
    for offset in range(max_trim):
        column_index = image.width - 1 - offset
        if _column_activity_score(image, column_index) >= BORDER_ACTIVITY_STD_THRESHOLD:
            return max(0, offset - TRIM_BACKOFF_PX)
    return 0


def trim_uniform_border(image: Image.Image) -> Image.Image:
    top = _detect_trim_start(image)
    bottom = _detect_trim_end(image)
    left = _detect_trim_left(image)
    right = _detect_trim_right(image)

    crop_left = left
    crop_top = top
    crop_right = max(crop_left + 1, image.width - right)
    crop_bottom = max(crop_top + 1, image.height - bottom)

    if crop_right <= crop_left or crop_bottom <= crop_top:
        return image
    return image.crop((crop_left, crop_top, crop_right, crop_bottom))


def load_trimmed_image(source_image_path: str | Path) -> Image.Image:
    return trim_uniform_border(Image.open(Path(source_image_path)).convert("RGB"))


def resize_cover(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    scale = max(target_width / image.width, target_height / image.height)
    resized_width = max(1, int(round(image.width * scale)))
    resized_height = max(1, int(round(image.height * scale)))
    resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)

    crop_left = max(0, (resized_width - target_width) // 2)
    crop_top = max(0, (resized_height - target_height) // 2)
    crop_right = crop_left + target_width
    crop_bottom = crop_top + target_height
    return resized.crop((crop_left, crop_top, crop_right, crop_bottom))


def resize_contain(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    scale = min(target_width / image.width, target_height / image.height)
    resized_width = max(1, int(round(image.width * scale)))
    resized_height = max(1, int(round(image.height * scale)))
    return image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)


def resolve_label_height(box_height: int) -> int:
    return max(
        LABEL_BAR_MIN_HEIGHT_PX,
        min(LABEL_BAR_MAX_HEIGHT_PX, int(box_height * LABEL_BAR_HEIGHT_RATIO)),
    )


def split_slot_box(box: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    label_height = resolve_label_height(int(box["height"]))
    image_height = max(1, int(box["height"]) - label_height)
    image_box = {
        "x": int(box["x"]),
        "y": int(box["y"]),
        "width": int(box["width"]),
        "height": image_height,
    }
    label_box = {
        "x": int(box["x"]),
        "y": int(box["y"]) + image_height,
        "width": int(box["width"]),
        "height": label_height,
    }
    return image_box, label_box


def render_slot_label(
    *,
    draw: ImageDraw.ImageDraw,
    font_path: Path,
    label_box: dict[str, int],
    label_text: str,
) -> None:
    draw.rectangle(
        (
            int(label_box["x"]),
            int(label_box["y"]),
            int(label_box["x"]) + int(label_box["width"]),
            int(label_box["y"]) + int(label_box["height"]),
        ),
        fill=LABEL_BAR_FILL,
    )

    font = fit_font(
        draw,
        label_text,
        font_path,
        max_width=int(label_box["width"]) - 2 * LABEL_SIDE_PADDING_PX,
        font_size=max(LABEL_FONT_MIN_SIZE, int(label_box["height"]) // LABEL_FONT_DIVISOR),
    )
    left, top, right, bottom = draw.textbbox((0, 0), label_text, font=font)
    text_x = int(label_box["x"]) + (int(label_box["width"]) - (right - left)) // 2
    text_y = int(label_box["y"]) + (int(label_box["height"]) - (bottom - top)) // 2 - top
    draw.text((text_x, text_y), label_text, fill=LABEL_TEXT_FILL, font=font)


def render_board_image(slots: list[dict[str, object]], output_path: Path) -> None:
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(canvas)
    font_path = resolve_label_font_path()

    for slot in slots:
        image = load_trimmed_image(str(slot["source_image_path"]))
        box = slot["target_box"]
        image_box, label_box = split_slot_box(box)
        fit_mode = str(slot.get("fit_mode", "cover"))
        if fit_mode == "contain":
            resized = resize_contain(image, image_box["width"], image_box["height"])
            paste_x = image_box["x"] + (image_box["width"] - resized.width) // 2
            paste_y = image_box["y"] + (image_box["height"] - resized.height)
            canvas.paste(resized, (paste_x, paste_y))
        else:
            resized = resize_cover(image, image_box["width"], image_box["height"])
            canvas.paste(resized, (image_box["x"], image_box["y"]))
        render_slot_label(
            draw=draw,
            font_path=font_path,
            label_box=label_box,
            label_text=str(slot["label_text"]),
        )

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
        target_boxes = (
            build_dual_asset_boxes(ordered_assets)
            if layout_template == "grid_2x1"
            else build_target_boxes(layout_template)
        )
        board_path = (artifacts.boards_dir / f"{shot.id}.png").resolve()

        render_slots_payload: list[dict[str, object]] = []
        slots_payload: list[dict[str, object]] = []
        blank_slots: list[int] = []
        for box, asset in zip(target_boxes, ordered_assets, strict=False):
            render_slots_payload.append(
                {
                    "slot_index": box["slot_index"],
                    "row": box["row"],
                    "col": box["col"],
                    "asset_type": asset["asset_type"],
                    "asset_id": asset["asset_id"],
                    "source_image_path": asset["source_image_path"],
                    "label_text": asset["label_text"],
                    "fit_mode": "contain" if layout_template == "grid_2x1" else "cover",
                    "target_box": {
                        "x": box["x"],
                        "y": box["y"],
                        "width": box["width"],
                        "height": box["height"],
                    },
                }
            )
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

        render_board_image(render_slots_payload, board_path)

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
            "preserve_asset_labels": False,
            "add_overlay_text": True,
            "blank_cell_fill": BLANK_CELL_FILL,
        },
        "boards": boards_payload,
    }
    manifest = ShotReferenceManifest.model_validate(manifest_payload)
    manifest_path = artifacts.board_dir / "shot_reference_manifest.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))

    return artifacts
