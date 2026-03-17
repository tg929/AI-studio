"""Asset image generation node."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
import subprocess
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from pipeline.io import dump_model, read_json, write_json
from pipeline.runtime import ImageModelConfig, build_image_client
from prompts.asset_images import (
    build_character_render_prompt,
    build_prop_render_prompt,
    build_scene_render_prompt,
)
from schemas.asset_images_manifest import AssetImagesManifest
from schemas.asset_prompts import AssetPrompts, CharacterAssetPrompt, PropAssetPrompt, SceneAssetPrompt


SIZE_BY_ASPECT_RATIO = {
    "3:4": "768x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "1:1": "1024x1024",
}

DISABLE_PLATFORM_WATERMARK = True


@dataclass(frozen=True, slots=True)
class AssetImageArtifacts:
    run_dir: Path
    image_dir: Path
    raw_dir: Path
    raw_character_dir: Path
    raw_scene_dir: Path
    raw_prop_dir: Path
    character_dir: Path
    scene_dir: Path
    prop_dir: Path
    response_dir: Path


def resolve_run_dir(asset_prompts_path: Path) -> Path:
    if asset_prompts_path.name != "asset_prompts.json":
        raise ValueError(f"Expected an asset_prompts.json file: {asset_prompts_path}")
    if asset_prompts_path.parent.name != "04_asset_prompts":
        raise ValueError(f"Expected asset_prompts.json under a 04_asset_prompts directory: {asset_prompts_path}")
    return asset_prompts_path.parent.parent


def build_image_artifacts(run_dir: Path) -> AssetImageArtifacts:
    image_dir = run_dir / "05_asset_images"
    raw_dir = image_dir / "raw"
    raw_character_dir = raw_dir / "characters"
    raw_scene_dir = raw_dir / "scenes"
    raw_prop_dir = raw_dir / "props"
    character_dir = image_dir / "characters"
    scene_dir = image_dir / "scenes"
    prop_dir = image_dir / "props"
    response_dir = image_dir / "responses"
    for path in (
        image_dir,
        raw_dir,
        raw_character_dir,
        raw_scene_dir,
        raw_prop_dir,
        character_dir,
        scene_dir,
        prop_dir,
        response_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return AssetImageArtifacts(
        run_dir=run_dir,
        image_dir=image_dir,
        raw_dir=raw_dir,
        raw_character_dir=raw_character_dir,
        raw_scene_dir=raw_scene_dir,
        raw_prop_dir=raw_prop_dir,
        character_dir=character_dir,
        scene_dir=scene_dir,
        prop_dir=prop_dir,
        response_dir=response_dir,
    )


def infer_suffix_from_url(url: str, default: str = ".png") -> str:
    suffix = Path(urlparse(url).path).suffix
    return suffix or default


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "curl",
            "-fsSL",
            "--http1.1",
            "--tlsv1.2",
            "--retry",
            "3",
            "--retry-delay",
            "1",
            "--output",
            str(dest),
            url,
        ],
        check=True,
    )


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
    raise FileNotFoundError("No usable Chinese font file found for local asset label rendering")


def fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: Path, max_width: int, font_size: int):
    while font_size >= 18:
        font = ImageFont.truetype(str(font_path), font_size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= max_width:
            return font
        font_size -= 2
    return ImageFont.truetype(str(font_path), 18)


def render_labeled_card(raw_image_path: Path, output_path: Path, label_text: str) -> None:
    image = Image.open(raw_image_path).convert("RGB")
    width, height = image.size
    label_bar_height = max(96, height // 7)
    canvas = Image.new("RGB", (width, height + label_bar_height), color="white")
    canvas.paste(image, (0, 0))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, height, width, height + label_bar_height), fill="black")

    font_path = resolve_label_font_path()
    font = fit_font(draw, label_text, font_path, width - 48, max(28, label_bar_height // 3))
    left, top, right, bottom = draw.textbbox((0, 0), label_text, font=font)
    text_width = right - left
    text_height = bottom - top
    text_x = (width - text_width) // 2
    text_y = height + (label_bar_height - text_height) // 2 - top
    draw.text((text_x, text_y), label_text, fill="white", font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_format = "PNG" if output_path.suffix.lower() == ".png" else "JPEG"
    canvas.save(output_path, format=image_format, quality=95)


def generate_single_image(
    *,
    client,
    model_name: str,
    render_prompt: str,
    size: str,
):
    response = client.images.generate(
        model=model_name,
        prompt=render_prompt,
        response_format="b64_json",
        size=size,
        watermark=not DISABLE_PLATFORM_WATERMARK,
        optimize_prompt=False,
        timeout=300.0,
    )
    if not response.data:
        raise ValueError("Image model returned no image data")
    image_item = response.data[0]
    image_b64 = getattr(image_item, "b64_json", "")
    image_url = getattr(image_item, "url", "")
    if not image_b64 and not image_url:
        raise ValueError("Image model returned neither image bytes nor download URL")
    return response, image_url, image_b64


def write_b64_image(image_b64: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(image_b64))


def build_jobs_payload(asset_prompts: AssetPrompts) -> dict[str, list[dict[str, str]]]:
    return {
        "characters": [
            {
                "id": item.id,
                "name": item.name,
                "label_text": item.label_text,
                "requested_size": SIZE_BY_ASPECT_RATIO[item.aspect_ratio],
                "render_prompt": build_character_render_prompt(
                    item,
                    visual_style=asset_prompts.visual_style,
                    consistency_anchors=asset_prompts.consistency_anchors,
                ),
            }
            for item in asset_prompts.characters
        ],
        "scenes": [
            {
                "id": item.id,
                "name": item.name,
                "label_text": item.label_text,
                "requested_size": SIZE_BY_ASPECT_RATIO[item.aspect_ratio],
                "render_prompt": build_scene_render_prompt(
                    item,
                    visual_style=asset_prompts.visual_style,
                    consistency_anchors=asset_prompts.consistency_anchors,
                ),
            }
            for item in asset_prompts.scenes
        ],
        "props": [
            {
                "id": item.id,
                "name": item.name,
                "label_text": item.label_text,
                "requested_size": SIZE_BY_ASPECT_RATIO[item.aspect_ratio],
                "render_prompt": build_prop_render_prompt(
                    item,
                    visual_style=asset_prompts.visual_style,
                    consistency_anchors=asset_prompts.consistency_anchors,
                ),
            }
            for item in asset_prompts.props
        ],
    }


def build_character_manifest_entry(
    item: CharacterAssetPrompt,
    requested_size: str,
    render_prompt: str,
    raw_image_path: Path,
    image_path: Path,
    response_path: Path,
    remote_url: str,
) -> dict[str, str]:
    return {
        "id": item.id,
        "name": item.name,
        "label_text": item.label_text,
        "aspect_ratio": item.aspect_ratio,
        "requested_size": requested_size,
        "render_prompt": render_prompt,
        "negative_prompt": item.negative_prompt,
        "raw_image_path": str(raw_image_path),
        "local_image_path": str(image_path),
        "raw_response_path": str(response_path),
        "remote_url": remote_url or "",
    }


def build_scene_manifest_entry(
    item: SceneAssetPrompt,
    requested_size: str,
    render_prompt: str,
    raw_image_path: Path,
    image_path: Path,
    response_path: Path,
    remote_url: str,
) -> dict[str, str]:
    return {
        "id": item.id,
        "name": item.name,
        "label_text": item.label_text,
        "aspect_ratio": item.aspect_ratio,
        "requested_size": requested_size,
        "render_prompt": render_prompt,
        "negative_prompt": item.negative_prompt,
        "raw_image_path": str(raw_image_path),
        "local_image_path": str(image_path),
        "raw_response_path": str(response_path),
        "remote_url": remote_url or "",
    }


def build_prop_manifest_entry(
    item: PropAssetPrompt,
    requested_size: str,
    render_prompt: str,
    raw_image_path: Path,
    image_path: Path,
    response_path: Path,
    remote_url: str,
) -> dict[str, str]:
    return {
        "id": item.id,
        "name": item.name,
        "label_text": item.label_text,
        "aspect_ratio": item.aspect_ratio,
        "requested_size": requested_size,
        "render_prompt": render_prompt,
        "negative_prompt": item.negative_prompt,
        "raw_image_path": str(raw_image_path),
        "local_image_path": str(image_path),
        "raw_response_path": str(response_path),
        "remote_url": remote_url or "",
    }


def generate_asset_images(
    *,
    asset_prompts_path: Path,
    model_config: ImageModelConfig,
    dry_run: bool = False,
) -> AssetImageArtifacts:
    asset_prompts = AssetPrompts.model_validate(read_json(asset_prompts_path))
    run_dir = resolve_run_dir(asset_prompts_path)
    artifacts = build_image_artifacts(run_dir)

    jobs_payload = build_jobs_payload(asset_prompts)
    jobs_path = artifacts.image_dir / "asset_image_jobs.json"
    write_json(jobs_path, jobs_payload)

    if dry_run:
        return artifacts

    client = build_image_client(model_config)

    character_entries = []
    for item, job in zip(asset_prompts.characters, jobs_payload["characters"], strict=True):
        response, image_url, image_b64 = generate_single_image(
            client=client,
            model_name=model_config.model_name,
            render_prompt=job["render_prompt"],
            size=job["requested_size"],
        )
        response_path = artifacts.response_dir / f"{item.id}.json"
        write_json(response_path, dump_model(response))
        raw_suffix = infer_suffix_from_url(image_url) if image_url else ".png"
        raw_image_path = artifacts.raw_character_dir / f"{item.id}{raw_suffix}"
        image_path = artifacts.character_dir / f"{item.id}.jpeg"
        if image_b64:
            write_b64_image(image_b64, raw_image_path)
        else:
            download_file(image_url, raw_image_path)
        render_labeled_card(raw_image_path, image_path, item.label_text)
        character_entries.append(
            build_character_manifest_entry(
                item,
                job["requested_size"],
                job["render_prompt"],
                raw_image_path,
                image_path,
                response_path,
                image_url,
            )
        )

    scene_entries = []
    for item, job in zip(asset_prompts.scenes, jobs_payload["scenes"], strict=True):
        response, image_url, image_b64 = generate_single_image(
            client=client,
            model_name=model_config.model_name,
            render_prompt=job["render_prompt"],
            size=job["requested_size"],
        )
        response_path = artifacts.response_dir / f"{item.id}.json"
        write_json(response_path, dump_model(response))
        raw_suffix = infer_suffix_from_url(image_url) if image_url else ".png"
        raw_image_path = artifacts.raw_scene_dir / f"{item.id}{raw_suffix}"
        image_path = artifacts.scene_dir / f"{item.id}.jpeg"
        if image_b64:
            write_b64_image(image_b64, raw_image_path)
        else:
            download_file(image_url, raw_image_path)
        render_labeled_card(raw_image_path, image_path, item.label_text)
        scene_entries.append(
            build_scene_manifest_entry(
                item,
                job["requested_size"],
                job["render_prompt"],
                raw_image_path,
                image_path,
                response_path,
                image_url,
            )
        )

    prop_entries = []
    for item, job in zip(asset_prompts.props, jobs_payload["props"], strict=True):
        response, image_url, image_b64 = generate_single_image(
            client=client,
            model_name=model_config.model_name,
            render_prompt=job["render_prompt"],
            size=job["requested_size"],
        )
        response_path = artifacts.response_dir / f"{item.id}.json"
        write_json(response_path, dump_model(response))
        raw_suffix = infer_suffix_from_url(image_url) if image_url else ".png"
        raw_image_path = artifacts.raw_prop_dir / f"{item.id}{raw_suffix}"
        image_path = artifacts.prop_dir / f"{item.id}.jpeg"
        if image_b64:
            write_b64_image(image_b64, raw_image_path)
        else:
            download_file(image_url, raw_image_path)
        render_labeled_card(raw_image_path, image_path, item.label_text)
        prop_entries.append(
            build_prop_manifest_entry(
                item,
                job["requested_size"],
                job["render_prompt"],
                raw_image_path,
                image_path,
                response_path,
                image_url,
            )
        )

    manifest = AssetImagesManifest.model_validate(
        {
            "schema_version": "1.0",
            "source_script_name": asset_prompts.source_script_name,
            "title": asset_prompts.title,
            "image_model": model_config.model_name,
            "characters": character_entries,
            "scenes": scene_entries,
            "props": prop_entries,
        }
    )
    manifest_path = artifacts.image_dir / "asset_images_manifest.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))

    return artifacts
